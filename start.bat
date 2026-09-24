@echo off
chcp 65001 >nul
title 六月息 · 后端服务
echo ========================================
echo  六月息 · 历史学学术面板
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查依赖
echo [1/3] 检查依赖...
if not exist venv (
    echo 创建虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q -r requirements.txt

:: 检查 Obsidian Local REST API
echo [2/3] 检查 Obsidian Local REST API...
echo     请确保已在 Obsidian 中安装并启用 "Local REST API" 插件
echo     插件设置中记下 API Key，并设置端口为 27123
echo.

:: 启动服务
echo [3/3] 启动 Flask 服务...
echo.
echo ========================================
echo  访问地址: http://127.0.0.1:5000
echo ========================================
echo.

python app.py

pause
