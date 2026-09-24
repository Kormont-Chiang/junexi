@echo off
chcp 65001 >nul
title 六月息
cd /d "%~dp0"
echo 正在启动六月息…
venv\Scripts\python.exe desktop.py
if errorlevel 1 (
    echo.
    echo 启动失败，请把 desktop.log 的内容发给 Auto-Korm
    pause
)
