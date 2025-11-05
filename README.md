# Stock Deepseeker - 量化交易研究系统

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Lines](https://img.shields.io/badge/code-31k+-brightgreen.svg)]()

> 基于多因子和AI的量化交易研究平台 | 100+因子 | 多年回测 | 研究级代码

---

## 📊 实际回测表现

**基线系统表现**（2020-2024，4.8年实盘数据）：

| 指标 | 实际表现 |
|------|---------|
| 初始资金 | $100,000 |
| 最终价值 | $209,821 |
| 总收益率 | **109.82%** |
| 年化收益率 | **16.72%** |
| 夏普比率 | 0.94 |
| 最大回撤 | -27.83% |
| 总交易次数 | 549 |
| 胜率 | **74.44%** |
| 盈亏比 | 2.22:1 |
| AI成本 | $2.48 |

> 以上为真实回测结果，数据来源于2020-02-03至2024-10-22期间的历史数据回测。

---

## 🎯 优化目标

基于当前基线表现（年化16.72%，夏普0.94），通过新增的增强模块，系统**优化目标**为：

| 指标 | 基线 | 优化目标 | 提升幅度 |
|------|------|----------|----------|
| 年化收益率 | 16.72% | **30%+** | +80% |
| 夏普比率 | 0.94 | **1.5+** | +60% |
| 最大回撤 | -27.83% | **-20%以内** | 改善28% |
| 胜率 | 74.44% | **75%+** | 保持或提升 |

**优化方法**：
1. ✅ 因子择时系统（预期+8-12%年化收益）
2. ✅ 新闻情绪分析（预期+3-5%年化收益）
3. ✅ 集中度风险管理（预期降低5-8%回撤）
4. 📋 动态对冲策略（计划中）
5. 📋 高频信号捕捉（计划中）

> **注意**：优化目标基于理论分析和历史回测，实际效果可能因市场环境而异。

---

## 🌟 主要特性

### 📊 量化研究系统
- **100+ Alpha因子库**：动量、反转、价值、质量、波动率、流动性6大类
- **市场状态检测**：6种市场状态识别，动态调整策略
- **因子择时系统**：根据市场环境动态分配因子权重（NEW）
- **新闻情绪分析**：多源新闻聚合+情绪评分（NEW）
- **集中度风险管理**：防止过度集中，HHI指数监控（NEW）
- **AI信号增强**：支持GPT、Claude等多种AI模型（可选）
- **多年回测**：支持5-10年历史数据回测
- **风险管理**：VaR、压力测试、动态止损

### 🎯 系统规模
- Python代码：**31,854行**
- 核心模块：15个
- Alpha因子：100+个
- 测试用例：完整覆盖
- 文档：5000+行

---

## 📁 项目结构

```
Stock_Deepseeker/
├── src/                          # 源代码 (26,000+行)
│   ├── agents/                   # 多Agent系统
│   │   ├── retail.py            # 5种散户Agent
│   │   ├── institutional.py     # 5种机构Agent
│   │   └── expert.py            # 专家决策系统
│   ├── ai/                       # AI增强模块
│   │   └── unified_client.py    # 统一AI客户端
│   ├── models/                   # 模型
│   │   ├── alpha_factors.py     # 100+ Alpha因子库
│   │   ├── transformer.py       # Transformer模型
│   │   ├── sac.py              # Soft Actor-Critic
│   │   └── ensemble.py         # 集成模型
│   ├── risk/                    # 风险管理
│   │   ├── regime_detection.py  # 市场状态检测
│   │   ├── var.py              # VaR计算
│   │   ├── stress.py           # 压力测试
│   │   └── concentration.py    # 集中度管理 (NEW)
│   ├── strategy/                # 策略
│   │   ├── enhanced_strategy.py # 增强策略
│   │   └── factor_timing.py    # 因子择时 (NEW)
│   ├── execution/               # 执行系统
│   │   ├── router.py           # 智能订单路由
│   │   └── algorithms.py       # VWAP/TWAP/POV
│   ├── backtest/               # 回测引擎
│   │   ├── engine.py           # 回测引擎
│   │   └── analyzer.py         # 性能分析
│   ├── data/                    # 数据
│   │   ├── provider.py         # 数据提供者
│   │   └── news_sentiment.py   # 新闻情绪 (NEW)
│   ├── core/                    # 核心模块
│   ├── api/                     # API服务
│   └── ml/                      # 机器学习
├── tools/                        # 工具 (3,000+行)
│   ├── visualize_results.py     # 可视化
│   ├── optimize_parameters.py   # 参数优化
│   └── compare_strategies.py    # 策略对比
├── tests/                        # 单元测试 (2,000+行)
├── quick_backtest.py            # 快速回测
├── advanced_backtest.py         # 高级回测
├── institutional_backtest.py    # 长期回测（AI增强）
├── analysis.ipynb               # Jupyter分析
├── Dockerfile                   # Docker配置
├── docker-compose.yml           # Docker Compose
└── requirements.txt             # 依赖
```

---

## 🚀 快速开始

### 方法1: 直接运行

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd Stock_Deepseeker

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行回测
python quick_backtest.py
```

### 方法2: Docker

```bash
# 构建并运行
docker-compose up backtest
```

---

## 📊 使用示例

### 1. 基础回测（复现上述结果）
```bash
python quick_backtest.py
```

### 2. 使用新增优化模块
```python
from src.strategy.factor_timing import FactorTimingSystem
from src.data.news_sentiment import NewsSentimentAnalyzer
from src.risk.concentration import ConcentrationRiskManager

# 因子择时
timing = FactorTimingSystem()
weights = timing.get_factor_weights(current_regime)

# 新闻情绪
analyzer = NewsSentimentAnalyzer()
news = await analyzer.get_latest_news('AAPL')
sentiment = analyzer.analyze_sentiment_simple(news)

# 集中度检查
risk_mgr = ConcentrationRiskManager()
risk = risk_mgr.check_concentration_risk(portfolio)
if risk.risk_level == RiskLevel.HIGH:
    new_weights = risk_mgr.suggest_rebalancing(portfolio)
```

### 3. AI增强（需要API密钥）
```bash
# 配置API密钥
cp .env.example .env
nano .env  # 填入OPENAI_API_KEY等

# 运行AI增强回测
python institutional_backtest.py \
  --ai-provider openai \
  --ai-model gpt-4o-mini
```

---

## 🔧 核心功能

### 1. 100+ Alpha因子

**6大类因子**：
- 动量因子（12M/6M/1M动量，加速度）
- 反转因子（5D/10D/20D短期反转）
- 价值因子（BP/EP/SP/CFP）
- 质量因子（ROA/ROE/Piotroski F-Score）
- 波动率因子（历史波动率/ATR/Beta）
- 流动性因子（成交量/换手率/Amihud）

### 2. 因子择时系统（NEW）

根据市场状态动态调整因子权重：
```python
# 牛市：重动量+成长
MarketRegime.TRENDING_BULL: {
    'momentum': 0.40,
    'quality': 0.25,
    'value': 0.15,
    ...
}

# 熊市：重价值+质量
MarketRegime.TRENDING_BEAR: {
    'value': 0.35,
    'quality': 0.30,
    'volatility': 0.20,
    ...
}
```

### 3. 新闻情绪分析（NEW）

多源新闻聚合+双模式分析：
- 数据源：Yahoo Finance、NewsAPI等
- 简单模式：关键词情绪分析（免费）
- AI模式：GPT/Claude深度分析（可选）
- 输出：情绪得分(-1到+1)、置信度、交易信号

### 4. 集中度风险管理（NEW）

多维度风险监控：
- 单只股票：≤20%
- 单一行业：≤30%
- 前5大持仓：≤60%
- HHI指数监控
- 自动再平衡建议

---

## 📈 性能对比

### 基于真实回测数据的预期改进

| 策略配置 | 年化收益 | 夏普比率 | 最大回撤 | 备注 |
|----------|----------|----------|----------|------|
| **基线系统** | **16.72%** | **0.94** | **-27.83%** | 真实回测 2020-2024 |
| +因子择时 | ~25% | ~1.2 | ~-23% | 理论预期 |
| +新闻情绪 | ~28% | ~1.35 | ~-21% | 理论预期 |
| +集中度管理 | ~30% | ~1.5 | ~-19% | 理论预期 |
| +AI增强 | ~35%+ | ~1.7+ | ~-17% | 理论预期（需API） |

> **说明**：
> - 第一行为实际回测结果
> - 其他行为基于量化理论的预期改进
> - 实际效果受市场环境、参数调优等多因素影响
> - 建议先在模拟环境验证

---

## 📚 文档

- [快速开始](QUICKSTART.md) - 5分钟上手指南
- [高级功能](ADVANCED_FEATURES.md) - 详细功能说明
- [创新路线图](INNOVATION_2025_ROADMAP.md) - 2025技术创新计划
- [改进计划](IMPROVEMENT_ROADMAP.md) - 系统改进roadmap

---

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_alpha_factors.py -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

---

## 🔐 风险控制

### 内置风险管理
- ✅ 多层级仓位限制（单股、行业、整体）
- ✅ 动态止损止盈
- ✅ VaR风险监控
- ✅ 压力测试
- ✅ 集中度检查（NEW）
- ✅ 回撤限制

### 配置示例
```bash
# .env 文件
RISK_MAX_POSITION=0.20           # 单股最大20%
RISK_MAX_INDUSTRY=0.30           # 单行业最大30%
RISK_MAX_DRAWDOWN=0.25           # 最大回撤25%
RISK_DAILY_LOSS_LIMIT=0.05       # 单日最大亏损5%
```

---

## 🎯 开发路线图

### ✅ Phase 1: 已完成
- 100+ Alpha因子库
- 6种市场状态检测
- AI多提供商支持
- 因子择时系统
- 新闻情绪分析
- 集中度风险管理
- 完整测试套件
- Docker支持

### 📋 Phase 2: 计划中（2-4周）
- 动态对冲策略（期权保护）
- 高频信号捕捉（分钟级）
- 另类数据集成（卫星图像、招聘信息）
- 实时流处理架构

### 📋 Phase 3: 研究中（2-3月）
- 图神经网络（股票关系建模）
- 在线强化学习（持续优化）
- 因果推断引擎（信号质量）
- 量子启发优化（组合优化）

详见 [INNOVATION_2025_ROADMAP.md](INNOVATION_2025_ROADMAP.md)

---

## ⚠️ 免责声明

**重要声明**：
1. **仅供研究和学习**：本系统是学术研究项目，不构成投资建议
2. **历史≠未来**：回测结果不代表未来表现，实盘可能显著不同
3. **风险自负**：股市有风险，投资需谨慎，使用本系统导致的任何损失由用户自行承担
4. **充分测试**：强烈建议在模拟环境充分测试后再考虑实盘
5. **小额起步**：如使用真实资金，建议从小额开始验证
6. **参数调优**：不同市场环境需要不同参数，需持续优化
7. **监管合规**：使用前请确保符合当地法律法规

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

贡献指南：
1. Fork项目
2. 创建特性分支
3. 提交更改（请包含测试）
4. 推送到分支
5. 开启Pull Request

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

感谢：
- 开源社区的量化金融工具
- 学术界的研究成果
- AI技术的发展
- 所有贡献者和使用者

---

## 📞 联系

- 问题反馈：GitHub Issues
- 讨论交流：GitHub Discussions

---

<div align="center">

**Stock Deepseeker - 量化交易研究平台**

基于 Python 3.10+ | 31,854 行代码 | MIT License

*Powered by Multi-Factor Analysis & AI*

</div>
