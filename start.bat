@echo off
chcp 65001 >nul
title A 股股东检索系统

echo ========================================
echo   A 股股东检索系统 - 启动中...
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python 检测通过

echo.
echo 正在安装/更新依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo ========================================
echo   服务启动成功！
echo   浏览器访问：http://127.0.0.1:5000
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

pause
