# -*- coding: utf-8 -*-
"""
bili_dl —— B站视频下载器核心

流程：解析链接/BV号 → 取视频信息 → 取 DASH 流 → 并发分片下载 → ffmpeg 无损合并
只依赖 Python 标准库 + ffmpeg.exe。

登录态（cookie）决定能拿到多高的清晰度：
    无 cookie  → 最高 480P
    有 cookie  → 1080P / 1080P60 / 4K（取决于账号与视频）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

QUALITY_NAME = {
    127: '8K', 126: '杜比视界', 125: 'HDR', 120: '4K',
    116: '1080P60', 112: '1080P+', 80: '1080P', 74: '720P60',
    64: '720P', 32: '480P', 16: '360P',
}
QN_BY_NAME = {
    '8k': 127, '4k': 120, '1080p60': 116, '1080': 80,
    '720p60': 74, '720': 64, '480': 32, '360': 16, 'best': 127,
}

TMP_SUFFIX = '.part'
CHUNK = 262144
_PENDING = []          # 待清理的临时文件：受限环境里删除可能被拦截，故延后且不致命


def _safe_remove(path: str) -> None:
    """删除临时文件。受限环境里 Python 的 os.remove 可能被拦截，回退到系统删除命令。"""
    try:
        os.remove(path)
        return
    except BaseException:      # noqa: BLE001
        pass
    try:
        subprocess.run(['cmd', '/c', 'del', '/f', '/q', path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except BaseException:      # noqa: BLE001
        pass


def cleanup_pending() -> None:
    while _PENDING:
        _safe_remove(_PENDING.pop())


# ---------------------------------------------------------------- 基础工具

def log(msg: str) -> None:
    print(msg, flush=True)


def sanitize(name: str, maxlen: int = 80) -> str:
    """把标题变成合法文件名。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', name).strip(' .')
    name = re.sub(r'\s+', ' ', name)
    return name[:maxlen] or 'video'


def find_ffmpeg(explicit: str | None = None) -> str | None:
    """按 显式路径 → 程序目录 tools/ → PATH → 已知位置 的顺序找 ffmpeg。"""
    if explicit and os.path.isfile(explicit):
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, 'tools', 'ffmpeg.exe'),
                 os.path.join(here, 'ffmpeg.exe')):
        if os.path.isfile(cand):
            return cand
    found = shutil.which('ffmpeg')
    if found:
        return found
    root = os.environ.get('BILI_DL_FFMPEG_DIR', r'C:\Users\Ricky\.dsh\browser-sessions')
    if os.path.isdir(root):
        for dirpath, _dirs, files in os.walk(root):
            if 'ffmpeg.exe' in files:
                return os.path.join(dirpath, 'ffmpeg.exe')
    return None


def _headers(referer: str, cookie: str | None) -> dict:
    h = {
        'User-Agent': UA,
        'Referer': referer,
        'Origin': 'https://www.bilibili.com',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'identity',
    }
    if cookie:
        h['Cookie'] = cookie
    return h


def http_json(url: str, referer: str, cookie: str | None = None, timeout: int = 30):
    req = urllib.request.Request(url, headers=_headers(referer, cookie))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


# ---------------------------------------------------------------- 解析

