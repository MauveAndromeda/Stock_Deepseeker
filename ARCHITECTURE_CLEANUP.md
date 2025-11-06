# Architecture Cleanup Plan

## Files to DELETE (Redundant/Empty)

### Main Entry Points (4 files - ALL EMPTY OR TODO)
- [ ] main.py (413 lines - multi-agent system, not integrated)
- [ ] main_upgraded.py (307 lines - ALL TODO, no implementation)
- [ ] elite_trading_system.py (1471 lines - duplicate system)
- [ ] ai_trading_complete_system.py (1323 lines - duplicate system)

### Duplicate Backtest Engines
- [ ] src/backtest/engine.py (OLD - replace with engine_v2.py)

### Old Module Directories
- [ ] agents/ (multi-agent system not integrated with backtest)
- [ ] utils/ (redundant with src/utils/)
- [ ] trading/ (redundant with src/execution/ and src/strategies/)
- [ ] data/ (redundant with src/data/)
- [ ] strategy/ (redundant with src/strategies/)

## Files to KEEP (Core Architecture)

### Core Backtest System
- ✅ src/backtest/engine_v2.py (event-driven, no lookahead)
- ✅ src/backtest/events.py
- ✅ src/backtest/execution.py
- ✅ src/backtest/portfolio_v2.py

### Data & Factors
- ✅ src/data/
- ✅ src/factors/

### Risk & Execution
- ✅ src/risk/
- ✅ src/execution/

### Strategies
- ✅ src/strategies/

### Monitoring & Analytics
- ✅ src/monitoring/
- ✅ src/analytics/

## New Structure

```
Stock_Deepseeker/
├── src/                    # Core library
│   ├── backtest/          # Backtest engine (engine_v2 only)
│   ├── data/              # Data providers
│   ├── factors/           # Factor library
│   ├── strategies/        # Strategy templates
│   ├── risk/              # Risk management
│   ├── execution/         # Order execution
│   ├── monitoring/        # System monitoring
│   └── analytics/         # Performance analytics
├── examples/              # Simple examples (NEW)
│   ├── basic_backtest.py
│   ├── factor_example.py
│   └── strategy_example.py
├── tests/                 # Real tests
├── docs/                  # Honest documentation
└── README.md              # Honest description
```

## Rationale

1. **Remove duplication** - Multiple main files doing different things
2. **Remove empty shells** - TODO functions that don't work
3. **Unify architecture** - One backtest engine (engine_v2)
4. **Clean separation** - src/ is library, examples/ for usage
5. **Honest documentation** - No false claims
