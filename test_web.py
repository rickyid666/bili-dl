import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8848'


def post(path, data=None):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(data or {}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=20))


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=20))


html = urllib.request.urlopen(BASE + '/', timeout=20).read().decode('utf-8')
print(f'[1] 首页 {len(html)} 字节, 含标题: {"bili_dl" in html}')
print(f'[2] /api/config -> {get("/api/config")}')

r = post('/api/task', {'url': 'BV1jw8w6yESY', 'quality': '480', 'parts': '1'})
print(f'[3] 提交任务 -> {r}')
tid = r.get('id')
if not tid:
    raise SystemExit('no task id')

last = ''
for _ in range(180):
    t = get(f'/api/task?id={tid}')
    line = f"{t['status']:<8} {t.get('stage',''):<28} {t.get('percent',0):3d}%  {t.get('done',0)/1048576:.1f}MB"
    if line != last:
        print('    ' + line)
        last = line
    if t['status'] in ('done', 'error'):
        print('[4] 最终:', json.dumps({k: v for k, v in t.items() if k != 'files'},
                                     ensure_ascii=False))
        for f in t.get('files', []):
            print(f"     -> {f['name']}  {f['quality']}  {f['size']/1048576:.2f}MB")
        break
    time.sleep(0.5)

print('[5] /api/open ->', post('/api/open'))
