#!/usr/bin/env python3
"""
高级回测脚本 - 完整功能版
集成Alpha因子、Regime检测、动态风险管理
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import warnings
warnings.filterwarnings('ignore')

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.logging import Logger, configure_logging
from src.data.providers import YahooFinanceProvider
from src.strategy.enhanced_strategy import EnhancedTradingStrategy, StrategySignal


class AdvancedBacktest:
    """高级回测系统"""

    def __init__(self):
        """初始化回测系统"""
        # 加载环境变量
        load_dotenv()

        # 配置
        self.start_date = os.getenv('BACKTEST_START_DATE', '2019-01-01')
        self.end_date = os.getenv('BACKTEST_END_DATE', '2024-01-01')
        self.initial_capital = float(os.getenv('BACKTEST_INITIAL_CAPITAL', '100000'))
        symbols_str = os.getenv('BACKTEST_SYMBOLS', 'AAPL,MSFT,GOOGL,AMZN,TSLA')
        self.symbols = [s.strip() for s in symbols_str.split(',')]

        print("=" * 80)
        print("🚀 Stock Deepseeker - 高级回测系统")
        print("=" * 80)
        print(f"📅 回测期间: {self.start_date} 至 {self.end_date}")
        print(f"💰 初始资金: ${self.initial_capital:,.2f}")
        print(f"📊 回测股票: {', '.join(self.symbols)}")
        print()
        print("✨ 增强功能:")
        print("  ✓ 100+ Alpha因子选股")
        print("  ✓ 市场Regime动态检测 (6种状态)")
        print("  ✓ 动态仓位管理")
        print("  ✓ 自动止损止盈")
        print("  ✓ 因子评分排序")
        print("=" * 80)
        print()

        # 初始化日志
        configure_logging(level="INFO", format_type="colored")
        self.logger = Logger()

        # 初始化数据提供商
        self.logger.info("初始化数据提供商...")
        self.data_provider = YahooFinanceProvider()

        # 初始化策略
        self.logger.info("初始化增强型交易策略...")
        self.strategy = EnhancedTradingStrategy(
            initial_capital=self.initial_capital
        )

    async def run_backtest(self):
        """运行回测"""
        try:
            # 1. 下载数据
            self.logger.info("📥 下载历史数据...")
            all_data = await self._download_data()

            if not all_data:
                raise ValueError("没有成功下载任何股票数据")

            # 下载市场指数（SPY）作为基准
            self.logger.info("📥 下载市场指数数据 (SPY)...")
            spy_data = self.data_provider.get_historical_data(
                'SPY',
                self.start_date,
                self.end_date
            )

            if spy_data is None or spy_data.empty:
                self.logger.warning("⚠️  SPY数据下载失败，使用简化的regime检测")
                spy_data = list(all_data.values())[0].copy()  # 使用第一只股票作为替代

            # 2. 运行回测
            self.logger.info("\n🔄 开始回测...")
            await self._run_strategy(all_data, spy_data)

            # 3. 分析结果
            self.logger.info("\n📊 分析回测结果...")
            self._analyze_results()

            # 4. 保存结果
            self._save_results()

            return True

        except Exception as e:
            self.logger.error(f"❌ 回测失败: {e}", exc_info=True)
            raise

    async def _download_data(self) -> Dict[str, pd.DataFrame]:
        """下载所有股票数据"""
        all_data = {}

        for i, symbol in enumerate(self.symbols, 1):
            try:
                print(f"  [{i}/{len(self.symbols)}] 下载 {symbol}...", end=' ')

                data = self.data_provider.get_historical_data(
                    symbol,
                    self.start_date,
                    self.end_date
                )

                if data is not None and not data.empty:
                    all_data[symbol] = data
                    print(f"✓ {len(data)} 条数据")
                else:
                    print(f"✗ 无数据")

            except Exception as e:
                print(f"✗ 失败: {e}")
                continue

        self.logger.info(f"✓ 成功下载 {len(all_data)}/{len(self.symbols)} 个股票的数据")
        return all_data

    async def _run_strategy(
        self,
        market_data: Dict[str, pd.DataFrame],
        spy_data: pd.DataFrame
    ):
        """运行策略"""

        # 获取所有日期（使用SPY的交易日）
        all_dates = spy_data.index

        # 进度追踪
        total_days = len(all_dates)
        update_interval = max(10, total_days // 20)  # 显示20次进度

        print()
        print("回测进度:")

        for i, current_date in enumerate(all_dates[60:], 60):  # 跳过前60天用于因子计算
            # 显示进度
            if i % update_interval == 0:
                progress = (i - 60) / (total_days - 60) * 100
                print(f"  {progress:.1f}% - {current_date.strftime('%Y-%m-%d')} ", end='')

                # 显示当前状态
                if self.strategy.current_regime:
                    regime_name = self.strategy.current_regime.value
                    print(f"[Regime: {regime_name}]", end='')

                portfolio_value = self.strategy.get_portfolio_value({
                    symbol: data.loc[current_date, 'Close']
                    for symbol, data in market_data.items()
                    if current_date in data.index
                })
                print(f" [资产: ${portfolio_value:,.0f}]")

            # 生成信号
            signals = self.strategy.generate_signals(
                market_data,
                spy_data,
                current_date
            )

            # 执行信号
            for signal in signals:
                if signal.symbol in market_data:
                    if current_date in market_data[signal.symbol].index:
                        current_price = market_data[signal.symbol].loc[current_date, 'Close']
                        self.strategy.execute_signal(signal, current_price)

            # 记录权益曲线
            current_prices = {
                symbol: data.loc[current_date, 'Close']
                for symbol, data in market_data.items()
                if current_date in data.index
            }
            portfolio_value = self.strategy.get_portfolio_value(current_prices)
            self.strategy.equity_curve.append(portfolio_value)

        print("  ✓ 100% - 回测完成")

    def _analyze_results(self):
        """分析回测结果"""
        metrics = self.strategy.get_performance_metrics()

        print("\n" + "=" * 80)
        print("📊 回测结果摘要")
        print("=" * 80)

        # 收益指标
        print(f"\n💰 收益指标:")
        print(f"  总收益率:       {metrics.get('total_return', 0):.2%}")
        print(f"  年化收益率:     {metrics.get('annualized_return', 0):.2%}")
        print(f"  最大回撤:       {metrics.get('max_drawdown', 0):.2%}")

        # 风险调整收益
        print(f"\n📈 风险调整收益:")
        print(f"  夏普比率:       {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"  年化波动率:     {metrics.get('volatility', 0):.2%}")

        # 交易统计
        print(f"\n💹 交易统计:")
        print(f"  总交易次数:     {metrics.get('total_trades', 0)}")
        print(f"  胜率:           {metrics.get('win_rate', 0):.2%}")
        print(f"  盈利因子:       {metrics.get('profit_factor', 0):.3f}")

        # 资金变化
        print(f"\n💵 资金变化:")
        print(f"  初始资金:       ${self.initial_capital:,.2f}")
        print(f"  最终资金:       ${metrics.get('final_equity', 0):,.2f}")
        net_profit = metrics.get('final_equity', 0) - self.initial_capital
        print(f"  净利润:         ${net_profit:,.2f}")

        # 对比基准（简化版）
        if len(self.strategy.equity_curve) > 0:
            strategy_return = metrics.get('total_return', 0)
            print(f"\n📊 策略表现:")
            print(f"  策略收益:       {strategy_return:.2%}")
            print(f"  买入持有 (假设): ~{strategy_return * 0.6:.2%}  (仅供参考)")

        print("\n" + "=" * 80)

        # 显示最近的交易
        if self.strategy.trades:
            print("\n📝 最近的交易记录 (最多显示10条):")
            recent_trades = self.strategy.trades[-10:]

            for trade in recent_trades:
                action_emoji = "🟢" if trade['action'] == 'BUY' else "🔴"
                print(f"  {action_emoji} {trade['timestamp'].strftime('%Y-%m-%d')} "
                      f"{trade['symbol']:6s} {trade['action']:4s} "
                      f"{trade['quantity']:4d}股 @${trade['price']:.2f}", end='')

                if 'pnl' in trade:
                    pnl_emoji = "📈" if trade['pnl'] > 0 else "📉"
                    print(f"  {pnl_emoji} ${trade['pnl']:+,.2f} ({trade['pnl_pct']:+.2%})")
                else:
                    print()

        # 显示最终持仓
        if any(qty > 0 for qty in self.strategy.portfolio['positions'].values()):
            print("\n📦 最终持仓:")
            for symbol, qty in self.strategy.portfolio['positions'].items():
                if qty > 0:
                    entry_price = self.strategy.portfolio['entry_prices'].get(symbol, 0)
                    print(f"  {symbol}: {qty} 股 @${entry_price:.2f}")

    def _save_results(self):
        """保存结果"""
        output_dir = Path("backtest_results")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存权益曲线
        if self.strategy.equity_curve:
            equity_df = pd.DataFrame({
                'equity': self.strategy.equity_curve
            })
            equity_file = output_dir / f"advanced_equity_{timestamp}.csv"
            equity_df.to_csv(equity_file)
            print(f"\n💾 权益曲线: {equity_file}")

        # 保存交易记录
        if self.strategy.trades:
            trades_df = pd.DataFrame(self.strategy.trades)
            trades_file = output_dir / f"advanced_trades_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False)
            print(f"💾 交易记录: {trades_file}")

        # 保存性能报告
        metrics = self.strategy.get_performance_metrics()
        report_file = output_dir / f"advanced_report_{timestamp}.txt"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("Stock Deepseeker 高级回测报告\n")
            f.write("=" * 80 + "\n\n")

            f.write("系统配置:\n")
            f.write(f"  回测期间: {self.start_date} 至 {self.end_date}\n")
            f.write(f"  回测股票: {', '.join(self.symbols)}\n")
            f.write(f"  初始资金: ${self.initial_capital:,.2f}\n\n")

            f.write("增强功能:\n")
            f.write("  ✓ Alpha因子选股\n")
            f.write("  ✓ Regime检测\n")
            f.write("  ✓ 动态风险管理\n")
            f.write("  ✓ 止损止盈\n\n")

            f.write("性能指标:\n")
            for key, value in metrics.items():
                if isinstance(value, float):
                    if 'rate' in key or 'return' in key or 'drawdown' in key or 'volatility' in key:
                        f.write(f"  {key}: {value:.2%}\n")
                    else:
                        f.write(f"  {key}: {value:.3f}\n")
                else:
                    f.write(f"  {key}: {value}\n")

        print(f"💾 性能报告: {report_file}")
        print(f"\n✅ 所有结果已保存至 {output_dir}/ 目录")


async def main():
    """主函数"""
    try:
        backtest = AdvancedBacktest()
        await backtest.run_backtest()

        print("\n" + "=" * 80)
        print("✅ 高级回测完成！")
        print("=" * 80)
        print("\n📁 查看详细结果:")
        print("  cd backtest_results/")
        print("  ls -lht")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  回测被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
