#!/usr/bin/env python3
"""
Multi-Agent Backtest Demo
演示多智能体系统与回测引擎的集成

Research-grade implementation (Under Development)
Not ready for production use

Usage:
    python run_multi_agent_backtest.py --mock  # 使用模拟数据（无需API密钥）
    python run_multi_agent_backtest.py --use-llm  # 使用LLM（需要API密钥）
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig
from src.agents.backtest_integration import create_default_multi_agent_strategy, MultiAgentStrategy
from src.data.providers.base import PriceData
from src.agents.enhanced_base import MomentumChaserAgent, ValueSeekerAgent, TechnicalTraderAgent
from src.agents.base import AgentType
from src.ai.model_unified import ModelTier
from loguru import logger


def generate_mock_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    initial_price: float = 100.0
) -> PriceData:
    """生成模拟数据"""
    dates = pd.bdate_range(start=start_date, end=end_date)
    np.random.seed(hash(symbol) % 2**32)
    returns = np.random.randn(len(dates)) * 0.02 + 0.0003
    prices = initial_price * (1 + returns).cumprod()

    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(len(dates))) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(len(dates))) * 0.01),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, len(dates)),
    }, index=dates)

    df['high'] = df[['high', 'close', 'open']].max(axis=1)
    df['low'] = df[['low', 'close', 'open']].min(axis=1)

    return PriceData(
        symbol=symbol,
        data=df,
        start_date=dates[0].to_pydatetime(),
        end_date=dates[-1].to_pydatetime(),
        adjusted=True,
        metadata={'source': 'mock'}
    )


async def create_multi_agent_strategy_mock() -> MultiAgentStrategy:
    """
    创建模拟的多智能体策略（不使用LLM）
    用于演示和测试
    """
    from src.backtest.events import SignalEvent
    from src.backtest.portfolio_v2 import PortfolioV2

    class MockAgent:
        """模拟智能体（不调用LLM）"""
        def __init__(self, agent_id, agent_type, bias):
            self.agent_id = agent_id
            self.agent_type = agent_type
            self.bias = bias  # 'bullish', 'bearish', 'neutral'

        async def analyze(self, market_data):
            from src.agents.base import AgentDecision, Action

            # 简单的启发式决策
            price_change = market_data.get('change_pct', 0)

            if self.bias == 'bullish':
                if price_change > 0.01:
                    action = Action.BUY
                    confidence = 0.7 + price_change * 10
                else:
                    action = Action.HOLD
                    confidence = 0.5
            elif self.bias == 'bearish':
                if price_change < -0.01:
                    action = Action.SELL
                    confidence = 0.7 - price_change * 10
                else:
                    action = Action.HOLD
                    confidence = 0.5
            else:  # neutral
                if abs(price_change) < 0.005:
                    action = Action.HOLD
                    confidence = 0.6
                elif price_change > 0.02:
                    action = Action.BUY
                    confidence = 0.65
                elif price_change < -0.02:
                    action = Action.SELL
                    confidence = 0.65
                else:
                    action = Action.HOLD
                    confidence = 0.5

            confidence = min(max(confidence, 0.5), 0.95)

            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=market_data['symbol'],
                action=action,
                confidence=confidence,
                reasoning=f"Mock decision based on {self.bias} bias",
                metadata={'mock': True}
            )

    # 创建模拟智能体
    agents = [
        MockAgent("mock_bull", AgentType.MOMENTUM_CHASER, "bullish"),
        MockAgent("mock_bear", AgentType.VALUE_SEEKER, "bearish"),
        MockAgent("mock_neutral", AgentType.TECHNICAL_TRADER, "neutral")
    ]

    strategy = MultiAgentStrategy(
        name="MockMultiAgent",
        agents=agents,
        use_expert_panel=False,  # 不使用专家面板（避免LLM调用）
        consensus_threshold=0.6,
        min_confidence=0.6
    )

    return strategy


async def run_backtest_with_multi_agents(
    use_llm: bool = False,
    symbols: list = ['AAPL'],
    start_date: str = '2024-01-01',
    end_date: str = '2024-06-30',
    initial_capital: float = 100000
):
    """运行多智能体回测"""

    print("=" * 70)
    print("Multi-Agent Backtest System")
    print("=" * 70)
    print(f"\nMode: {'LLM-Powered' if use_llm else 'Mock (No LLM)'}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print()

    # 1. 准备数据
    print("Step 1: Loading data...")
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    warmup_days = 60

    price_data = {}
    for symbol in symbols:
        data = generate_mock_data(
            symbol,
            start - timedelta(days=warmup_days),
            end
        )
        price_data[symbol] = data
        print(f"  ✓ Generated {len(data.data)} days of data for {symbol}")

    # 2. 创建策略
    print("\nStep 2: Creating multi-agent strategy...")
    if use_llm:
        print("  ⚠️  LLM mode requires API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
        print("  ⚠️  This will incur API costs!")
        strategy = await create_default_multi_agent_strategy(use_expert_panel=True)
        print(f"  ✓ Created strategy with {len(strategy.agents)} LLM agents")
        print("  ✓ Expert panel enabled (2 rounds)")
    else:
        strategy = await create_multi_agent_strategy_mock()
        print(f"  ✓ Created mock strategy with {len(strategy.agents)} agents")
        print("  ✓ No LLM calls (offline mode)")

    # 3. 配置回测
    print("\nStep 3: Configuring backtest engine...")
    config = BacktestConfig(
        start_date=start,
        end_date=end,
        initial_capital=initial_capital,
        warmup_period=warmup_days,
        commission=0.001,
        slippage=0.0005
    )
    engine = BacktestEngineV2(config)
    engine.load_data(price_data)
    engine.set_strategy(strategy)
    print("  ✓ Backtest engine configured")

    # 4. 运行回测
    print("\nStep 4: Running backtest...")
    print("  (This may take a while with LLM mode)")
    print()

    results = await asyncio.to_thread(engine.run)

    # 5. 显示结果
    print("\n" + "=" * 70)
    print("Backtest Results")
    print("=" * 70)

    portfolio_stats = results.get('portfolio', {})
    print(f"\n【Portfolio Performance】")
    print(f"Initial Capital:  ${config.initial_capital:,.2f}")
    print(f"Final Value:      ${portfolio_stats.get('final_value', 0):,.2f}")
    print(f"Total Return:     ${portfolio_stats.get('total_return_abs', 0):,.2f}")
    print(f"Return %:         {portfolio_stats.get('total_return_pct', 0):.2%}")

    print(f"\n【Trading Activity】")
    stats = results.get('stats', {})
    print(f"Signal Events:    {stats.get('signal_events', 0)}")
    print(f"Order Events:     {stats.get('order_events', 0)}")
    print(f"Fill Events:      {stats.get('fill_events', 0)}")
    print(f"Rejected Orders:  {stats.get('rejected_orders', 0)}")

    print(f"\n【Multi-Agent Statistics】")
    strategy_summary = strategy.get_performance_summary()
    print(f"Total Signals Generated: {strategy_summary['total_signals']}")
    print(f"Decision Count:          {strategy_summary['decision_count']}")
    print(f"Agent Count:             {strategy_summary.get('agent_count', len(strategy.agents))}")
    print(f"Avg Confidence:          {strategy_summary.get('avg_confidence', 0):.2%}")

    if use_llm and hasattr(strategy, 'agents') and strategy.agents:
        # 显示LLM成本统计
        print(f"\n【LLM Cost Analysis】")
        total_cost = 0
        total_tokens = 0
        for agent in strategy.agents:
            if hasattr(agent, 'router') and agent.router:
                stats = agent.router.get_statistics()
                for model_name, model_stats in stats.items():
                    total_cost += model_stats['total_cost']
                    total_tokens += model_stats['total_tokens']

        print(f"Total LLM Cost:   ${total_cost:.4f}")
        print(f"Total Tokens:     {total_tokens:,}")

    print("\n" + "=" * 70)
    print("✅ Backtest completed successfully!")
    print()

    if not use_llm:
        print("💡 Tip: Try --use-llm flag to use real LLM agents (requires API keys)")
    print("💡 Tip: This is a research-grade system under development")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Backtest Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mock                    # Mock mode (no API keys needed)
  %(prog)s --use-llm                 # LLM mode (requires API keys)
  %(prog)s --symbols AAPL MSFT       # Multiple symbols
  %(prog)s --start 2023-01-01        # Custom start date
        """
    )

    parser.add_argument('--use-llm', action='store_true',
                        help='Use real LLM agents (requires API keys)')
    parser.add_argument('--mock', action='store_true',
                        help='Use mock agents (no LLM, no API keys needed)')
    parser.add_argument('--symbols', nargs='+', default=['AAPL'],
                        help='Stock symbols')
    parser.add_argument('--start', default='2024-01-01',
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-06-30',
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000,
                        help='Initial capital')

    args = parser.parse_args()

    # 默认是mock模式
    use_llm = args.use_llm and not args.mock

    if use_llm:
        import os
        if not (os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')):
            print("❌ Error: No API keys found!")
            print("Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
            print("Or use --mock flag for offline demo")
            sys.exit(1)

    try:
        asyncio.run(run_backtest_with_multi_agents(
            use_llm=use_llm,
            symbols=args.symbols,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
