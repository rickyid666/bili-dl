@echo off
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
