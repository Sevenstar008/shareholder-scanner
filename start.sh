#!/bin/bash

echo "========================================"
echo "  A 股股东检索系统 - 启动中..."
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未检测到 Python3，请先安装 Python 3.8+"
    exit 1
fi

echo "✅ Python 检测通过"
echo ""
echo "正在安装/更新依赖..."
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo ""
echo "========================================"
echo "  服务启动成功！"
echo "  浏览器访问：http://127.0.0.1:5000"
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

python3 app.py
