# -*- coding: utf-8 -*-
"""
bili_dl Web UI —— 本地网页版 B站下载器

双击 启动.bat 或运行：python bili_web.py
然后浏览器打开 http://127.0.0.1:8848
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bili_dl  # noqa: E402

PORT = int(os.environ.get('BILI_DL_PORT', '8848'))
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(ROOT, 'downloads')
CONFIG = os.path.join(ROOT, 'config.json')
os.makedirs(OUTDIR, exist_ok=True)

TASKS: dict = {}
LOCK = threading.Lock()


def load_config() -> dict:
    try:
        with open(CONFIG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except Exception:  # noqa: BLE001
        pass


def run_task(tid: str, url: str, quality: str, parts: str, cookie: str) -> None:
    def progress(stage, done=0, total=0):
        with LOCK:
            t = TASKS.get(tid)
            if not t:
                return
            t['stage'] = stage
            t['done'] = done
            t['total'] = total
            t['percent'] = int(done * 100 / total) if total else 0

    with LOCK:
        TASKS[tid]['status'] = 'running'

    try:
        res = bili_dl.download_video(
            source=url, outdir=OUTDIR, quality=quality or 'best',
            cookie=cookie or None, parts=parts or '1',
            progress=progress)
        files = []
        for f in res['files']:
            try:
                size = os.path.getsize(f['path'])
            except OSError:
                size = 0
            files.append({'page': f['page'], 'quality': f['quality'],
                          'path': f['path'], 'name': os.path.basename(f['path']),
                          'size': size})
        with LOCK:
            t = TASKS[tid]
            t.update(status='done', title=res['title'], owner=res.get('owner', ''),
                     files=files, percent=100, stage='完成')
    except BaseException as e:  # noqa: BLE001
        with LOCK:
            TASKS[tid].update(status='error', error=f'{type(e).__name__}: {e}',
                              stage='失败')


PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>bili_dl · B站视频下载器</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#060d1a;color:#d6e6f7;
 font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;font-size:14px;
 background-image:radial-gradient(120% 80% at 85% -10%,rgba(77,166,255,.20),rgba(6,13,26,0) 60%),linear-gradient(165deg,#0a1a33,#060d1a 55%,#07182c)}
.wrap{max-width:760px;margin:0 auto;padding:34px 20px 60px}
h1{font-size:22px;margin:0 0 4px;font-weight:700;letter-spacing:.3px}
h1 span{color:#7fd3ff}
.sub{color:#7f9cba;font-size:12.5px;margin-bottom:22px}
.card{background:rgba(16,36,60,.72);border:1px solid #17324f;border-radius:14px;padding:18px;margin-bottom:16px}
label{display:block;font-size:12px;color:#5f86ab;letter-spacing:1.2px;margin:0 0 7px}
input,select{width:100%;padding:11px 12px;border-radius:9px;border:1px solid #1e4570;
 background:rgba(8,20,36,.9);color:#e6f1fc;font-size:13.5px;font-family:inherit;outline:none}
input:focus,select:focus{border-color:#3d7fbd;box-shadow:0 0 0 3px rgba(61,127,189,.18)}
.row{display:flex;gap:12px}
.row>div{flex:1}
button{margin-top:16px;width:100%;padding:12px;border:0;border-radius:10px;cursor:pointer;
 background:linear-gradient(135deg,#2b7fd4,#4da6ff);color:#04121f;font-size:15px;font-weight:700;
 font-family:inherit;letter-spacing:.5px}
button:disabled{opacity:.5;cursor:not-allowed}
button.ghost{background:rgba(32,68,110,.6);color:#bcd8f2;font-weight:500;font-size:13px;margin-top:10px}
.bar{height:9px;border-radius:6px;background:rgba(10,26,45,.9);overflow:hidden;margin:14px 0 9px;border:1px solid #16304d}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#2b7fd4,#7fd3ff);border-radius:6px}
.stage{display:flex;justify-content:space-between;font-size:12.5px;color:#9fbdd8}
.hide{display:none}
.mono{font-family:Consolas,monospace;font-size:12px}
.file{display:flex;justify-content:space-between;gap:10px;padding:9px 11px;border-radius:9px;
 background:rgba(20,44,72,.6);border:1px solid #1b3a5c;margin-bottom:8px;font-size:13px}
.file b{color:#8fe0ff;font-weight:600}
.err{color:#ff8fa8;background:rgba(90,20,40,.35);border:1px solid rgba(255,100,140,.35);
 border-radius:9px;padding:11px;font-size:12.5px;margin-top:12px;word-break:break-all}
.tip{font-size:11.5px;color:#6d8aa8;margin-top:7px;line-height:1.6}
.tip b{color:#8fe0ff}
details summary{cursor:pointer;color:#5f86ab;font-size:12px;letter-spacing:1.2px;margin-bottom:8px}
</style></head><body><div class="wrap">
<h1>bili_dl · <span>B站视频下载器</span></h1>
<div class="sub">粘贴链接 → 自动取流 → ffmpeg 无损合并为 mp4（不重新编码）</div>

<div class="card">
  <label>视频地址 / BV号（支持一次一个，或分号分隔多个）</label>
  <input id="url" placeholder="https://www.bilibili.com/video/BV1jw8w6yESY/  或  BV1jw8w6yESY" autofocus>
  <div class="row" style="margin-top:12px">
    <div><label>清晰度</label>
      <select id="quality">
        <option value="best">最高可用（best）</option>
        <option value="1080p60">1080P60</option>
        <option value="1080">1080P</option>
        <option value="720p60">720P60</option>
        <option value="720">720P</option>
        <option value="480">480P</option>
        <option value="360">360P</option>
      </select></div>
    <div><label>分P</label>
      <select id="parts">
        <option value="1">仅第 1 P</option>
        <option value="all">全部分P</option>
      </select></div>
  </div>
  <details style="margin-top:14px">
    <summary>登录 cookie（不填最高只有 480P）</summary>
    <input id="cookie" placeholder="SESSDATA=xxx; bili_jct=yyy; ...">
    <div class="tip">获取方式：在浏览器打开 bilibili.com 并登录 → F12 → Console → 输入
      <b>document.cookie</b> → 复制整串粘贴到这里。填一次会自动记住。</div>
  </details>
  <button id="go">开始下载</button>
</div>

<div class="card hide" id="prog">
  <div class="stage"><span id="stage">准备中…</span><span id="pct">0%</span></div>
  <div class="bar"><i id="bar"></i></div>
  <div class="stage"><span id="bytes"></span><span id="title"></span></div>
</div>

<div class="card hide" id="result">
  <label id="rlabel">已完成</label>
  <div id="files"></div>
  <button class="ghost" id="open">打开下载文件夹</button>
</div>

<div class="err hide" id="err"></div>

<script>
let tid=null, timer=null;
const $=id=>document.getElementById(id);
fetch('/api/config').then(r=>r.json()).then(c=>{
  if(c.cookie) $('cookie').value=c.cookie;
  if(c.quality) $('quality').value=c.quality;
  if(c.parts) $('parts').value=c.parts;
});
$('go').onclick=async()=>{
  const urls=$('url').value.trim();
  $('err').classList.add('hide'); $('result').classList.add('hide');
  if(!urls){alert('请输入视频地址或 BV 号');return;}
  $('go').disabled=true; $('prog').classList.remove('hide');
  $('stage').textContent='提交任务…'; $('bar').style.width='0%'; $('pct').textContent='0%';
  const r=await fetch('/api/task',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({url:urls,quality:$('quality').value,parts:$('parts').value,cookie:$('cookie').value.trim()})});
  const j=await r.json();
  if(!j.id){showErr(j.error||'提交失败');return;}
  tid=j.id; timer=setInterval(poll,400);
};
async function poll(){
  const r=await fetch('/api/task?id='+tid); const t=await r.json();
  $('stage').textContent=t.stage||'';
  const p=t.percent||0; $('bar').style.width=p+'%'; $('pct').textContent=p+'%';
  if(t.total) $('bytes').textContent=(t.done/1048576).toFixed(1)+' / '+(t.total/1048576).toFixed(1)+' MB';
  if(t.title) $('title').textContent=t.title;
  if(t.status==='done'){clearInterval(timer);$('go').disabled=false;render(t);}
  if(t.status==='error'){clearInterval(timer);$('go').disabled=false;showErr(t.error);}
}
function render(t){
  $('result').classList.remove('hide');
  $('rlabel').textContent='已完成 · '+(t.title||'')+(t.owner?(' · '+t.owner):'');
  $('files').innerHTML=(t.files||[]).map(f=>
    '<div class="file"><span>'+f.name+'</span><b>'+f.quality+' · '+(f.size/1048576).toFixed(1)+'MB</b></div>').join('');
}
function showErr(m){$('err').textContent=m;$('err').classList.remove('hide');$('prog').classList.add('hide');}
$('open').onclick=()=>fetch('/api/open',{method:'POST'});
</script></div></body></html>
'''


class Handler(BaseHTTPRequestHandler):
    server_version = 'bili_dl'

    def log_message(self, *args):  # 安静点
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith('/api/task'):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            tid = (q.get('id') or [''])[0]
            with LOCK:
                t = TASKS.get(tid)
            if not t:
                return self._json({'error': 'no such task'}, 404)
            return self._json(t)
        if self.path.startswith('/api/config'):
            return self._json(load_config())
        body = PAGE.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b'{}'
        if self.path.startswith('/api/open'):
            try:
                os.startfile(OUTDIR)  # noqa: S606
            except Exception as e:  # noqa: BLE001
                return self._json({'error': str(e)}, 500)
            return self._json({'ok': True})
        if self.path.startswith('/api/task'):
            try:
                req = json.loads(raw.decode('utf-8'))
            except Exception:  # noqa: BLE001
                return self._json({'error': 'bad json'}, 400)
            url = (req.get('url') or '').strip()
            if not url:
                return self._json({'error': '缺少地址'}, 400)
            cfg = {'cookie': req.get('cookie', ''), 'quality': req.get('quality', 'best'),
                   'parts': req.get('parts', '1')}
            save_config(cfg)
            tid = uuid.uuid4().hex[:12]
            with LOCK:
                TASKS[tid] = {'id': tid, 'status': 'queued', 'stage': '排队中',
                              'done': 0, 'total': 0, 'percent': 0, 'files': []}
            threading.Thread(target=run_task, args=(
                tid, url, cfg['quality'], cfg['parts'], cfg['cookie']), daemon=True).start()
            return self._json({'id': tid})
        self._json({'error': 'not found'}, 404)


def main() -> None:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ff = bili_dl.find_ffmpeg()
    print('=' * 56)
    print('  bili_dl · B站视频下载器')
    print('=' * 56)
    print(f'  ffmpeg : {ff or "未找到（无法合并！）"}')
    print(f'  输出到 : {OUTDIR}')
    print(f'  地址   : http://127.0.0.1:{PORT}')
    print('  关闭这个窗口即停止服务')
    print('=' * 56)
    try:
        if not os.environ.get('BILI_DL_NO_BROWSER'):
            webbrowser.open(f'http://127.0.0.1:{PORT}')
    except Exception:  # noqa: BLE001
        pass
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as e:
        print(f'[错误] 端口 {PORT} 起不来：{e}')
        print(f'        可能是端口被占用。换一个端口再试，例如：')
        print(f'        set BILI_DL_PORT=8849')
        print(f'        python bili_web.py')
        return
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()
