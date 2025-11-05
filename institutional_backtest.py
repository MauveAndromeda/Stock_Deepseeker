"""
机构级回测系统
支持5-10年历史数据回测，集成多种AI API
目标：年化收益率30%-50%+，最大回撤<15%
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from dotenv import load_dotenv

from src.ai.unified_client import UnifiedAIClient, AIProvider
from src.models.alpha_factors import AlphaFactorLibrary
from src.risk.regime_detection import MarketRegimeDetector, MarketRegime
from src.strategy.enhanced_strategy import EnhancedTradingStrategy
from src.core.config import Config
from src.core.logging import get_logger
from src.data.provider import DataProvider

# 加载环境变量
load_dotenv()

logger = get_logger(__name__)


class InstitutionalBacktest:
    """
    机构级回测系统

    特性：
    1. 多年回测（5-10年）
    2. AI增强信号（GPT/Claude/Gemini）
    3. 100+ Alpha因子
    4. 动态市场状态检测
    5. 高级风险管理
    6. 多策略ensemble
    """

    def __init__(
        self,
        start_date: str = "2015-01-01",
        end_date: str = "2024-12-31",
        initial_capital: float = 100000,
        symbols: List[str] = None,
        ai_provider: str = "openai",
        ai_model: Optional[str] = None,
        use_ai_enhancement: bool = True,
        use_ensemble: bool = True
    ):
        """
        初始化回测系统

        Args:
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            symbols: 股票列表
            ai_provider: AI提供商 (openai/anthropic/google/deepseek)
            ai_model: AI模型名称
            use_ai_enhancement: 是否使用AI增强
            use_ensemble: 是否使用ensemble策略
        """
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # 默认股票池（美股大盘股+科技股）
        if symbols is None:
            self.symbols = [
                # 科技股
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
                # 金融
                'JPM', 'BAC', 'WFC', 'GS', 'MS',
                # 消费
                'WMT', 'HD', 'NKE', 'MCD', 'SBUX',
                # 医疗
                'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO',
                # 工业
                'BA', 'CAT', 'GE', 'MMM', 'HON',
                # 能源
                'XOM', 'CVX', 'COP',
                # 通信
                'VZ', 'T', 'TMUS'
            ]
        else:
            self.symbols = symbols

        # AI配置
        self.use_ai_enhancement = use_ai_enhancement
        self.ai_provider = AIProvider[ai_provider.upper()]
        self.ai_model = ai_model
        self.ai_client = None

        # 策略配置
        self.use_ensemble = use_ensemble

        # 组件初始化
        self.config = Config()
        self.data_provider = DataProvider()
        self.alpha_library = AlphaFactorLibrary()
        self.regime_detector = MarketRegimeDetector()
        self.strategy = EnhancedTradingStrategy()

        # 回测数据
        self.portfolio = {}  # 当前持仓
        self.trades = []     # 交易记录
        self.equity_curve = []  # 权益曲线
        self.daily_returns = []  # 日收益率

        # 性能统计
        self.ai_calls = 0
        self.ai_cost = 0.0

    async def download_data(self) -> Dict[str, pd.DataFrame]:
        """
        下载历史数据

        Returns:
            symbol -> DataFrame 的映射
        """
        print("\n" + "=" * 80)
        print("📥 下载历史数据")
        print("=" * 80)

        all_data = {}
        success_count = 0

        for symbol in self.symbols:
            try:
                print(f"  下载 {symbol}...", end=" ", flush=True)

                df = self.data_provider.get_historical_data(
                    symbol,
                    start_date=self.start_date,
                    end_date=self.end_date
                )

                if df is not None and len(df) > 0:
                    all_data[symbol] = df
                    success_count += 1
                    print(f"✓ ({len(df)} 条数据)")
                else:
                    print("✗ 无数据")

            except Exception as e:
                print(f"✗ 错误: {e}")
                continue

        print(f"\n成功下载: {success_count}/{len(self.symbols)} 只股票")

        return all_data

    async def initialize_ai_client(self):
        """初始化AI客户端"""
        if self.use_ai_enhancement:
            print("\n" + "=" * 80)
            print("🤖 初始化AI增强系统")
            print("=" * 80)
            print(f"  提供商: {self.ai_provider.value}")
            print(f"  模型: {self.ai_model or '默认'}")

            self.ai_client = UnifiedAIClient()
            await self.ai_client.__aenter__()

            print("  ✓ AI客户端初始化完成")

    async def get_ai_signal_enhancement(
        self,
        symbol: str,
        market_data: Dict,
        technical_indicators: Dict
    ) -> Dict:
        """
        获取AI增强信号

        Args:
            symbol: 股票代码
            market_data: 市场数据
            technical_indicators: 技术指标

        Returns:
            AI增强信号
        """
        if not self.use_ai_enhancement or not self.ai_client:
            return {'action': 'HOLD', 'confidence': 0.5, 'ai_enhanced': False}

        try:
            # 构建基本面数据（简化版）
            fundamental_data = {
                'symbol': symbol,
                'price': market_data.get('close', 0),
                'volume': market_data.get('volume', 0)
            }

            # 调用AI生成信号
            response = await self.ai_client.generate_trading_signal(
                market_data,
                technical_indicators,
                fundamental_data,
                provider=self.ai_provider,
                model=self.ai_model
            )

            self.ai_calls += 1
            self.ai_cost += response.cost

            # 解析AI响应
            try:
                signal_data = self.ai_client.parse_json_response(response.content)
                signal_data['ai_enhanced'] = True
                signal_data['ai_cost'] = response.cost
                return signal_data
            except Exception as e:
                logger.warning(f"AI响应解析失败: {e}")
                return {'action': 'HOLD', 'confidence': 0.5, 'ai_enhanced': False}

        except Exception as e:
            logger.error(f"AI信号生成失败: {e}")
            return {'action': 'HOLD', 'confidence': 0.5, 'ai_enhanced': False}

    def calculate_position_size(
        self,
        signal: Dict,
        regime: MarketRegime,
        factor_score: float,
        current_price: float
    ) -> int:
        """
        计算仓位大小

        Args:
            signal: 交易信号
            regime: 市场状态
            factor_score: 因子得分
            current_price: 当前价格

        Returns:
            股数
        """
        # 获取市场状态参数
        regime_params = self.regime_detector.get_regime_parameters(regime)
        base_position_pct = regime_params['max_position']

        # AI置信度调整
        ai_confidence = signal.get('confidence', 0.5)
        confidence_adj = 0.5 + (ai_confidence * 0.5)  # 0.5-1.0

        # 因子得分调整（标准化到0-1）
        factor_adj = 0.5 + (factor_score * 0.5)

        # 综合仓位比例
        position_pct = base_position_pct * confidence_adj * factor_adj

        # 限制最大仓位（不超过20%）
        position_pct = min(position_pct, 0.20)

        # 计算可用资金
        available_capital = self.current_capital * position_pct

        # 计算股数
        shares = int(available_capital / current_price)

        return max(shares, 0)

    async def run_backtest(self):
        """运行回测"""
        print("\n" + "=" * 80)
        print("🚀 启动机构级回测系统")
        print("=" * 80)
        print(f"  回测期间: {self.start_date} → {self.end_date}")
        print(f"  初始资金: ${self.initial_capital:,.0f}")
        print(f"  股票池: {len(self.symbols)} 只")
        print(f"  AI增强: {'是' if self.use_ai_enhancement else '否'}")
        print(f"  Ensemble策略: {'是' if self.use_ensemble else '否'}")

        # 1. 下载数据
        all_data = await self.download_data()

        if len(all_data) == 0:
            print("\n❌ 未能下载任何数据，回测终止")
            return

        # 2. 下载基准数据（SPY）
        print("\n📊 下载基准数据 (SPY)...")
        spy_data = self.data_provider.get_historical_data(
            'SPY',
            start_date=self.start_date,
            end_date=self.end_date
        )

        # 3. 初始化AI客户端
        await self.initialize_ai_client()

        # 4. 获取所有交易日
        all_dates = sorted(set(
            date for df in all_data.values()
            for date in df.index
        ))

        print(f"\n总交易日: {len(all_dates)} 天")

        # 5. 计算Alpha因子
        print("\n" + "=" * 80)
        print("📊 计算Alpha因子 (100+ 因子)")
        print("=" * 80)

        factor_data = {}
        for symbol in all_data.keys():
            try:
                data_dict = {
                    symbol: {
                        'prices': all_data[symbol]['Close'],
                        'ohlcv': all_data[symbol],
                        'volume': all_data[symbol]['Volume'],
                        'fundamentals': {
                            'market_cap': 1000000000,  # 简化
                            'book_value': 500000000,
                            'earnings': 100000000,
                            'revenue': 1000000000,
                            'cash_flow': 150000000,
                            'roa': 0.10,
                            'delta_roa': 0.01,
                            'delta_leverage': -0.01,
                            'delta_liquidity': 0.02,
                            'delta_margin': 0.01,
                            'delta_turnover': 0.01,
                            'accruals': 5
                        }
                    }
                }

                factors = self.alpha_library.compute_all_factors(data_dict)
                factor_data[symbol] = factors[symbol]

                print(f"  ✓ {symbol}: {len(factors[symbol].columns)} 个因子")

            except Exception as e:
                logger.error(f"计算 {symbol} 因子失败: {e}")
                continue

        # 6. 主回测循环
        print("\n" + "=" * 80)
        print("⚙️  开始回测")
        print("=" * 80)

        start_index = 60  # 需要足够历史数据
        total_days = len(all_dates) - start_index

        for day_idx, current_date in enumerate(all_dates[start_index:], 1):
            # 进度显示
            if day_idx % 50 == 0 or day_idx == total_days:
                pct = (day_idx / total_days) * 100
                current_value = self.current_capital + sum(
                    self.portfolio.get(sym, 0) * all_data[sym].loc[current_date, 'Close']
                    for sym in self.portfolio.keys()
                    if current_date in all_data[sym].index
                )
                print(f"  进度: {pct:.1f}% ({day_idx}/{total_days}) | "
                      f"资产: ${current_value:,.0f} | "
                      f"持仓: {len(self.portfolio)} 只")

            # 检测市场状态
            market_data = spy_data.loc[:current_date].tail(60)
            regime = self.regime_detector.detect_regime(market_data, method='rule_based')

            # 计算当前持仓价值
            portfolio_value = sum(
                self.portfolio.get(sym, 0) * all_data[sym].loc[current_date, 'Close']
                for sym in self.portfolio.keys()
                if current_date in all_data[sym].index
            )
            total_value = self.current_capital + portfolio_value

            # 记录权益
            self.equity_curve.append({
                'date': current_date,
                'equity': total_value,
                'cash': self.current_capital,
                'positions': portfolio_value
            })

            # 因子选股
            stock_scores = {}
            for symbol in all_data.keys():
                if current_date not in all_data[symbol].index:
                    continue
                if symbol not in factor_data:
                    continue

                # 获取当前因子值
                if current_date in factor_data[symbol].index:
                    factor_row = factor_data[symbol].loc[current_date]

                    # 计算综合得分（简化：取所有因子的均值）
                    valid_factors = factor_row.dropna()
                    if len(valid_factors) > 0:
                        score = valid_factors.mean()
                        stock_scores[symbol] = score

            # 选择Top N股票
            if len(stock_scores) > 0:
                top_stocks = sorted(
                    stock_scores.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]  # Top 5

                # 生成交易信号
                for symbol, factor_score in top_stocks:
                    current_price = all_data[symbol].loc[current_date, 'Close']

                    # 构建技术指标
                    tech_indicators = {
                        'price': current_price,
                        'volume': all_data[symbol].loc[current_date, 'Volume'],
                        'factor_score': factor_score
                    }

                    market_data_dict = {
                        'close': current_price,
                        'volume': all_data[symbol].loc[current_date, 'Volume'],
                        'price_change': all_data[symbol]['Close'].pct_change().loc[current_date],
                        'volatility': all_data[symbol]['Close'].pct_change().std()
                    }

                    # AI增强（每10天调用一次，节省成本）
                    if day_idx % 10 == 0:
                        ai_signal = await self.get_ai_signal_enhancement(
                            symbol,
                            market_data_dict,
                            tech_indicators
                        )
                    else:
                        ai_signal = {'action': 'HOLD', 'confidence': 0.7, 'ai_enhanced': False}

                    # 决策：买入
                    if ai_signal['action'] in ['BUY', 'HOLD'] and factor_score > 0:
                        if symbol not in self.portfolio or self.portfolio[symbol] == 0:
                            # 计算仓位
                            shares = self.calculate_position_size(
                                ai_signal,
                                regime,
                                factor_score,
                                current_price
                            )

                            if shares > 0:
                                cost = shares * current_price * 1.001  # 含手续费

                                if cost <= self.current_capital:
                                    self.portfolio[symbol] = shares
                                    self.current_capital -= cost

                                    self.trades.append({
                                        'timestamp': current_date,
                                        'symbol': symbol,
                                        'action': 'BUY',
                                        'quantity': shares,
                                        'price': current_price,
                                        'value': cost,
                                        'factor_score': factor_score,
                                        'regime': regime.value,
                                        'ai_enhanced': ai_signal.get('ai_enhanced', False)
                                    })

                # 卖出逻辑：不在Top 5或亏损超过止损
                symbols_to_sell = []
                top_symbols = {s for s, _ in top_stocks}

                for symbol in self.portfolio.keys():
                    if self.portfolio[symbol] == 0:
                        continue
                    if current_date not in all_data[symbol].index:
                        continue

                    current_price = all_data[symbol].loc[current_date, 'Close']

                    # 找到买入价
                    buy_trades = [t for t in self.trades
                                 if t['symbol'] == symbol and t['action'] == 'BUY']
                    if len(buy_trades) > 0:
                        avg_buy_price = sum(t['price'] for t in buy_trades) / len(buy_trades)
                        pnl_pct = (current_price - avg_buy_price) / avg_buy_price

                        # 止损或不在Top 5
                        regime_params = self.regime_detector.get_regime_parameters(regime)
                        stop_loss = regime_params['stop_loss']

                        if pnl_pct < -stop_loss or symbol not in top_symbols:
                            symbols_to_sell.append(symbol)

                # 执行卖出
                for symbol in symbols_to_sell:
                    if self.portfolio[symbol] > 0:
                        shares = self.portfolio[symbol]
                        current_price = all_data[symbol].loc[current_date, 'Close']
                        proceeds = shares * current_price * 0.999  # 扣除手续费

                        self.current_capital += proceeds
                        self.portfolio[symbol] = 0

                        # 计算PnL
                        buy_trades = [t for t in self.trades
                                     if t['symbol'] == symbol and t['action'] == 'BUY']
                        total_cost = sum(t['value'] for t in buy_trades)
                        pnl = proceeds - total_cost

                        self.trades.append({
                            'timestamp': current_date,
                            'symbol': symbol,
                            'action': 'SELL',
                            'quantity': shares,
                            'price': current_price,
                            'value': proceeds,
                            'pnl': pnl,
                            'regime': regime.value
                        })

        # 关闭AI客户端
        if self.ai_client:
            await self.ai_client.__aexit__(None, None, None)

        print("\n✅ 回测完成！")

    def generate_report(self, output_dir: str = "institutional_results"):
        """生成回测报告"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print("\n" + "=" * 80)
        print("📊 生成回测报告")
        print("=" * 80)

        # 1. 保存权益曲线
        equity_df = pd.DataFrame(self.equity_curve)
        equity_file = output_path / "equity_curve.csv"
        equity_df.to_csv(equity_file, index=False)
        print(f"  ✓ 权益曲线: {equity_file}")

        # 2. 保存交易记录
        trades_df = pd.DataFrame(self.trades)
        trades_file = output_path / "trades.csv"
        trades_df.to_csv(trades_file, index=False)
        print(f"  ✓ 交易记录: {trades_file}")

        # 3. 计算性能指标
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 计算年数
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        years = (end - start).days / 365.25

        annualized_return = (1 + total_return) ** (1 / years) - 1

        # 最大回撤
        equity_curve = equity_df['equity'].values
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()

        # 夏普比率
        returns = equity_df['equity'].pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)

        # 交易统计
        buy_trades = trades_df[trades_df['action'] == 'BUY']
        sell_trades = trades_df[trades_df['action'] == 'SELL']

        winning_trades = len(sell_trades[sell_trades['pnl'] > 0])
        total_trades = len(sell_trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        metrics = {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'win_rate': win_rate,
            'ai_calls': self.ai_calls,
            'ai_cost': self.ai_cost,
            'backtest_years': years
        }

        # 保存指标
        metrics_file = output_path / "metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"  ✓ 性能指标: {metrics_file}")

        # 4. 显示摘要
        print("\n" + "=" * 80)
        print("📈 回测结果摘要")
        print("=" * 80)
        print(f"  回测年数: {years:.2f} 年")
        print(f"  初始资金: ${self.initial_capital:,.0f}")
        print(f"  最终权益: ${final_equity:,.0f}")
        print(f"  总收益率: {total_return:.2%}")
        print(f"  年化收益率: {annualized_return:.2%}")
        print(f"  最大回撤: {max_drawdown:.2%}")
        print(f"  夏普比率: {sharpe_ratio:.2f}")
        print(f"  总交易: {len(self.trades)} 笔")
        print(f"  胜率: {win_rate:.2%}")

        if self.use_ai_enhancement:
            print(f"\n🤖 AI增强统计:")
            print(f"  AI调用次数: {self.ai_calls}")
            print(f"  AI总成本: ${self.ai_cost:.2f}")

        print("\n" + "=" * 80)

        # 目标评估
        if annualized_return >= 0.30:
            print("🎯 ✅ 达到年化收益率目标 (>30%)")
        else:
            gap = (0.30 - annualized_return) * 100
            print(f"🎯 ⚠️  距离30%目标还差 {gap:.1f} 个百分点")

        if abs(max_drawdown) <= 0.15:
            print("🛡️  ✅ 风险控制良好 (回撤<15%)")
        else:
            print(f"🛡️  ⚠️  回撤稍高 ({abs(max_drawdown):.1%})")

        print("=" * 80)

        return metrics


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="机构级回测系统")
    parser.add_argument('--start', type=str, default='2015-01-01', help='开始日期')
    parser.add_argument('--end', type=str, default='2024-12-31', help='结束日期')
    parser.add_argument('--capital', type=float, default=100000, help='初始资金')
    parser.add_argument('--ai-provider', type=str, default='openai',
                       choices=['openai', 'anthropic', 'google', 'deepseek'],
                       help='AI提供商')
    parser.add_argument('--ai-model', type=str, help='AI模型名称')
    parser.add_argument('--no-ai', action='store_true', help='禁用AI增强')
    parser.add_argument('--output', type=str, default='institutional_results',
                       help='输出目录')

    args = parser.parse_args()

    # 创建回测实例
    backtest = InstitutionalBacktest(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        ai_provider=args.ai_provider,
        ai_model=args.ai_model,
        use_ai_enhancement=not args.no_ai
    )

    # 运行回测
    await backtest.run_backtest()

    # 生成报告
    backtest.generate_report(output_dir=args.output)

    print("\n✨ 回测系统使用示例:")
    print("  # 10年回测，使用GPT-4o-mini")
    print("  python institutional_backtest.py --start 2014-01-01 --end 2024-01-01 --ai-provider openai --ai-model gpt-4o-mini")
    print("\n  # 5年回测，使用Claude 3.5 Sonnet")
    print("  python institutional_backtest.py --start 2019-01-01 --ai-provider anthropic --ai-model claude-3-5-sonnet-20241022")
    print("\n  # 无AI增强回测")
    print("  python institutional_backtest.py --no-ai")


if __name__ == "__main__":
    asyncio.run(main())
