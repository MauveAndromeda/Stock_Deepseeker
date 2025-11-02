#!/usr/bin/env python3
"""
快速回测脚本 - 5年历史数据回测
使用 ChatGPT-5 Nano API 进行智能分析
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

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.config import Config, Environment, TradingMode
from src.core.logging import Logger, configure_logging
from src.backtest.engine import BacktestEngine, BacktestConfig
from src.backtest.analyzer import PerformanceAnalyzer, TradeAnalyzer
from src.data.providers import YahooFinanceProvider, MultiSourceProvider
from src.models.gpt5_client import GPT5Client, GPT5Config, MarketAnalyzer
from src.models.transformer import MarketTransformer, TransformerConfig
from src.agents.retail import RetailAgentFactory
from src.agents.institutional import InstitutionalAgentFactory
from src.agents.expert import ExpertPanel, VotingStrategy
from src.agents.base import AgentType


class QuickBacktest:
    """快速回测系统"""

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
        print("Stock Deepseeker - 5年回测系统")
        print("=" * 80)
        print(f"回测期间: {self.start_date} 至 {self.end_date}")
        print(f"初始资金: ${self.initial_capital:,.2f}")
        print(f"回测股票: {', '.join(self.symbols)}")
        print("=" * 80)
        print()

        # 初始化日志
        configure_logging(level="INFO", format_type="colored")
        self.logger = Logger()

        # 初始化数据提供商
        self.logger.info("初始化数据提供商...")
        self.data_provider = YahooFinanceProvider()

        # 初始化AI模型（如果有API key）
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and openai_key != 'your_gpt5_nano_api_key_here':
            self.logger.info("初始化 ChatGPT-5 Nano 分析器...")
            gpt5_config = GPT5Config(
                api_key=openai_key,
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                temperature=0.7
            )
            self.gpt5_client = GPT5Client(gpt5_config)
            self.market_analyzer = MarketAnalyzer(self.gpt5_client)
            self.use_gpt5 = True
        else:
            self.logger.warning("未配置 OpenAI API Key，将不使用 GPT-5 分析")
            self.use_gpt5 = False

        # 初始化智能体
        self.logger.info("初始化多智能体系统...")
        self.agents = self._create_agents()

        # 初始化回测引擎
        self.logger.info("初始化回测引擎...")
        self.backtest_config = BacktestConfig(
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            commission=0.001,  # 0.1% 手续费
            slippage=0.0005    # 0.05% 滑点
        )

    def _create_agents(self) -> List:
        """创建智能体群体"""
        agents = []

        # 零售投资者（较少数量）
        retail_config = {
            AgentType.MOMENTUM_CHASER: 2,
            AgentType.PANIC_SELLER: 1,
            AgentType.TECHNICAL_TRADER: 2,
        }
        retail_agents = RetailAgentFactory.create_population(
            retail_config,
            initial_capital=self.initial_capital * 0.1  # 零售资金较少
        )
        agents.extend(retail_agents)

        # 机构投资者（较多数量和资金）
        institutional_config = {
            AgentType.QUANTITATIVE: 3,
            AgentType.VALUE_INVESTOR: 2,
            AgentType.TREND_FOLLOWER: 2,
        }
        institutional_agents = InstitutionalAgentFactory.create_population(
            institutional_config,
            initial_capital=self.initial_capital
        )
        agents.extend(institutional_agents)

        self.logger.info(f"创建了 {len(agents)} 个智能体")
        return agents

    async def run_backtest(self):
        """运行回测"""
        try:
            self.logger.info("开始下载历史数据...")

            # 下载所有股票的历史数据
            all_data = {}
            for symbol in self.symbols:
                try:
                    print(f"  下载 {symbol} 数据...")
                    data = self.data_provider.get_historical_data(
                        symbol,
                        self.start_date,
                        self.end_date
                    )
                    if data is not None and not data.empty:
                        all_data[symbol] = data
                        print(f"  ✓ {symbol}: {len(data)} 条数据")
                    else:
                        print(f"  ✗ {symbol}: 无数据")
                except Exception as e:
                    print(f"  ✗ {symbol}: 下载失败 - {e}")

            if not all_data:
                raise ValueError("没有成功下载任何股票数据")

            self.logger.info(f"成功下载 {len(all_data)} 个股票的历史数据")

            # 创建简单的交易策略
            def simple_strategy(data: Dict[str, pd.DataFrame], **kwargs):
                """简单的多智能体投票策略"""
                trades = []
                portfolio = {'cash': self.initial_capital, 'positions': {}}

                # 获取日期列表（使用第一个股票的日期）
                first_symbol = list(data.keys())[0]
                dates = data[first_symbol].index

                for i, date in enumerate(dates[20:]):  # 跳过前20天用于计算指标
                    # 为每个股票收集智能体决策
                    for symbol in all_data.keys():
                        if symbol not in data:
                            continue

                        symbol_data = data[symbol].loc[:date]

                        if len(symbol_data) < 20:
                            continue

                        # 准备市场数据
                        current_price = symbol_data['Close'].iloc[-1]
                        prev_price = symbol_data['Close'].iloc[-2]

                        market_data = {
                            'symbol': symbol,
                            'close': current_price,
                            'prev_close': prev_price,
                            'volume': symbol_data['Volume'].iloc[-1],
                            'avg_volume': symbol_data['Volume'].tail(20).mean(),
                            'rsi': self._calculate_rsi(symbol_data['Close']),
                            'macd': 0,  # 简化
                            'macd_signal': 0,
                        }

                        # 收集智能体意见（使用专家面板）
                        expert_panel = ExpertPanel(
                            self.agents[:5],  # 使用前5个智能体
                            voting_strategy=VotingStrategy.CONFIDENCE_WEIGHTED
                        )

                        decision = expert_panel.make_consensus_decision(
                            symbol,
                            market_data
                        )

                        # 执行交易
                        if decision.action.value == 'buy' and decision.confidence > 0.7:
                            # 买入
                            max_position_value = portfolio['cash'] * 0.2  # 最多20%仓位
                            quantity = int(max_position_value / current_price)

                            if quantity > 0 and portfolio['cash'] >= quantity * current_price:
                                cost = quantity * current_price
                                portfolio['cash'] -= cost
                                portfolio['positions'][symbol] = portfolio['positions'].get(symbol, 0) + quantity

                                trades.append({
                                    'date': date,
                                    'symbol': symbol,
                                    'side': 'buy',
                                    'quantity': quantity,
                                    'price': current_price,
                                    'pnl': 0
                                })

                        elif decision.action.value == 'sell' and decision.confidence > 0.7:
                            # 卖出
                            if symbol in portfolio['positions'] and portfolio['positions'][symbol] > 0:
                                quantity = portfolio['positions'][symbol]
                                proceeds = quantity * current_price
                                portfolio['cash'] += proceeds

                                # 计算盈亏
                                buy_trades = [t for t in trades if t['symbol'] == symbol and t['side'] == 'buy']
                                if buy_trades:
                                    avg_buy_price = np.mean([t['price'] for t in buy_trades])
                                    pnl = (current_price - avg_buy_price) * quantity
                                else:
                                    pnl = 0

                                portfolio['positions'][symbol] = 0

                                trades.append({
                                    'date': date,
                                    'symbol': symbol,
                                    'side': 'sell',
                                    'quantity': quantity,
                                    'price': current_price,
                                    'pnl': pnl
                                })

                return trades

            # 运行回测
            self.logger.info("运行回测...")
            engine = BacktestEngine(self.backtest_config)
            result = engine.run(simple_strategy, data=all_data)

            # 分析结果
            self.logger.info("分析回测结果...")
            self._print_results(result)

            # 保存结果
            self._save_results(result)

            return result

        except Exception as e:
            self.logger.error(f"回测失败: {e}", exc_info=True)
            raise

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0

    def _print_results(self, result):
        """打印回测结果"""
        print("\n" + "=" * 80)
        print("回测结果摘要")
        print("=" * 80)

        metrics = result.performance_metrics

        print(f"\n📊 收益指标:")
        print(f"  总收益率:     {metrics['total_return']:.2%}")
        print(f"  年化收益率:   {metrics['annualized_return']:.2%}")
        print(f"  最大回撤:     {metrics['max_drawdown']:.2%}")

        print(f"\n📈 风险调整收益:")
        print(f"  夏普比率:     {metrics['sharpe_ratio']:.3f}")
        print(f"  索提诺比率:   {metrics['sortino_ratio']:.3f}")
        print(f"  卡玛比率:     {metrics['calmar_ratio']:.3f}")

        print(f"\n💹 交易统计:")
        print(f"  总交易次数:   {metrics['total_trades']}")
        print(f"  胜率:         {metrics['win_rate']:.2%}")
        print(f"  盈利因子:     {metrics['profit_factor']:.3f}")

        print(f"\n💰 资金变化:")
        print(f"  初始资金:     ${self.initial_capital:,.2f}")
        print(f"  最终资金:     ${metrics['final_equity']:,.2f}")
        print(f"  净利润:       ${metrics['final_equity'] - self.initial_capital:,.2f}")

        print("\n" + "=" * 80)

    def _save_results(self, result):
        """保存回测结果"""
        # 创建输出目录
        output_dir = Path("backtest_results")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存权益曲线
        if hasattr(result, 'equity_curve'):
            equity_file = output_dir / f"equity_curve_{timestamp}.csv"
            result.equity_curve.to_csv(equity_file)
            print(f"\n💾 权益曲线已保存至: {equity_file}")

        # 保存交易记录
        if hasattr(result, 'trades') and result.trades:
            trades_file = output_dir / f"trades_{timestamp}.csv"
            trades_df = pd.DataFrame(result.trades)
            trades_df.to_csv(trades_file, index=False)
            print(f"💾 交易记录已保存至: {trades_file}")

        # 保存性能指标
        metrics_file = output_dir / f"metrics_{timestamp}.txt"
        with open(metrics_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("Stock Deepseeker 5年回测报告\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"回测期间: {self.start_date} 至 {self.end_date}\n")
            f.write(f"回测股票: {', '.join(self.symbols)}\n")
            f.write(f"初始资金: ${self.initial_capital:,.2f}\n\n")

            metrics = result.performance_metrics
            f.write("收益指标:\n")
            f.write(f"  总收益率:     {metrics['total_return']:.2%}\n")
            f.write(f"  年化收益率:   {metrics['annualized_return']:.2%}\n")
            f.write(f"  最大回撤:     {metrics['max_drawdown']:.2%}\n\n")

            f.write("风险调整收益:\n")
            f.write(f"  夏普比率:     {metrics['sharpe_ratio']:.3f}\n")
            f.write(f"  索提诺比率:   {metrics['sortino_ratio']:.3f}\n\n")

            f.write("交易统计:\n")
            f.write(f"  总交易次数:   {metrics['total_trades']}\n")
            f.write(f"  胜率:         {metrics['win_rate']:.2%}\n")

        print(f"💾 性能指标已保存至: {metrics_file}")


async def main():
    """主函数"""
    try:
        backtest = QuickBacktest()
        await backtest.run_backtest()

        print("\n✅ 回测完成！")
        print("\n📁 结果文件位于 backtest_results/ 目录")

    except KeyboardInterrupt:
        print("\n\n⚠️  回测被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
