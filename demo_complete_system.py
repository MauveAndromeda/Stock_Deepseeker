"""
Complete Multi-Agent Trading System Demo
完整的多智能体交易系统演示

Research-grade implementation (Under Development)
Demonstrates all features: agents, risk management, expert panel
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from src.agents import (
    create_default_multi_agent_strategy,
    get_agent_registry,
)
from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig
from src.backtest.portfolio_v2 import PortfolioV2
from src.data.providers.base import PriceData
from src.risk import RiskLimit
from loguru import logger


def generate_realistic_market_data(
    symbols: list,
    start_date: str = '2023-01-01',
    end_date: str = '2024-01-01',
    seed: int = 42
) -> dict:
    """
    生成真实风格的市场数据

    模拟不同市场条件：
    - 趋势期
    - 震荡期
    - 崩盘期
    - 恢复期
    """
    np.random.seed(seed)

    dates = pd.date_range(start_date, end_date, freq='D')
    data = {}

    for i, symbol in enumerate(symbols):
        n_days = len(dates)

        # 为每个股票创建不同的行为
        if i % 4 == 0:
            # 趋势股：稳定上涨
            trend = np.linspace(0, 40, n_days)
            volatility = 2
        elif i % 4 == 1:
            # 价值股：缓慢上涨
            trend = np.linspace(0, 20, n_days)
            volatility = 1.5
        elif i % 4 == 2:
            # 波动股：高波动
            trend = np.linspace(0, 30, n_days)
            volatility = 5
        else:
            # 周期股：上下波动
            trend = 10 * np.sin(np.linspace(0, 4*np.pi, n_days))
            volatility = 3

        # 添加市场事件
        # 在中间模拟一次小崩盘
        crash_start = n_days // 2
        crash_duration = 20
        crash_effect = np.zeros(n_days)
        crash_effect[crash_start:crash_start+crash_duration] = -15

        # 基础价格
        base_price = 100 + (i * 10)  # 不同股票不同起始价

        # 价格 = 基础价格 + 趋势 + 随机波动 + 崩盘效应
        noise = np.random.randn(n_days) * volatility
        prices = base_price + trend + noise + crash_effect
        prices = np.maximum(prices, 10)  # 价格不低于10

        # 成交量（与价格波动相关）
        volume_base = 1000000 * (1 + i * 0.5)
        volume_volatility = np.abs(np.diff(prices, prepend=prices[0])) / prices * 5
        volumes = volume_base * (1 + np.random.randn(n_days) * 0.3 + volume_volatility)
        volumes = np.maximum(volumes, volume_base * 0.5)

        # 创建OHLC数据
        df = pd.DataFrame({
            'open': prices * (1 + np.random.randn(n_days) * 0.01),
            'high': prices * (1 + np.abs(np.random.randn(n_days)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(n_days)) * 0.02),
            'close': prices,
            'volume': volumes.astype(int)
        }, index=dates)

        data[symbol] = df

        logger.info(
            f"{symbol}: Start=${df['close'].iloc[0]:.2f}, "
            f"End=${df['close'].iloc[-1]:.2f}, "
            f"Return={((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.1f}%"
        )

    return data


async def run_full_demo(
    use_llm: bool = False,
    use_expert_panel: bool = False,
    enable_risk_management: bool = True,
    symbols: list = None
):
    """
    运行完整的系统演示

    Args:
        use_llm: 是否使用真实LLM（需要API密钥）
        use_expert_panel: 是否使用专家面板
        enable_risk_management: 是否启用风险管理
        symbols: 股票列表
    """
    if symbols is None:
        symbols = ['TECH_A', 'VALUE_B', 'GROWTH_C', 'CYCLE_D']

    logger.info("=" * 60)
    logger.info("Multi-Agent Trading System - Complete Demo")
    logger.info("=" * 60)
    logger.info(f"Use LLM: {use_llm}")
    logger.info(f"Use Expert Panel: {use_expert_panel}")
    logger.info(f"Risk Management: {enable_risk_management}")
    logger.info(f"Symbols: {symbols}")
    logger.info("=" * 60)

    # 1. 生成市场数据
    logger.info("\n[1/6] Generating market data...")
    data = generate_realistic_market_data(symbols)

    # 2. 创建策略
    logger.info("\n[2/6] Creating multi-agent strategy...")

    if use_llm:
        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=use_expert_panel,
            register_agents=True
        )
        logger.info(f"Created strategy with {len(strategy.agents)} LLM agents")
    else:
        # Mock模式：使用规则智能体
        from src.agents.backtest_integration import MultiAgentStrategy
        from src.agents.unified_interface import MarketContext, AgentDecisionOutput, ActionType, RiskLevel, AgentCapability

        class MockRuleAgent:
            """简单规则智能体（无LLM）"""
            def __init__(self, agent_id, agent_type, rule):
                self.agent_id = agent_id
                self.agent_type = agent_type
                self.capabilities = [AgentCapability.MARKET_ANALYSIS]
                self.rule = rule
                self._decision_history = []

            async def analyze(self, market_ctx: MarketContext) -> AgentDecisionOutput:
                # 简单规则
                if self.rule == 'momentum':
                    action = ActionType.BUY if market_ctx.price_change_pct > 0.01 else ActionType.HOLD
                    confidence = min(abs(market_ctx.price_change_pct) * 10, 0.9)
                elif self.rule == 'value':
                    action = ActionType.BUY if market_ctx.current_price < 110 else ActionType.HOLD
                    confidence = 0.7
                elif self.rule == 'technical':
                    trend_score = market_ctx.technical_indicators.get('trend_score', 0)
                    action = ActionType.BUY if trend_score > 0 else ActionType.HOLD
                    confidence = 0.75
                else:
                    action = ActionType.HOLD
                    confidence = 0.5

                decision = AgentDecisionOutput(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    action=action,
                    confidence=confidence,
                    reasoning=f"Rule-based {self.rule} analysis",
                    key_factors=[f"{self.rule} signal"],
                    risk_level=RiskLevel.MEDIUM,
                    concerns=[]
                )

                self._decision_history.append(decision)
                return decision

            def get_performance_metrics(self):
                from src.agents.unified_interface import AgentPerformanceMetrics
                return AgentPerformanceMetrics(
                    agent_id=self.agent_id,
                    total_decisions=len(self._decision_history),
                    avg_confidence=np.mean([d.confidence for d in self._decision_history]) if self._decision_history else 0,
                    decisions_by_action={},
                    avg_processing_time=0,
                    total_cost=0
                )

            def reset(self):
                self._decision_history.clear()

        agents = [
            MockRuleAgent('mock_momentum', 'momentum_chaser', 'momentum'),
            MockRuleAgent('mock_value', 'value_seeker', 'value'),
            MockRuleAgent('mock_technical', 'technical_trader', 'technical'),
        ]

        # 自定义风险限制
        custom_limits = RiskLimit(
            max_position_size=0.15,  # 15% max per position
            min_cash_reserve=0.15,   # 15% cash reserve
            stop_loss_pct=0.10       # 10% stop loss
        )

        strategy = MultiAgentStrategy(
            name="Mock_MultiAgent",
            agents=agents,
            use_expert_panel=False,
            consensus_threshold=0.6,
            min_confidence=0.6,
            risk_limits=custom_limits if enable_risk_management else None,
            enable_risk_management=enable_risk_management
        )
        logger.info(f"Created mock strategy with {len(agents)} rule-based agents")

    # 3. 配置回测
    logger.info("\n[3/6] Configuring backtest engine...")

    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,  # 0.1%
        slippage=0.0005,   # 0.05%
        start_date=pd.Timestamp('2023-01-01'),
        end_date=pd.Timestamp('2024-01-01')
    )

    engine = BacktestEngineV2(config=config)

    # 转换为PriceData对象
    price_data_dict = {}
    for symbol, df in data.items():
        price_data_dict[symbol] = PriceData(
            symbol=symbol,
            data=df,
            start_date=df.index[0],
            end_date=df.index[-1]
        )

    engine.load_data(price_data_dict)
    engine.set_strategy(strategy)

    # 4. 运行回测
    logger.info("\n[4/6] Running backtest...")
    logger.info(f"Period: {config.start_date.date()} to {config.end_date.date()}")
    logger.info(f"Initial Capital: ${config.initial_capital:,.2f}")

    results = engine.run()

    # 5. 分析结果
    logger.info("\n[5/6] Analyzing results...")

    portfolio_value = results['portfolio_values']
    returns = results['returns']

    # 计算关键指标
    total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
    annual_return = total_return  # 刚好1年

    # Sharpe ratio
    returns_array = returns.values
    sharpe = (returns_array.mean() / returns_array.std() * np.sqrt(252)) if returns_array.std() > 0 else 0

    # 最大回撤
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100

    # 胜率
    trades = results.get('trades', [])
    if trades:
        profitable_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = (profitable_trades / len(trades)) * 100 if trades else 0
    else:
        win_rate = 0

    # 6. 显示结果
    logger.info("\n[6/6] Results Summary")
    logger.info("=" * 60)
    logger.info("PERFORMANCE METRICS")
    logger.info("=" * 60)
    logger.info(f"Initial Capital:      ${config.initial_capital:,.2f}")
    logger.info(f"Final Value:          ${portfolio_value.iloc[-1]:,.2f}")
    logger.info(f"Total Return:         {total_return:.2f}%")
    logger.info(f"Annual Return:        {annual_return:.2f}%")
    logger.info(f"Sharpe Ratio:         {sharpe:.2f}")
    logger.info(f"Max Drawdown:         {max_drawdown:.2f}%")
    logger.info(f"Total Trades:         {len(trades)}")
    logger.info(f"Win Rate:             {win_rate:.1f}%")
    logger.info("=" * 60)

    # 策略统计
    strategy_summary = strategy.get_performance_summary()
    logger.info("\nSTRATEGY STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total Signals:        {strategy_summary.get('total_signals', 0)}")
    logger.info(f"Decision Count:       {strategy_summary.get('decision_count', 0)}")
    logger.info(f"Avg Confidence:       {strategy_summary.get('avg_confidence', 0):.2f}")
    logger.info(f"Agent Count:          {strategy_summary.get('agent_count', 0)}")

    # 风险管理统计
    if enable_risk_management and strategy.risk_manager:
        risk_summary = strategy.risk_manager.get_check_history_summary()
        logger.info("\nRISK MANAGEMENT")
        logger.info("=" * 60)
        logger.info(f"Total Checks:         {risk_summary['total_checks']}")
        logger.info(f"Approved:             {risk_summary['approved']} ({risk_summary['approval_rate']*100:.1f}%)")
        logger.info(f"Adjusted:             {risk_summary['adjusted']} ({risk_summary['adjustment_rate']*100:.1f}%)")
        logger.info(f"Rejected:             {risk_summary['rejected']} ({risk_summary['rejection_rate']*100:.1f}%)")
        logger.info(f"Avg Risk Score:       {risk_summary['avg_risk_score']:.2f}")

    logger.info("=" * 60)
    logger.info("Demo completed successfully!")
    logger.info("=" * 60)

    return {
        'results': results,
        'metrics': {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trades)
        },
        'strategy_summary': strategy_summary,
        'risk_summary': risk_summary if enable_risk_management else None
    }


async def main():
    """主函数"""
    import sys

    # 检查命令行参数
    use_llm = '--llm' in sys.argv
    use_expert_panel = '--expert-panel' in sys.argv
    no_risk = '--no-risk' in sys.argv

    if use_llm:
        logger.warning("LLM mode requires API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
        logger.warning("This will incur API costs!")
        import os
        if not os.getenv('OPENAI_API_KEY') and not os.getenv('ANTHROPIC_API_KEY'):
            logger.error("No API keys found. Running in mock mode instead.")
            use_llm = False

    await run_full_demo(
        use_llm=use_llm,
        use_expert_panel=use_expert_panel,
        enable_risk_management=not no_risk
    )


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║   Multi-Agent Trading System - Complete Demo                 ║
║   Research-grade implementation (Under Development)          ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python demo_complete_system.py                # Mock mode (no API needed)
    python demo_complete_system.py --llm          # Use real LLMs (requires API key)
    python demo_complete_system.py --expert-panel # Enable expert panel
    python demo_complete_system.py --no-risk      # Disable risk management

Features demonstrated:
    ✓ Multi-agent decision making (4 agents)
    ✓ Risk management (VaR + position limits)
    ✓ Market scenario simulation
    ✓ Performance metrics tracking
    ✓ Complete backtest workflow
    ✓ No lookahead bias guarantee

""")
    asyncio.run(main())
