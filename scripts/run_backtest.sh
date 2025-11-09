#!/bin/bash
# Stock Deepseeker 一键回测脚本
# 运行 5 年历史数据回测

set -e  # 遇到错误立即退出

echo "========================================"
echo "Stock Deepseeker - 5年回测"
echo "========================================"
echo ""

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
    echo "✓ 虚拟环境已激活"
    echo ""
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 未找到 .env 文件！"
    echo "请先运行: ./setup.sh"
    exit 1
fi

# 检查 OpenAI API Key
if grep -q "your_gpt5_nano_api_key_here" .env; then
    echo "⚠️  警告: 检测到默认的 OpenAI API Key"
    echo ""
    echo "为了获得最佳体验，请配置您的 OpenAI API Key："
    echo "  1. 访问 https://platform.openai.com/api-keys"
    echo "  2. 创建或复制您的 API Key"
    echo "  3. 编辑 .env 文件: nano .env"
    echo "  4. 替换 OPENAI_API_KEY 的值"
    echo ""
    read -p "是否继续不使用 GPT-5 分析？[y/N]: " continue_without_gpt
    if [[ ! $continue_without_gpt =~ ^[Yy]$ ]]; then
        echo "已取消。请配置 API Key 后重新运行。"
        exit 0
    fi
    echo ""
fi

# 检查依赖
echo "检查依赖..."
python3 -c "
import sys
try:
    import pandas
    import numpy
    import yfinance
    import torch
    print('✓ 所有依赖已安装')
except ImportError as e:
    print(f'❌ 缺少依赖: {e}')
    print('请运行: pip3 install -r requirements.txt')
    sys.exit(1)
" || exit 1
echo ""

# 显示配置
echo "回测配置:"
echo "----------------------------------------"
source .env 2>/dev/null || true
echo "  起始日期: ${BACKTEST_START_DATE:-2019-01-01}"
echo "  结束日期: ${BACKTEST_END_DATE:-2024-01-01}"
echo "  初始资金: \$${BACKTEST_INITIAL_CAPITAL:-100000}"
echo "  回测股票: ${BACKTEST_SYMBOLS:-AAPL,MSFT,GOOGL,AMZN,TSLA}"
echo "----------------------------------------"
echo ""

# 运行回测
echo "开始运行回测..."
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

# 记录开始时间
start_time=$(date +%s)

# 运行 Python 脚本
python3 quick_backtest.py

# 计算耗时
end_time=$(date +%s)
duration=$((end_time - start_time))
minutes=$((duration / 60))
seconds=$((duration % 60))

echo ""
echo "========================================"
echo "✅ 回测完成！"
echo "========================================"
echo "耗时: ${minutes}分${seconds}秒"
echo ""
echo "📊 回测结果已保存至 backtest_results/ 目录"
echo ""
echo "下一步:"
echo "  查看结果: ls -lh backtest_results/"
echo "  查看图表: cat backtest_results/metrics_*.txt"
echo ""
