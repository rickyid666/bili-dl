# -*- coding: utf-8 -*-
"""生成 Windows 原生批处理：GBK 编码 + CRLF 行尾（cmd 的唯一安全写法）"""
import os

D = r"C:\Users\Ricky\.dsh\browser-sessions\bili-dl"

START = r'''@echo off
setlocal
cd /d "%~dp0"
title bili_dl - B站视频下载器

where python >nul 2>nul
if errorlevel 1 goto nopython

if not exist "tools\ffmpeg.exe" echo [警告] 没找到 tools\ffmpeg.exe，下载后无法合并音视频。

echo ============================================
echo    bili_dl   B站视频下载器
echo ============================================
echo    浏览器会自动打开： http://127.0.0.1:8848
echo    关闭本窗口即停止服务
echo ============================================
echo.

python "bili_web.py"
set RC=%ERRORLEVEL%

echo.
if not "%RC%"=="0" echo [出错] 程序退出码 %RC%（若是端口被占用，见 README 的说明）
echo 服务已停止。按任意键关闭窗口。
pause >nul
exit /b %RC%

:nopython
echo [错误] 在 PATH 里找不到 python。
echo 请先安装 Python 3，或把 python.exe 所在目录加进系统 Path。
echo.
pause >nul
exit /b 1
'''

CLI = r'''@echo off
setlocal
cd /d "%~dp0"
title bili_dl - 命令行下载

echo ============================================
echo    bili_dl   命令行下载
echo ============================================
echo.

if not "%~1"=="" (
  set "URL=%~1"
) else (
  set /p "URL=请输入B站视频链接或BV号： "
)

if "%URL%"=="" echo 没有输入，退出。& pause >nul & exit /b 1

echo.
echo 清晰度：best / 1080p60 / 1080 / 720p60 / 720 / 480 / 360
if "%~2"=="" (
  set /p "Q=清晰度（直接回车用 best）： "
) else (
  set "Q=%~2"
)
if "%Q%"=="" set "Q=best"

echo.
echo 分P：1=只下第1P，all=全部
if "%~3"=="" (
  set /p "P=分P（直接回车只下第1P）： "
) else (
  set "P=%~3"
)
if "%P%"=="" set "P=1"

echo.
echo ---- 开始下载 ----
python "bili_dl.py" "%URL%" -q "%Q%" -p "%P%"
echo.
echo ---- 结束，产物在 downloads 目录 ----
pause >nul
'''

for name, text in (('启动.bat', START), ('命令行下载.bat', CLI)):
    p = os.path.join(D, name)
    with open(p, 'w', encoding='gbk', newline='\r\n') as f:
        f.write(text)
    raw = open(p, 'rb').read()
    crlf = raw.count(b'\r\n')
    lf_only = raw.count(b'\n') - crlf
    print(f'{name}: {len(raw)} bytes, CRLF={crlf}, bare-LF={lf_only}, head={raw[:9]!r}')
