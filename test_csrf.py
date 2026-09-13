"""验证 Web UI 的跨站防护：同源放行、跨站拦截。"""
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8848'


def post(headers, body=None, path='/api/task'):
    data = json.dumps(body or {}).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode('utf-8')[:70]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')[:70]


print('1) 无 Origin（本机脚本/curl）  ->', post(
    {'Content-Type': 'application/json'}, {'url': 'BV0000000000'}))
print('2) 同源 Origin 127.0.0.1      ->', post(
    {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:8848'}, {'url': 'BV0000000000'}))
print('3) 跨站 Origin evil.example   ->', post(
    {'Content-Type': 'application/json', 'Origin': 'http://evil.example'}, {'url': 'BV0000000000'}))
print('4) 跨站简单请求 text/plain     ->', post(
    {'Content-Type': 'text/plain', 'Origin': 'http://evil.example'}, {'url': 'BV0000000000'}))
print('5) 同源 text/plain（也拒）     ->', post(
    {'Content-Type': 'text/plain', 'Origin': 'http://127.0.0.1:8848'}, {'url': 'BV0000000000'}))
print('6) OPTIONS 预检（不响应即阻止）->', end=' ')
req = urllib.request.Request(BASE + '/api/task', method='OPTIONS')
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(r.status, r.headers.get('Access-Control-Allow-Origin'))
except urllib.error.HTTPError as e:
    print(e.code, '(无 CORS 头 = 浏览器会阻止跨站 JSON 请求)')
