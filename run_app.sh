#!/bin/bash
# TAF Parse Web 应用启动脚本

echo "======================================"
echo "  TAF Parse - Web 测试界面"
echo "======================================"
echo ""

# 检查是否安装了依赖
if ! python -c "import streamlit" 2>/dev/null; then
    echo "正在安装依赖..."
    pip install -r requirements.txt
fi

echo "启动 Streamlit 应用..."
echo ""
echo "应用将在浏览器中打开"
echo "如果没有自动打开，请访问下方显示的 URL"
echo ""
echo "按 Ctrl+C 停止应用"
echo ""
echo "======================================"
echo ""

cd "$(dirname "$0")"
streamlit run app.py
