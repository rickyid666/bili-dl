# -*- coding: utf-8 -*-
"""
下载 ffmpeg.exe 到 tools/ 目录（bili-dl 合并音视频要用）。

用法：  python tools/get_ffmpeg.py
仓库里不放 ffmpeg 二进制（100MB+），首次使用跑一次这个脚本即可。
"""
from __future__ import annotations

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'ffmpeg.exe')
URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if os.path.isfile(TARGET) and os.path.getsize(TARGET) > 1024 * 1024:
        print(f'已存在：{TARGET}（{os.path.getsize(TARGET)/1048576:.1f} MB），无需下载。')
        return 0

    import urllib.request

    zp = os.path.join(HERE, 'ffmpeg.zip')
    print(f'正在下载 ffmpeg …\n  {URL}')
    req = urllib.request.Request(URL, headers={'User-Agent': UA})
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
    print(f'下载完成（{done/1048576:.1f} MB），正在解压 …')

    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.lower().endswith('bin/ffmpeg.exe')]
        if not names:
            print('压缩包里没找到 ffmpeg.exe，可能是下载源变了。')
            return 1
        with z.open(names[0]) as src, open(TARGET, 'wb') as dst:
            dst.write(src.read())
    os.remove(zp)
    print(f'完成：{TARGET}（{os.path.getsize(TARGET)/1048576:.1f} MB）')
    print('现在可以运行 启动.bat 或 python bili_dl.py 了。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
