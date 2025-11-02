#!/bin/bash
# Stock Deepseeker 环境安装脚本

set -e  # 遇到错误立即退出

echo "========================================"
echo "Stock Deepseeker 环境安装"
echo "========================================"
echo ""

# 检查 Python 版本
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 版本过低！需要 Python 3.9+ ，当前版本: $python_version"
    exit 1
fi

echo "✓ Python 版本: $python_version"

# 检查 pip
echo ""
echo "检查 pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 未安装！请先安装 pip3"
    exit 1
fi
echo "✓ pip3 已安装"

# 创建虚拟环境（可选）
echo ""
read -p "是否创建虚拟环境？(推荐) [y/N]: " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "创建虚拟环境..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✓ 虚拟环境已创建"
    else
        echo "✓ 虚拟环境已存在"
    fi

    echo "激活虚拟环境..."
    source venv/bin/activate
    echo "✓ 虚拟环境已激活"
fi

# 升级 pip
echo ""
echo "升级 pip..."
pip3 install --upgrade pip

# 安装依赖
echo ""
echo "安装 Python 依赖包..."
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo "✓ 依赖包安装完成"
else
    echo "❌ 未找到 requirements.txt 文件！"
    exit 1
fi

# 创建必要的目录
echo ""
echo "创建必要的目录..."
mkdir -p data
mkdir -p logs
mkdir -p backtest_results
mkdir -p models
echo "✓ 目录创建完成"

# 复制环境变量配置文件
echo ""
if [ ! -f ".env" ]; then
    echo "创建环境变量配置文件..."
    cp .env.example .env
    echo "✓ .env 文件已创建"
    echo ""
    echo "⚠️  重要：请编辑 .env 文件并填写您的 API 密钥："
    echo "   - OPENAI_API_KEY (必需，用于 ChatGPT-5 Nano)"
    echo "   - ALPHA_VANTAGE_API_KEY (可选，用于获取股票数据)"
    echo ""
    echo "   编辑命令: nano .env  或  vim .env"
else
    echo "✓ .env 文件已存在"
fi

# 测试导入
echo ""
echo "测试 Python 模块导入..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from src.core.config import Config
    from src.data.providers import YahooFinanceProvider
    print('✓ 核心模块导入成功')
except Exception as e:
    print(f'❌ 模块导入失败: {e}')
    sys.exit(1)
"

echo ""
echo "========================================"
echo "✅ 安装完成！"
echo "========================================"
echo ""
echo "下一步："
echo "  1. 编辑 .env 文件并填写您的 OpenAI API Key"
echo "  2. 运行一键回测：./run_backtest.sh"
echo ""
echo "命令："
echo "  编辑配置: nano .env"
echo "  运行回测: ./run_backtest.sh"
echo "  手动回测: python3 quick_backtest.py"
echo ""

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "💡 提示: 下次使用前请先激活虚拟环境："
    echo "   source venv/bin/activate"
    echo ""
fi
