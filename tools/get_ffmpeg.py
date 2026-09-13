# -*- coding: utf-8 -*-
"""
下载 ffmpeg.exe 到 tools/ 目录（bili-dl 合并音视频要用）。

用法：  python tools/get_ffmpeg.py
仓库里不放 ffmpeg 二进制（100MB+），首次使用跑一次这个脚本即可。
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'ffmpeg.exe')
# gyan.dev 的 release 包是浮动指向最新版的；再备一个 BtbN 的 GitHub Release 兜底
URLS = [
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if os.path.isfile(TARGET) and os.path.getsize(TARGET) > 1024 * 1024:
        print(f'已存在：{TARGET}（{os.path.getsize(TARGET)/1048576:.1f} MB），无需下载。')
        return 0

    import urllib.request

    zp = os.path.join(HERE, 'ffmpeg.zip')
    done = 0
    ok = False
    for url in URLS:
        print(f'正在下载 ffmpeg …\n  {url}')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(zp, 'wb') as f:
                total = int(r.headers.get('Content-Length') or 0)
                done = 0
                mark = 0
                while True:
                    chunk = r.read(1048576)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    pct = done * 100 // total if total else 0
                    if pct >= mark + 10:
                        mark = pct
                        print(f'  {pct:3d}%  {done/1048576:6.1f} MB')
            ok = True
            break
        except Exception as e:  # noqa: BLE001
            print(f'  这个源失败了（{type(e).__name__}: {e}），换下一个 …')
    if not ok:
        print('所有下载源都失败了。请手动下载 ffmpeg.exe 放进 tools/ 目录。')
        return 1
    print(f'下载完成（{done/1048576:.1f} MB），正在解压 …')

    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.lower().endswith('bin/ffmpeg.exe')]
        if not names:
            print('压缩包里没找到 ffmpeg.exe，可能是下载源变了。')
            return 1
        with z.open(names[0]) as src, open(TARGET, 'wb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)   # 别把 100MB 一次性读进内存
    os.remove(zp)
    print(f'完成：{TARGET}（{os.path.getsize(TARGET)/1048576:.1f} MB）')
    print('现在可以运行 启动.bat 或 python bili_dl.py 了。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
