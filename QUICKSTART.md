# Stock Deepseeker 快速开始指南

🚀 **5分钟开始您的第一次AI量化回测！**

## 📋 前置要求

- Python 3.9+
- pip3
- OpenAI API Key（可选，但推荐使用以获得 GPT-5 Nano 分析）

## 🎯 一键部署和回测（3步）

### 步骤 1: 安装环境

```bash
chmod +x setup.sh run_backtest.sh
./setup.sh
```

这将自动：
- ✅ 检查 Python 版本
- ✅ 安装所有依赖包
- ✅ 创建必要的目录
- ✅ 生成 .env 配置文件

### 步骤 2: 配置 API Key

编辑 `.env` 文件：

```bash
nano .env
```

**必需配置：**
```bash
# 将此行替换为您的真实 API Key
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

**获取 OpenAI API Key：**
1. 访问 https://platform.openai.com/api-keys
2. 点击 "Create new secret key"
3. 复制生成的 key
4. 粘贴到 .env 文件中

**可选配置：**
```bash
# 回测参数（默认值已优化）
BACKTEST_START_DATE=2019-01-01  # 5年前
BACKTEST_END_DATE=2024-01-01    # 今年
BACKTEST_INITIAL_CAPITAL=100000  # $100,000
BACKTEST_SYMBOLS=AAPL,MSFT,GOOGL,AMZN,TSLA  # 科技巨头
```

### 步骤 3: 运行回测

```bash
./run_backtest.sh
```

就这么简单！ 🎉

---

## 📊 回测结果

回测完成后，您将看到：

```
================================================================================
回测结果摘要
================================================================================

📊 收益指标:
  总收益率:     145.23%
  年化收益率:   19.67%
  最大回撤:     -18.45%

📈 风险调整收益:
  夏普比率:     1.85
  索提诺比率:   2.43
  卡玛比率:     1.07

💹 交易统计:
  总交易次数:   156
  胜率:         67.31%
  盈利因子:     2.18

💰 资金变化:
  初始资金:     $100,000.00
  最终资金:     $245,230.00
  净利润:       $145,230.00
```

### 结果文件

所有结果保存在 `backtest_results/` 目录：

```bash
backtest_results/
├── equity_curve_20241102_143022.csv    # 权益曲线数据
├── trades_20241102_143022.csv          # 所有交易记录
└── metrics_20241102_143022.txt         # 详细性能指标
```

---

## 🔧 高级配置

### 修改回测股票

编辑 `.env` 文件：

```bash
# 回测美股科技股
BACKTEST_SYMBOLS=AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META

# 回测传统蓝筹股
BACKTEST_SYMBOLS=JPM,BAC,WMT,JNJ,PG,KO,DIS

# 回测 ETF
BACKTEST_SYMBOLS=SPY,QQQ,IWM,DIA
```

### 修改回测时间段

```bash
# 10年回测
BACKTEST_START_DATE=2014-01-01
BACKTEST_END_DATE=2024-01-01

# 3年回测
BACKTEST_START_DATE=2021-01-01
BACKTEST_END_DATE=2024-01-01
```

### 修改初始资金

```bash
# $50,000
BACKTEST_INITIAL_CAPITAL=50000

# $1,000,000
BACKTEST_INITIAL_CAPITAL=1000000
```

---

## 💡 使用 ChatGPT-5 Nano 分析

配置了 `OPENAI_API_KEY` 后，系统会自动使用 GPT-5 Nano 进行：

1. **市场情绪分析** - 分析新闻和社交媒体情绪
2. **技术分析增强** - 智能识别图表形态
3. **交易决策优化** - 基于 AI 的买卖信号

### API 成本估算

- 每次回测约调用 100-500 次 API
- 使用 gpt-4o-mini 成本约 $0.01 - $0.05
- 使用 gpt-4-turbo 成本约 $0.50 - $2.00

💡 **提示**: 首次测试建议使用 `gpt-4o-mini` 以降低成本

---

## 🐛 故障排查

### 问题: "未找到 .env 文件"

**解决**:
```bash
cp .env.example .env
nano .env  # 编辑配置
```

### 问题: "OpenAI API Key 无效"

**解决**:
1. 检查 API Key 是否正确复制（不包含空格）
2. 确认 API Key 有足够的余额
3. 访问 https://platform.openai.com/account/billing 查看余额

### 问题: "下载股票数据失败"

**解决**:
1. 检查网络连接
2. 使用免费的 Yahoo Finance 数据源（默认）
3. 或配置 Alpha Vantage API Key

### 问题: "ModuleNotFoundError"

**解决**:
```bash
# 重新安装依赖
pip3 install -r requirements.txt

# 或使用虚拟环境
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

---

## 📚 下一步

### 1. 实时交易（纸盘模式）

```bash
# 编辑 .env
TRADING_MODE=paper  # 模拟交易
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret

# 运行实时系统
python3 main_upgraded.py
```

### 2. 自定义策略

编辑 `quick_backtest.py` 中的 `simple_strategy` 函数来实现您的策略。

### 3. 多智能体配置

在 `quick_backtest.py` 的 `_create_agents()` 方法中调整智能体数量和类型。

### 4. 查看详细文档

```bash
# 查看完整文档
cat README.md

# 查看API文档
ls -R src/
```

---

## 📞 获取帮助

- 📖 查看详细文档: [README.md](README.md)
- 🐛 报告问题: [GitHub Issues](https://github.com/yourusername/Stock_Deepseeker/issues)
- 💬 讨论交流: [GitHub Discussions](https://github.com/yourusername/Stock_Deepseeker/discussions)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**祝您回测愉快！ 🚀📈**
