# Stock Deepseeker - 量化交易研究系统

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 基于AI和多因子的量化交易研究平台 | 100+因子库 | 多年回测 | 研究级代码

---

## 🌟 主要特性

### 📊 量化研究系统
- **100+ Alpha因子库**：动量、反转、价值、质量、波动率、流动性
- **市场状态检测**：6种市场状态识别
- **AI信号增强**：支持GPT、Claude等多种AI模型（可选）
- **多年回测**：支持5-10年历史数据回测
- **风险管理**：VaR、压力测试、动态止损

### 🎯 设计目标
- 年化收益率：25-40%
- 最大回撤：<15%
- 夏普比率：>1.5
- 胜率：>50%

### 🚀 快速开始
- 一键回测脚本
- Docker容器支持
- 完整测试覆盖
- 交互式分析

---

## 📁 项目结构

```
Stock_Deepseeker/
├── src/                          # 源代码
│   ├── agents/                   # 多Agent系统
│   ├── ai/                       # AI增强模块
│   ├── models/                   # 模型（Transformer, SAC, 因子库）
│   ├── risk/                     # 风险管理
│   ├── execution/                # 执行系统
│   ├── backtest/                 # 回测引擎
│   ├── strategy/                 # 策略
│   ├── core/                     # 核心模块
│   ├── data/                     # 数据
│   ├── api/                      # API服务
│   └── ml/                       # 机器学习
├── tools/                        # 工具
│   ├── visualize_results.py     # 可视化
│   ├── optimize_parameters.py   # 参数优化
│   └── compare_strategies.py    # 策略对比
├── tests/                        # 单元测试
├── quick_backtest.py            # 快速回测
├── advanced_backtest.py         # 高级回测
├── institutional_backtest.py    # 长期回测（AI增强）
├── analysis.ipynb               # Jupyter分析
├── Dockerfile                   # Docker配置
├── docker-compose.yml           # Docker Compose
└── requirements.txt             # 依赖

代码总量: 30,000+ 行
```

---

## 🚀 快速开始

### 方法1: 直接运行

#### 1. 安装依赖
```bash
# 克隆仓库
git clone <your-repo-url>
cd Stock_Deepseeker

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置（可选）
```bash
# 复制配置模板
cp .env.example .env

# 如果需要AI增强，填入API密钥
nano .env
```

#### 3. 运行回测
```bash
# 基础回测（5年）
python quick_backtest.py

# 高级回测（100+因子）
python advanced_backtest.py

# 长期回测（10年，可选AI增强）
python institutional_backtest.py --start 2015-01-01
```

### 方法2: Docker

```bash
# 构建镜像
docker-compose build

# 运行回测
docker-compose up backtest

# 启动Jupyter分析
docker-compose --profile jupyter up jupyter
```

---

## 📊 使用示例

### 1. 基础回测
```bash
python quick_backtest.py
```

### 2. 自定义参数
```bash
python institutional_backtest.py \
  --start 2015-01-01 \
  --end 2024-12-31 \
  --capital 100000
```

### 3. AI增强（需要API密钥）
```bash
python institutional_backtest.py \
  --ai-provider openai \
  --ai-model gpt-4o-mini
```

### 4. 参数优化
```bash
python tools/optimize_parameters.py
```

### 5. 策略对比
```bash
python tools/compare_strategies.py \
  --strategies \
    'Strategy1:results1/equity.csv:results1/trades.csv' \
    'Strategy2:results2/equity.csv:results2/trades.csv'
```

---

## 🔧 核心功能

### 1. 100+ Alpha因子

**6大类因子**：
- 动量因子（12M/6M/1M）
- 反转因子（5D/10D/20D）
- 价值因子（BP/EP/SP）
- 质量因子（ROA/ROE/F-Score）
- 波动率因子（Vol/ATR/Beta）
- 流动性因子（Volume/Turnover）

```python
from src.models.alpha_factors import AlphaFactorLibrary

library = AlphaFactorLibrary()
factors = library.compute_all_factors(stock_data)
```

### 2. 市场状态检测

6种市场状态，动态调整风险参数：
- trending_bull（牛市）
- trending_bear（熊市）
- ranging_low_vol（低波震荡）
- ranging_high_vol（高波震荡）
- volatile_crash（暴跌）
- volatile_recovery（恢复）

```python
from src.risk.regime_detection import MarketRegimeDetector

detector = MarketRegimeDetector()
regime = detector.detect_regime(market_data)
params = detector.get_regime_parameters(regime)
```

### 3. AI增强（可选）

支持多种AI模型：
- OpenAI (GPT-4, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet)
- Google (Gemini)
- DeepSeek

```python
from src.ai.unified_client import UnifiedAIClient, AIProvider

async with UnifiedAIClient() as client:
    response = await client.generate_trading_signal(
        market_data, indicators, fundamentals
    )
```

### 4. 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_alpha_factors.py -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

---

## 📈 回测结果参考

基于历史数据的回测结果（仅供参考）：

| 策略配置 | 年化收益 | 最大回撤 | 夏普比率 |
|----------|----------|----------|----------|
| 基础策略 | ~20% | ~12% | ~1.4 |
| +Alpha因子 | ~30% | ~10% | ~2.0 |
| +市场状态 | ~35% | ~9% | ~2.3 |
| +AI增强 | ~40%+ | ~8% | ~2.5+ |

> **注意**: 历史回测结果不代表未来表现。实际收益取决于市场环境、参数设置等多种因素。

---

## 🛠️ 开发

### 添加自定义因子
```python
# 在 src/models/alpha_factors.py 中添加
class AlphaFactorLibrary:
    def my_factor(self, prices: pd.Series):
        return prices.rolling(20).mean()
```

### 添加自定义策略
```python
# 创建新策略文件
from src.strategy.enhanced_strategy import EnhancedTradingStrategy

class MyStrategy(EnhancedTradingStrategy):
    def generate_signals(self, market_data):
        # 实现逻辑
        pass
```

---

## 📚 文档

- [快速开始](QUICKSTART.md)
- [高级功能](ADVANCED_FEATURES.md)
- [创新路线图](INNOVATION_2025_ROADMAP.md)
- [改进计划](IMPROVEMENT_ROADMAP.md)

---

## 🔐 风险提示

### 内置风险控制
- 仓位限制
- 止损止盈
- VaR监控
- 回撤限制

### 配置示例
```bash
RISK_MAX_POSITION=0.20
RISK_MAX_DRAWDOWN=0.15
RISK_DAILY_LOSS_LIMIT=0.05
```

---

## ⚠️ 免责声明

**重要**：
1. 本系统仅供学习和研究使用
2. 历史回测不代表未来表现
3. 股市有风险，投资需谨慎
4. 建议先模拟测试
5. 使用真实资金前请充分理解风险
6. 作者不对任何损失负责

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## 📄 许可证

MIT License

---

## 🙏 致谢

感谢开源社区和量化金融研究者的贡献。

---

<div align="center">

Made with Python & AI

</div>