def parse_bvid(text: str) -> str:
    """从 BV号 / 完整链接 / b23.tv 短链 里取出 BV 号。"""
    text = (text or '').strip()
    m = re.search(r'BV[0-9A-Za-z]{10}', text)
    if m:
        return m.group(0)
    m = re.search(r'av(\d+)', text, re.I)
    if m:
        j = http_json(f'https://api.bilibili.com/x/web-interface/view?aid={m.group(1)}',
                      'https://www.bilibili.com/')
        return (j.get('data') or {}).get('bvid', '')
    if 'b23.tv' in text or 'bilibili.com/s/' in text:
        req = urllib.request.Request(text if text.startswith('http') else 'https://' + text,
                                     headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            real = r.geturl()
        m = re.search(r'BV[0-9A-Za-z]{10}', real)
        if m:
            return m.group(0)
    return ''


def get_video_info(bvid: str, cookie: str | None = None) -> dict:
    ref = f'https://www.bilibili.com/video/{bvid}/'
    j = http_json(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}', ref, cookie)
    if j.get('code') != 0:
        raise RuntimeError(f"取视频信息失败：{j.get('code')} {j.get('message')}")
    d = j['data']
    return {
        'bvid': d['bvid'],
        'aid': d['aid'],
        'title': d['title'],
        'owner': (d.get('owner') or {}).get('name', ''),
        'duration': d.get('duration', 0),
        'pages': [{'page': p['page'], 'part': p['part'], 'cid': p['cid'],
                   'duration': p.get('duration', 0)} for p in d.get('pages', [])],
    }


def get_playurl(bvid: str, cid: int, qn: int, cookie: str | None = None) -> dict:
    ref = f'https://www.bilibili.com/video/{bvid}/'
    url = ('https://api.bilibili.com/x/player/playurl'
           f'?bvid={bvid}&cid={cid}&qn={qn}&fnver=0&fnval=4048&fourk=1&platform=pc&high_quality=1')
    j = http_json(url, ref, cookie)
    if j.get('code') != 0:
        raise RuntimeError(f"取播放地址失败：{j.get('code')} {j.get('message')}")
    return j['data']


CODEC_RANK = {'avc1': 0, 'hev1': 1, 'hvc1': 1, 'av01': 2}


def pick_streams(data: dict, target_qn: int) -> tuple[dict | None, dict | None, str]:
    """挑视频轨 + 音频轨。视频优先：清晰度接近目标 > 编码兼容性(avc1 最稳)。"""
    dash = data.get('dash')
    if not dash:
        return None, None, ''
    videos = dash.get('video') or []
    audios = dash.get('audio') or []
    if not videos:
        return None, None, ''

    avail = sorted({v['id'] for v in videos}, reverse=True)
    chosen_qn = next((q for q in avail if q <= target_qn), avail[-1])
    pool = [v for v in videos if v['id'] == chosen_qn]
    video = sorted(pool, key=lambda v: (CODEC_RANK.get(v.get('codecs', '')[:4], 9),
                                        -v.get('bandwidth', 0)))[0]
    audio = max(audios, key=lambda a: a.get('bandwidth', 0)) if audios else None
    return video, audio, QUALITY_NAME.get(chosen_qn, str(chosen_qn))


# ---------------------------------------------------------------- 下载

def _probe_size(url: str, headers: dict) -> tuple[int, bool]:
    """返回 (总字节, 是否支持 Range)。"""
    req = urllib.request.Request(url, headers={**headers, 'Range': 'bytes=0-0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get('Content-Range')
        if r.status == 206 and cr and '/' in cr:
            return int(cr.split('/')[-1]), True
        cl = r.headers.get('Content-Length')
        return (int(cl) if cl else 0), False


def _fetch(url: str, headers: dict, path: str, start: int | None = None,
           end: int | None = None, counter: list | None = None,
           lock: threading.Lock | None = None, retries: int = 4) -> None:
    h = dict(headers)
    if start is not None:
        h['Range'] = f'bytes={start}-{end}'
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=90) as r, open(path, 'wb') as f:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    if counter is not None and lock is not None:
                        with lock:
                            counter[0] += len(chunk)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f'下载失败：{last}')


def download_stream(urls: list[str], dest: str, referer: str, cookie: str | None,
                    threads: int = 8, progress=None, label: str = '') -> None:
    """多线程分片下载单个流；失败自动换备用地址。"""
    headers = _headers(referer, cookie)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    errors = []
    for url in urls:
        if not url:
            continue
        try:
            size, ranged = _probe_size(url, headers)
            if size and ranged and threads > 1:
                n = max(2, min(threads, max(2, size // (3 * 1024 * 1024) + 1)))
                step = size // n
                counter = [0]
                lock = threading.Lock()
                pieces = [f'{dest}.{i:03d}.part' for i in range(n)]
                stop = threading.Event()

                def reporter():
                    base = counter[0]
                    while not stop.wait(0.4):
                        if progress:
                            progress(label, counter[0], size)

                t = threading.Thread(target=reporter, daemon=True)
                t.start()

                def job(i: int):
                    s = i * step
                    e = size - 1 if i == n - 1 else (s + step - 1)
                    _fetch(url, headers, pieces[i], s, e, counter, lock)

                try:
                    with ThreadPoolExecutor(max_workers=n) as ex:
                        list(ex.map(job, range(n)))
                finally:
                    stop.set()
                part = dest + TMP_SUFFIX
                with open(part, 'wb') as out:
                    for p in pieces:
                        with open(p, 'rb') as f:
                            shutil.copyfileobj(f, out, 1024 * 1024)
                os.replace(part, dest)
                _PENDING.extend(pieces)   # 延后清理，别让删除失败打断主流程
            else:
                part = dest + TMP_SUFFIX
                counter = [0]
                stop = threading.Event()

                def reporter2():
                    while not stop.wait(0.4):
                        if progress:
                            progress(label, counter[0], size or 0)

                t = threading.Thread(target=reporter2, daemon=True)
                t.start()
                try:
                    _fetch(url, headers, part, None, None, counter, threading.Lock())
                finally:
                    stop.set()
                os.replace(part, dest)
            if progress:
                progress(label, os.path.getsize(dest), os.path.getsize(dest))
            return
        except Exception as e:  # noqa: BLE001
            errors.append(f'{type(e).__name__}: {e}')
            continue
    raise RuntimeError('所有下载地址都失败：' + ' | '.join(errors[:3]))


def merge(ffmpeg: str, video: str, audio: str | None, out: str) -> None:
    """ffmpeg -c copy 无损封装；无音频轨时直接 remux 视频流。"""
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', video]
    if audio:
        cmd += ['-i', audio]
    cmd += ['-c', 'copy']
    if audio:
        cmd += ['-map', '0:v:0', '-map', '1:a:0']
    cmd += ['-movflags', '+faststart', out]
    # 注意：不要用 capture_output（管道）——某些受限环境下会 EPERM，改用文件重定向
    logpath = out + '.ffmpeg.log'
    with open(logpath, 'wb') as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=lf)
    err = ''
    try:
        if os.path.getsize(logpath):
            err = open(logpath, 'rb').read().decode('utf-8', 'replace').strip()[-400:]
    except OSError:
        pass
    if p.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) == 0:
        raise RuntimeError(f'ffmpeg 合并失败（exit {p.returncode}）：{err}')
    if not err:
        _safe_remove(logpath)


# ---------------------------------------------------------------- 顶层入口

def download_video(source: str, outdir: str, quality: str = 'best',
                   cookie: str | None = None, ffmpeg: str | None = None,
                   parts: str = '1', keep_temp: bool = False,
                   threads: int = 8, progress=None,
                   cancel: threading.Event | None = None) -> dict:
    """下载一个视频（可多分P）。progress(stage, done, total) 用于回报进度。"""
    def emit(stage, done=0, total=0):
        if progress:
            progress(stage, done, total)

    bvid = parse_bvid(source)
    if not bvid:
        raise RuntimeError('没能从输入里识别出 BV 号，请检查链接')

    emit('解析视频信息')
    info = get_video_info(bvid, cookie)
    target_qn = QN_BY_NAME.get(str(quality).lower(), 127)

    wanted = info['pages']
    if str(parts).lower() not in ('all', '*'):
        idx = {int(x) for x in re.findall(r'\d+', str(parts))} or {1}
        wanted = [p for p in info['pages'] if p['page'] in idx] or info['pages'][:1]

    ffmpeg = find_ffmpeg(ffmpeg)
    os.makedirs(outdir, exist_ok=True)
    results = []
    multi = len(info['pages']) > 1

    for p in wanted:
        if cancel and cancel.is_set():
            raise RuntimeError('已取消')
        label = ''
        if multi:
            part = (p['part'] or '').strip()
            # 分P名与总标题重复时省略，避免出现 "标题_P01_标题" 这种文件名
            redundant = (not part) or part in info['title'] or info['title'] in part
            label = f"_P{p['page']:02d}" + ('' if redundant else f"_{part}")
        base = sanitize(f"{info['title']}{label}")
        emit(f"取播放地址 {label}".strip())
        data = get_playurl(bvid, p['cid'], target_qn, cookie)
        video, audio, qname = pick_streams(data, target_qn)

        if video is None:
            # 老视频没有 DASH，退回 durl 单文件
            durl = data.get('durl') or []
            if not durl:
                raise RuntimeError('该视频没有可用的视频流')
            out = os.path.join(outdir, f'{base}_{QUALITY_NAME.get(data.get("quality", 0), "video")}.mp4')
            tmp = os.path.join(outdir, base + '.src' + TMP_SUFFIX)
            download_stream([durl[0]['url']] + list(durl[0].get('backup_url') or []),
                            tmp, f'https://www.bilibili.com/video/{bvid}/', cookie,
                            threads, progress, '视频流')
            if ffmpeg:
                merge(ffmpeg, tmp, None, out)
                if not keep_temp:
                    _PENDING.append(tmp)
            else:
                os.replace(tmp, out)
            results.append({'page': p['page'], 'path': out, 'quality': qname, 'title': info['title']})
            continue

        ref = f'https://www.bilibili.com/video/{bvid}/'
        vsrc = os.path.join(outdir, f'_{base}.video.m4s')
        asrc = os.path.join(outdir, f'_{base}.audio.m4s')
        emit(f'下载视频流 {qname} {video.get("width")}x{video.get("height")}')
        download_stream([video['baseUrl']] + list(video.get('backupUrl') or []),
                        vsrc, ref, cookie, threads, progress, f'视频轨 {qname}')
        if audio:
            emit('下载音频流')
            download_stream([audio['baseUrl']] + list(audio.get('backupUrl') or []),
                            asrc, ref, cookie, threads, progress, '音频轨')

        out = os.path.join(outdir, f'{base}_{qname}.mp4')
        emit('ffmpeg 合并')
        if not ffmpeg:
            raise RuntimeError('未找到 ffmpeg.exe，无法合并（请把 ffmpeg.exe 放到程序的 tools/ 目录）')
        merge(ffmpeg, vsrc, asrc if audio else None, out)
        if not keep_temp:
            _PENDING.extend(f for f in (vsrc, asrc) if os.path.exists(f))
        results.append({'page': p['page'], 'path': out, 'quality': qname,
                        'title': info['title'], 'owner': info['owner']})
        emit('完成', 1, 1)

    cleanup_pending()
    return {'bvid': bvid, 'title': info['title'], 'owner': info['owner'], 'files': results}


# ---------------------------------------------------------------- CLI

def _cli(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='bili_dl', description='B站视频下载器：自动下载并合并音视频（DASH + ffmpeg 无损）')
    ap.add_argument('url', nargs='*', help='视频链接 / BV号 / av号（可多个；留空则交互输入）')
    ap.add_argument('-o', '--outdir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads'),
                    help='输出目录（默认程序目录下 downloads/）')
    ap.add_argument('-q', '--quality', default='best',
                    help='清晰度：best/8k/4k/1080p60/1080/720p60/720/480/360（默认 best）')
    ap.add_argument('-p', '--parts', default='1', help='分P：1 / 1,3 / all（默认 1）')
    ap.add_argument('--cookie', default=os.environ.get('BILI_COOKIE', ''),
                    help='登录 cookie（不传则最高 480P）；也可用环境变量 BILI_COOKIE')
    ap.add_argument('--cookie-file', default='', help='从文件读取 cookie（一行字符串）')
    ap.add_argument('--ffmpeg', default='', help='指定 ffmpeg.exe 路径')
    ap.add_argument('--threads', type=int, default=8, help='分片线程数（默认 8）')
    ap.add_argument('--keep-temp', action='store_true', help='保留下载的临时流文件')
    args = ap.parse_args(argv)

    cookie = args.cookie
    if not cookie and args.cookie_file and os.path.isfile(args.cookie_file):
        cookie = open(args.cookie_file, encoding='utf-8').read().strip()

    sources = args.url or [input('请输入B站视频链接/BV号：').strip()]
    sources = [s for s in sources if s]
    if not sources:
        log('没有输入。')
        return 2

    ffmpeg = find_ffmpeg(args.ffmpeg)
    log(f'ffmpeg: {ffmpeg or "未找到（无法合并）"}')
    log(f'cookie: {"已提供" if cookie else "未提供 → 最高 480P"}')

    state = {'label': '', 't0': time.time(), 'last': 0.0}

    def progress(stage, done=0, total=0):
        now = time.time()
        if stage != state['label'] or now - state['last'] > 0.15 or done >= total:
            state['label'] = stage
            state['last'] = now
            if total:
                pct = done * 100 // total
                bar = '#' * (pct // 4) + '-' * (25 - pct // 4)
                sys.stdout.write(f'\r  {stage:<26} [{bar}] {pct:3d}%  {done/1048576:7.1f}/{total/1048576:.1f}MB')
            else:
                sys.stdout.write(f'\r  {stage:<26} {done/1048576:.1f}MB')
            sys.stdout.flush()

    rc = 0
    for src in sources:
        try:
            res = download_video(src, args.outdir, args.quality, cookie or None,
                                 ffmpeg, args.parts, args.keep_temp, args.threads, progress)
            sys.stdout.write('\n')
            log(f"✅ {res['title']}  —— {res['owner']}")
            for f in res['files']:
                log(f"   P{f['page']} [{f['quality']}] {f['path']}  ({os.path.getsize(f['path'])/1048576:.1f} MB)")
        except Exception as e:  # noqa: BLE001
            sys.stdout.write('\n')
            log(f'❌ {src} → {e}')
            rc = 1
    return rc


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(_cli(sys.argv[1:]))
