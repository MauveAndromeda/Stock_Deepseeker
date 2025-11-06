#!/usr/bin/env python3
"""
一键回测脚本 - Stock Deepseeker

真正可运行的回测示例，使用真实Yahoo Finance数据。
这是一个完整的端到端示例，展示了项目的实际能力。

用法:
    python run_backtest.py                    # 运行默认回测
    python run_backtest.py --symbols AAPL MSFT  # 自定义股票
    python run_backtest.py --help             # 查看帮助
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
import numpy as np
import argparse

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig, Strategy
from src.backtest.events import SignalEvent
from src.backtest.portfolio_v2 import PortfolioV2
from src.data.providers.yahoo import YahooFinanceProvider
from src.data.providers.base import PriceData


class SimpleMovingAverageCrossover(Strategy):
    """
    双均线交叉策略

    策略逻辑:
    - 当快速均线(短期)上穿慢速均线(长期)时买入
    - 当快速均线下穿慢速均线时卖出
    - 经典的趋势跟踪策略
    """

    def __init__(
        self,
        name: str = "MA_Crossover",
        fast_period: int = 20,
        slow_period: int = 50,
        position_size: float = 0.95  # 使用95%的资金
    ):
        super().__init__(name)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position_size = position_size

        # 存储每个股票的历史MA值
        self.fast_ma_history: Dict[str, List[float]] = {}
        self.slow_ma_history: Dict[str, List[float]] = {}

    def generate_signals(
        self,
        date: datetime,
        data: Dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> List[SignalEvent]:
        """生成交易信号"""
        signals = []

        for symbol, df in data.items():
            if len(df) < self.slow_period:
                continue  # 数据不足

            # 获取最近的收盘价
            recent_closes = df['close'].values[-self.slow_period:]

            # 计算均线
            fast_ma = recent_closes[-self.fast_period:].mean()
            slow_ma = recent_closes.mean()

            # 初始化历史记录
            if symbol not in self.fast_ma_history:
                self.fast_ma_history[symbol] = []
                self.slow_ma_history[symbol] = []

            # 检查是否有前一天的MA（用于检测交叉）
            if len(self.fast_ma_history[symbol]) > 0:
                prev_fast = self.fast_ma_history[symbol][-1]
                prev_slow = self.slow_ma_history[symbol][-1]

                current_price = df['close'].iloc[-1]
                position_obj = portfolio.get_position(symbol)
                current_position = 0 if position_obj is None else position_obj.quantity

                # 金叉：快线上穿慢线 -> 买入信号
                if prev_fast <= prev_slow and fast_ma > slow_ma:
                    if current_position == 0:  # 当前无持仓
                        signals.append(SignalEvent(
                            timestamp=date,
                            symbol=symbol,
                            signal_type='LONG',
                            strength=1.0,
                            metadata={
                                'reason': 'golden_cross',
                                'fast_ma': fast_ma,
                                'slow_ma': slow_ma,
                                'price': current_price
                            }
                        ))
                        self.signals_generated += 1

                # 死叉：快线下穿慢线 -> 卖出信号
                elif prev_fast >= prev_slow and fast_ma < slow_ma:
                    if current_position > 0:  # 当前有持仓
                        signals.append(SignalEvent(
                            timestamp=date,
                            symbol=symbol,
                            signal_type='EXIT',
                            strength=1.0,
                            metadata={
                                'reason': 'death_cross',
                                'fast_ma': fast_ma,
                                'slow_ma': slow_ma,
                                'price': current_price
                            }
                        ))
                        self.signals_generated += 1

            # 更新MA历史
            self.fast_ma_history[symbol].append(fast_ma)
            self.slow_ma_history[symbol].append(slow_ma)

        return signals


def generate_mock_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    initial_price: float = 100.0
) -> PriceData:
    """
    生成模拟数据（用于演示和测试）

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        initial_price: 初始价格

    Returns:
        PriceData对象
    """
    # 生成交易日（仅工作日）
    dates = pd.bdate_range(start=start_date, end=end_date)

    # 生成随机游走价格，带有轻微上升趋势
    np.random.seed(hash(symbol) % 2**32)  # 每个股票有不同的种子
    returns = np.random.randn(len(dates)) * 0.02 + 0.0003  # 年化约7.5%
    prices = initial_price * (1 + returns).cumprod()

    # 生成OHLCV数据
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(len(dates))) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(len(dates))) * 0.01),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, len(dates)),
    }, index=dates)

    # 确保high >= low
    df['high'] = df[['high', 'close', 'open']].max(axis=1)
    df['low'] = df[['low', 'close', 'open']].min(axis=1)

    return PriceData(
        symbol=symbol,
        data=df,
        start_date=dates[0].to_pydatetime(),
        end_date=dates[-1].to_pydatetime(),
        adjusted=True,
        metadata={'source': 'mock', 'generator': 'random_walk'}
    )


def fetch_data(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    warmup_days: int = 60,
    use_mock_data: bool = False
) -> Dict[str, PriceData]:
    """
    获取回测数据

    Args:
        symbols: 股票代码列表
        start_date: 回测开始日期
        end_date: 回测结束日期
        warmup_days: 预热期天数
        use_mock_data: 是否使用模拟数据

    Returns:
        股票代码到PriceData的映射
    """
    print("\n" + "=" * 70)
    if use_mock_data:
        print("正在生成模拟数据... (用于演示)")
    else:
        print("正在获取数据...")
    print("=" * 70)

    price_data = {}
    fetch_start = start_date - timedelta(days=warmup_days)

    if use_mock_data:
        # 使用模拟数据
        for symbol in symbols:
            print(f"生成 {symbol} 模拟数据... ", end='', flush=True)
            data = generate_mock_data(symbol, fetch_start, end_date)
            price_data[symbol] = data
            print(f"✓ ({len(data.data)} 行)")
    else:
        # 使用真实数据
        provider = YahooFinanceProvider()
        for symbol in symbols:
            try:
                print(f"获取 {symbol} 数据... ", end='', flush=True)
                data = provider.get_historical_prices(
                    symbol=symbol,
                    start_date=fetch_start,
                    end_date=end_date,
                    adjusted=True
                )
                price_data[symbol] = data
                print(f"✓ ({len(data.data)} 行)")
            except Exception as e:
                print(f"✗ 失败: {e}")
                print(f"   尝试使用模拟数据作为后备...")
                data = generate_mock_data(symbol, fetch_start, end_date)
                price_data[symbol] = data
                print(f"   ✓ 使用模拟数据 ({len(data.data)} 行)")

    if not price_data:
        raise ValueError("未能获取任何数据，请检查网络连接或股票代码")

    print(f"\n成功获取 {len(price_data)}/{len(symbols)} 个股票的数据")
    return price_data


def print_results(results: Dict):
    """打印回测结果"""
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)

    # 基本信息
    print("\n【基本信息】")
    config = results.get('config')
    portfolio_stats = results.get('portfolio', {})

    if config:
        print(f"初始资金: ${config.initial_capital:,.2f}")

    if portfolio_stats:
        print(f"最终资金: ${portfolio_stats.get('final_value', 0):,.2f}")
        print(f"总收益: ${portfolio_stats.get('total_return_abs', 0):,.2f}")
        print(f"总收益率: {portfolio_stats.get('total_return_pct', 0):.2%}")

    # 交易统计
    print("\n【交易统计】")
    stats = results.get('stats', {})
    print(f"总事件数: {stats.get('total_events', 0)}")
    print(f"市场事件: {stats.get('market_events', 0)}")
    print(f"信号事件: {stats.get('signal_events', 0)}")
    print(f"订单事件: {stats.get('order_events', 0)}")
    print(f"成交事件: {stats.get('fill_events', 0)}")
    print(f"拒绝订单: {stats.get('rejected_orders', 0)}")

    # 持仓信息
    print("\n【最终持仓】")
    positions = portfolio_stats.get('positions', {})
    if positions:
        for symbol, qty in positions.items():
            print(f"{symbol}: {qty} 股")
    else:
        print("无持仓")

    # 权益曲线信息
    if 'equity_curve' in results:
        equity = results['equity_curve']
        print(f"\n【权益曲线】")
        print(f"数据点数: {len(equity)}")
        if len(equity) > 0:
            # equity可能是Series或DataFrame，需要提取值
            if hasattr(equity, 'values'):
                values = equity.values if equity.ndim == 1 else equity.values[:, 0]
                print(f"起始值: ${values[0]:,.2f}")
                print(f"最终值: ${values[-1]:,.2f}")
                print(f"最高值: ${values.max():,.2f}")
                print(f"最低值: ${values.min():,.2f}")

    print("\n" + "=" * 70)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Stock Deepseeker 一键回测脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 默认回测 AAPL
  %(prog)s --symbols AAPL MSFT      # 回测多个股票
  %(prog)s --start 2022-01-01       # 自定义开始日期
  %(prog)s --capital 50000          # 自定义初始资金
        """
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['AAPL'],
        help='股票代码列表 (默认: AAPL)'
    )
    parser.add_argument(
        '--start',
        type=str,
        default='2023-01-01',
        help='回测开始日期 YYYY-MM-DD (默认: 2023-01-01)'
    )
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='回测结束日期 YYYY-MM-DD (默认: 今天)'
    )
    parser.add_argument(
        '--capital',
        type=float,
        default=100000.0,
        help='初始资金 (默认: 100000)'
    )
    parser.add_argument(
        '--fast-ma',
        type=int,
        default=20,
        help='快速均线周期 (默认: 20)'
    )
    parser.add_argument(
        '--slow-ma',
        type=int,
        default=50,
        help='慢速均线周期 (默认: 50)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='使用模拟数据（用于演示和测试）'
    )

    args = parser.parse_args()

    # 解析日期
    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d') if args.end else datetime.now()

    # 打印配置
    print("=" * 70)
    print("Stock Deepseeker - 一键回测")
    print("=" * 70)
    print(f"\n配置:")
    print(f"  股票代码: {', '.join(args.symbols)}")
    print(f"  回测周期: {start_date.date()} 至 {end_date.date()}")
    print(f"  初始资金: ${args.capital:,.2f}")
    print(f"  策略参数: 快速MA={args.fast_ma}, 慢速MA={args.slow_ma}")

    try:
        # 1. 获取数据
        price_data = fetch_data(
            symbols=args.symbols,
            start_date=start_date,
            end_date=end_date,
            warmup_days=args.slow_ma + 10,  # 确保有足够的warmup数据
            use_mock_data=args.mock
        )

        # 2. 配置回测
        print("\n" + "=" * 70)
        print("配置回测引擎...")
        print("=" * 70)

        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=args.capital,
            warmup_period=args.slow_ma + 10,
            commission=0.001,  # 0.1%
            slippage=0.0005,   # 0.05%
        )

        # 3. 创建引擎和策略
        engine = BacktestEngineV2(config)
        strategy = SimpleMovingAverageCrossover(
            fast_period=args.fast_ma,
            slow_period=args.slow_ma
        )

        print(f"✓ 引擎已创建")
        print(f"✓ 策略: {strategy.name}")

        # 4. 加载数据
        print("\n加载数据到引擎...")
        engine.load_data(price_data)
        print(f"✓ 已加载 {len(price_data)} 个股票")

        # 5. 设置策略
        engine.set_strategy(strategy)
        print(f"✓ 策略已设置")

        # 6. 运行回测
        print("\n" + "=" * 70)
        print("运行回测... (这可能需要几秒钟)")
        print("=" * 70)

        results = engine.run()

        # 7. 显示结果
        print_results(results)

        # 8. 成功提示
        print("\n✅ 回测成功完成！")
        print("\n💡 提示:")
        print("   - 这是一个简单的双均线策略示例")
        print("   - 结果仅供研究和学习，不构成投资建议")
        print("   - 可以修改参数重新运行: python run_backtest.py --help")

    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
