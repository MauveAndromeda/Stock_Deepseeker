# Stock Deepseeker - 机构级量化交易系统
# 基于Python 3.10，包含所有依赖

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p data logs backtest_results models institutional_results comparison_results

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露API端口（如果使用API模式）
EXPOSE 8000

# 默认命令：显示帮助信息
CMD ["python", "-c", "print('Stock Deepseeker - 机构级量化交易系统\\n\\n使用示例:\\n  快速回测: python quick_backtest.py\\n  高级回测: python advanced_backtest.py\\n  机构级回测: python institutional_backtest.py --start 2015-01-01\\n  参数优化: python tools/optimize_parameters.py\\n  策略对比: python tools/compare_strategies.py\\n\\n更多信息请查看 README.md')"]
