@echo off
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
