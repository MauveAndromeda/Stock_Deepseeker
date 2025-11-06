# Stock Deepseeker

A **research-grade** quantitative trading framework for backtesting and strategy development.

## ⚠️ Project Status: Under Development

This is an **active research project** focused on building a solid quantitative trading infrastructure. It is **NOT production-ready** and should **NOT be used for live trading** without substantial additional work.

### What This Project IS

- ✅ Event-driven backtest engine with no-lookahead bias enforcement
- ✅ 62+ quantitative factors across 6 categories
- ✅ Basic risk management modules (VaR, position limits, stop-loss)
- ✅ Multiple strategy templates
- ✅ Data providers (Yahoo Finance, Alpha Vantage)
- ✅ Performance analytics and reporting

### What This Project IS NOT

- ❌ Production trading system
- ❌ "Institutional-grade" or "Enterprise-level"
- ❌ Fully tested and validated
- ❌ Ready for live trading
- ❌ Complete or feature-complete

## Project Structure

```
Stock_Deepseeker/
├── src/                    # Core library
│   ├── backtest/          # Event-driven backtest engine
│   ├── data/              # Data providers and loaders
│   ├── factors/           # Quantitative factor library (62+ factors)
│   ├── strategies/        # Strategy templates
│   ├── risk/              # Risk management modules
│   ├── execution/         # Order execution simulation
│   ├── monitoring/        # System monitoring
│   └── analytics/         # Performance analytics
├── examples/              # Usage examples (educational)
├── tests/                 # Test suite (partial coverage)
└── docs/                  # Documentation
```

## Core Components

### Backtest Engine

Event-driven architecture designed to prevent lookahead bias:

- `engine_v2.py`: Main backtest engine with strict time-ordering
- `events.py`: Event system (Market, Signal, Order, Fill)
- `portfolio_v2.py`: Portfolio tracking and management
- `execution.py`: Order execution simulation

### Factor Library

62+ quantitative factors across:
- Momentum (13 factors)
- Value (14 factors)
- Quality (13 factors)
- Volatility (12 factors)
- Growth (10 factors)
- Liquidity (11 factors)

### Strategy Templates

- Momentum
- Mean Reversion
- Pairs Trading
- Value Investing
- Multi-Factor
- Volatility Arbitrage
- Sector Rotation
- Breakout
- Trend Following
- Market Neutral

## Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/Stock_Deepseeker.git
cd Stock_Deepseeker

# Install dependencies
pip install -e .

# Optional: Install development dependencies
pip install -e ".[dev]"
```

## Quick Start

### 一键回测（推荐）

最简单的方式 - 使用完整的回测脚本：

```bash
# 使用模拟数据运行回测（用于演示）
python run_backtest.py --mock

# 使用真实数据（需要网络连接）
python run_backtest.py --symbols AAPL

# 自定义参数
python run_backtest.py --symbols AAPL MSFT --start 2023-01-01 --capital 50000 --mock

# 查看所有选项
python run_backtest.py --help
```

**特性：**
- ✅ 完整的端到端回测示例
- ✅ 使用真实的 Yahoo Finance 数据或模拟数据
- ✅ 双均线交叉策略（可定制参数）
- ✅ 详细的回测结果报告
- ✅ 100% 可运行，无需额外配置

### 示例代码

查看 `examples/` 目录了解更多用法：

```bash
python examples/basic_backtest.py
```

**注意:** 示例代码是教学性骨架，`run_backtest.py` 是完整实现。

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

**Current test status:**
- 191 tests collected (imports work)
- Partial test coverage
- Some tests are templates/incomplete

## Development Roadmap

### Phase 1: Core Stability (Current)
- [x] Clean up architecture
- [x] Remove duplicate code
- [ ] Complete test coverage for core modules
- [ ] Validate no-lookahead enforcement
- [ ] Document actual capabilities

### Phase 2: Data Pipeline
- [ ] Robust data ingestion
- [ ] Corporate actions handling
- [ ] Survivorship bias elimination
- [ ] Data quality checks

### Phase 3: Risk Integration
- [ ] Connect risk modules to backtest
- [ ] Real-time risk monitoring
- [ ] Position sizing
- [ ] Portfolio constraints

### Phase 4: Strategy Framework
- [ ] Standardized strategy interface
- [ ] Factor integration
- [ ] Signal generation
- [ ] Portfolio optimization

### Phase 5: Production Prep (Future)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Broker integrations
- [ ] Live trading capabilities

## Known Issues

1. **Test Coverage**: Many tests are incomplete or template-based
2. **Integration**: Components not fully integrated (data → strategy → backtest → risk)
3. **Documentation**: Some docs describe planned, not actual features
4. **Performance**: Not optimized for large-scale backtesting

## Contributing

This is a research project. Contributions welcome, but please:
1. Write tests for new features
2. Update documentation to reflect **actual** capabilities
3. Follow existing code style
4. Be honest about limitations

## Disclaimer

This software is for **educational and research purposes only**.

- **NOT** financial advice
- **NOT** production-ready
- **NOT** guaranteed to be correct
- **NO** warranty of any kind

Use at your own risk. Past performance does not predict future results.

## License

[Your License Here]

## Contact

[Your Contact Info]

---

**Built with honesty in mind** 🎯
