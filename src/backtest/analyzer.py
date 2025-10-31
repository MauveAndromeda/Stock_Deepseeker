"""
回测分析器
提供性能指标分析和交易分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from scipy import stats


@dataclass
class PerformanceMetrics:
    """性能指标"""
    # 收益指标
    total_return: float  # 总收益率
    annualized_return: float  # 年化收益率
    cumulative_return: float  # 累计收益率

    # 风险指标
    volatility: float  # 波动率
    downside_deviation: float  # 下行偏差
    max_drawdown: float  # 最大回撤
    max_drawdown_duration: int  # 最大回撤持续期（天）

    # 风险调整收益
    sharpe_ratio: float  # 夏普比率
    sortino_ratio: float  # 索提诺比率
    calmar_ratio: float  # 卡玛比率
    omega_ratio: float  # Omega比率

    # 交易统计
    total_trades: int  # 总交易次数
    win_rate: float  # 胜率
    profit_factor: float  # 盈利因子
    avg_win: float  # 平均盈利
    avg_loss: float  # 平均亏损
    win_loss_ratio: float  # 盈亏比

    # 其他
    recovery_factor: float  # 恢复因子
    payoff_ratio: float  # 回报比

    metadata: Dict = field(default_factory=dict)


@dataclass
class TradeMetrics:
    """交易指标"""
    trade_id: str
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_percentage: float
    holding_period: int  # 持仓天数
    mae: float  # Maximum Adverse Excursion
    mfe: float  # Maximum Favorable Excursion
    commission: float = 0.0
    slippage: float = 0.0


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, risk_free_rate: float = 0.02):
        """
        初始化性能分析器

        Args:
            risk_free_rate: 无风险利率（年化）
        """
        self.risk_free_rate = risk_free_rate

    def analyze(
        self,
        equity_curve: pd.Series,
        returns: pd.Series,
        trades: List[Dict],
        benchmark_returns: Optional[pd.Series] = None
    ) -> PerformanceMetrics:
        """
        分析回测性能

        Args:
            equity_curve: 权益曲线
            returns: 收益率序列
            trades: 交易列表
            benchmark_returns: 基准收益率（可选）

        Returns:
            性能指标
        """
        # 收益指标
        total_return = self._calculate_total_return(equity_curve)
        annualized_return = self._calculate_annualized_return(returns)
        cumulative_return = self._calculate_cumulative_return(returns)

        # 风险指标
        volatility = self._calculate_volatility(returns)
        downside_deviation = self._calculate_downside_deviation(returns)
        max_dd, max_dd_duration = self._calculate_max_drawdown(equity_curve)

        # 风险调整收益
        sharpe = self._calculate_sharpe_ratio(returns, volatility)
        sortino = self._calculate_sortino_ratio(returns, downside_deviation)
        calmar = self._calculate_calmar_ratio(annualized_return, max_dd)
        omega = self._calculate_omega_ratio(returns)

        # 交易统计
        trade_stats = self._calculate_trade_statistics(trades)

        # 其他指标
        recovery_factor = abs(total_return / max_dd) if max_dd != 0 else 0
        payoff_ratio = trade_stats['avg_win'] / abs(trade_stats['avg_loss']) if trade_stats['avg_loss'] != 0 else 0

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            cumulative_return=cumulative_return,
            volatility=volatility,
            downside_deviation=downside_deviation,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            omega_ratio=omega,
            total_trades=trade_stats['total_trades'],
            win_rate=trade_stats['win_rate'],
            profit_factor=trade_stats['profit_factor'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            win_loss_ratio=payoff_ratio,
            recovery_factor=recovery_factor,
            payoff_ratio=payoff_ratio
        )

    def _calculate_total_return(self, equity_curve: pd.Series) -> float:
        """计算总收益率"""
        if len(equity_curve) == 0:
            return 0.0
        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]
        return (final - initial) / initial if initial != 0 else 0.0

    def _calculate_annualized_return(self, returns: pd.Series) -> float:
        """计算年化收益率"""
        if len(returns) == 0:
            return 0.0

        # 假设252个交易日
        trading_days = 252
        n_periods = len(returns)

        if n_periods == 0:
            return 0.0

        # 复合收益率
        cumulative_return = (1 + returns).prod() - 1

        # 年化
        years = n_periods / trading_days
        if years > 0:
            annualized = (1 + cumulative_return) ** (1 / years) - 1
        else:
            annualized = 0.0

        return annualized

    def _calculate_cumulative_return(self, returns: pd.Series) -> float:
        """计算累计收益率"""
        return (1 + returns).prod() - 1

    def _calculate_volatility(self, returns: pd.Series, annualize: bool = True) -> float:
        """计算波动率"""
        if len(returns) < 2:
            return 0.0

        vol = returns.std()

        if annualize:
            vol *= np.sqrt(252)  # 年化

        return vol

    def _calculate_downside_deviation(self, returns: pd.Series, annualize: bool = True) -> float:
        """计算下行偏差"""
        if len(returns) == 0:
            return 0.0

        # 只考虑负收益
        negative_returns = returns[returns < 0]

        if len(negative_returns) == 0:
            return 0.0

        downside_dev = negative_returns.std()

        if annualize:
            downside_dev *= np.sqrt(252)

        return downside_dev

    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> Tuple[float, int]:
        """
        计算最大回撤和持续期

        Returns:
            (最大回撤百分比, 持续期天数)
        """
        if len(equity_curve) == 0:
            return 0.0, 0

        # 计算累计最高点
        cummax = equity_curve.cummax()

        # 回撤
        drawdown = (equity_curve - cummax) / cummax

        # 最大回撤
        max_dd = drawdown.min()

        # 计算最大回撤持续期
        max_dd_duration = 0
        current_duration = 0

        for dd in drawdown:
            if dd < 0:
                current_duration += 1
                max_dd_duration = max(max_dd_duration, current_duration)
            else:
                current_duration = 0

        return max_dd, max_dd_duration

    def _calculate_sharpe_ratio(self, returns: pd.Series, volatility: float) -> float:
        """计算夏普比率"""
        if volatility == 0:
            return 0.0

        # 计算超额收益
        excess_returns = returns - self.risk_free_rate / 252  # 日化无风险利率

        # 年化
        mean_excess = excess_returns.mean() * 252

        return mean_excess / volatility if volatility != 0 else 0.0

    def _calculate_sortino_ratio(self, returns: pd.Series, downside_deviation: float) -> float:
        """计算索提诺比率"""
        if downside_deviation == 0:
            return 0.0

        # 计算超额收益
        excess_returns = returns - self.risk_free_rate / 252

        # 年化
        mean_excess = excess_returns.mean() * 252

        return mean_excess / downside_deviation if downside_deviation != 0 else 0.0

    def _calculate_calmar_ratio(self, annualized_return: float, max_drawdown: float) -> float:
        """计算卡玛比率"""
        if max_drawdown == 0:
            return 0.0

        return annualized_return / abs(max_drawdown)

    def _calculate_omega_ratio(self, returns: pd.Series, threshold: float = 0.0) -> float:
        """计算Omega比率"""
        if len(returns) == 0:
            return 0.0

        # 超过阈值的收益
        gains = returns[returns > threshold] - threshold
        # 低于阈值的损失
        losses = threshold - returns[returns < threshold]

        gains_sum = gains.sum() if len(gains) > 0 else 0
        losses_sum = losses.sum() if len(losses) > 0 else 0

        return gains_sum / losses_sum if losses_sum != 0 else 0.0

    def _calculate_trade_statistics(self, trades: List[Dict]) -> Dict:
        """计算交易统计"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }

        total_trades = len(trades)

        # 盈亏分类
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        # 胜率
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        # 平均盈利/亏损
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0

        # 盈利因子
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses != 0 else 0

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }

    def calculate_information_ratio(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """计算信息比率"""
        if len(returns) != len(benchmark_returns):
            return 0.0

        # 超额收益
        excess_returns = returns - benchmark_returns

        # 跟踪误差
        tracking_error = excess_returns.std() * np.sqrt(252)

        if tracking_error == 0:
            return 0.0

        # 平均超额收益
        mean_excess = excess_returns.mean() * 252

        return mean_excess / tracking_error

    def calculate_beta(
        self,
        returns: pd.Series,
        market_returns: pd.Series
    ) -> float:
        """计算Beta"""
        if len(returns) != len(market_returns) or len(returns) < 2:
            return 1.0

        # 协方差
        covariance = np.cov(returns, market_returns)[0][1]

        # 市场方差
        market_variance = market_returns.var()

        if market_variance == 0:
            return 1.0

        return covariance / market_variance


class TradeAnalyzer:
    """交易分析器"""

    def __init__(self):
        """初始化交易分析器"""
        pass

    def analyze_trades(self, trades: List[Dict]) -> Dict[str, any]:
        """
        分析交易

        Args:
            trades: 交易列表

        Returns:
            交易分析结果
        """
        if not trades:
            return {}

        # 转换为TradeMetrics对象
        trade_metrics = []

        for trade in trades:
            if 'entry_time' in trade and 'exit_time' in trade:
                # 计算MAE和MFE（如果有价格历史）
                mae, mfe = self._calculate_mae_mfe(trade)

                tm = TradeMetrics(
                    trade_id=trade.get('trade_id', ''),
                    entry_time=trade['entry_time'],
                    exit_time=trade['exit_time'],
                    symbol=trade.get('symbol', ''),
                    side=trade.get('side', 'long'),
                    entry_price=trade.get('entry_price', 0),
                    exit_price=trade.get('exit_price', 0),
                    quantity=trade.get('quantity', 0),
                    pnl=trade.get('pnl', 0),
                    pnl_percentage=trade.get('pnl_percentage', 0),
                    holding_period=trade.get('holding_period', 0),
                    mae=mae,
                    mfe=mfe,
                    commission=trade.get('commission', 0),
                    slippage=trade.get('slippage', 0)
                )

                trade_metrics.append(tm)

        # 分析
        analysis = {
            'total_trades': len(trade_metrics),
            'long_trades': sum(1 for t in trade_metrics if t.side == 'long'),
            'short_trades': sum(1 for t in trade_metrics if t.side == 'short'),
            'winning_trades': sum(1 for t in trade_metrics if t.pnl > 0),
            'losing_trades': sum(1 for t in trade_metrics if t.pnl < 0),
            'win_rate': sum(1 for t in trade_metrics if t.pnl > 0) / len(trade_metrics),
            'avg_pnl': np.mean([t.pnl for t in trade_metrics]),
            'avg_win': np.mean([t.pnl for t in trade_metrics if t.pnl > 0]) if any(t.pnl > 0 for t in trade_metrics) else 0,
            'avg_loss': np.mean([t.pnl for t in trade_metrics if t.pnl < 0]) if any(t.pnl < 0 for t in trade_metrics) else 0,
            'largest_win': max([t.pnl for t in trade_metrics]) if trade_metrics else 0,
            'largest_loss': min([t.pnl for t in trade_metrics]) if trade_metrics else 0,
            'avg_holding_period': np.mean([t.holding_period for t in trade_metrics]),
            'total_commission': sum(t.commission for t in trade_metrics),
            'total_slippage': sum(t.slippage for t in trade_metrics),
        }

        # 连续盈亏
        analysis['max_consecutive_wins'] = self._max_consecutive(trade_metrics, True)
        analysis['max_consecutive_losses'] = self._max_consecutive(trade_metrics, False)

        # MAE/MFE分析
        analysis['avg_mae'] = np.mean([t.mae for t in trade_metrics])
        analysis['avg_mfe'] = np.mean([t.mfe for t in trade_metrics])

        # 持仓时间分布
        analysis['holding_period_distribution'] = self._analyze_holding_periods(trade_metrics)

        return analysis

    def _calculate_mae_mfe(self, trade: Dict) -> Tuple[float, float]:
        """
        计算MAE (Maximum Adverse Excursion) 和 MFE (Maximum Favorable Excursion)

        Args:
            trade: 交易字典

        Returns:
            (MAE, MFE)
        """
        # 如果交易字典中已有价格历史，使用它
        if 'price_history' in trade:
            prices = trade['price_history']
            entry_price = trade['entry_price']
            side = trade.get('side', 'long')

            if side == 'long':
                # 做多：MAE是最大跌幅，MFE是最大涨幅
                mae = min([(p - entry_price) / entry_price for p in prices])
                mfe = max([(p - entry_price) / entry_price for p in prices])
            else:
                # 做空：MAE是最大涨幅，MFE是最大跌幅
                mae = max([(entry_price - p) / entry_price for p in prices])
                mfe = min([(entry_price - p) / entry_price for p in prices])

            return abs(mae), abs(mfe)
        else:
            # 如果没有历史数据，使用简化计算
            pnl_pct = trade.get('pnl_percentage', 0)
            # 假设MAE是PNL的一半，MFE是PNL的1.5倍（简化）
            if pnl_pct > 0:
                mae = abs(pnl_pct * 0.3)
                mfe = abs(pnl_pct * 1.2)
            else:
                mae = abs(pnl_pct * 1.2)
                mfe = abs(pnl_pct * 0.3)

            return mae, mfe

    def _max_consecutive(self, trades: List[TradeMetrics], winning: bool) -> int:
        """计算最大连续盈亏次数"""
        max_consecutive = 0
        current_consecutive = 0

        for trade in trades:
            if (winning and trade.pnl > 0) or (not winning and trade.pnl < 0):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _analyze_holding_periods(self, trades: List[TradeMetrics]) -> Dict[str, int]:
        """分析持仓时间分布"""
        periods = [t.holding_period for t in trades]

        if not periods:
            return {}

        return {
            'min': min(periods),
            'max': max(periods),
            'median': int(np.median(periods)),
            'mean': int(np.mean(periods)),
            'std': int(np.std(periods))
        }

    def identify_best_worst_trades(
        self,
        trades: List[Dict],
        n: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        识别最好和最差的交易

        Args:
            trades: 交易列表
            n: 返回数量

        Returns:
            {'best': [...], 'worst': [...]}
        """
        sorted_by_pnl = sorted(trades, key=lambda t: t.get('pnl', 0))

        return {
            'worst': sorted_by_pnl[:n],
            'best': sorted_by_pnl[-n:][::-1]
        }

    def analyze_by_symbol(self, trades: List[Dict]) -> Dict[str, Dict]:
        """按股票分析交易"""
        symbol_trades = {}

        for trade in trades:
            symbol = trade.get('symbol', 'UNKNOWN')
            if symbol not in symbol_trades:
                symbol_trades[symbol] = []
            symbol_trades[symbol].append(trade)

        # 为每个股票计算统计
        symbol_stats = {}

        for symbol, symbol_trade_list in symbol_trades.items():
            total_pnl = sum(t.get('pnl', 0) for t in symbol_trade_list)
            win_count = sum(1 for t in symbol_trade_list if t.get('pnl', 0) > 0)

            symbol_stats[symbol] = {
                'total_trades': len(symbol_trade_list),
                'total_pnl': total_pnl,
                'win_rate': win_count / len(symbol_trade_list) if symbol_trade_list else 0,
                'avg_pnl': total_pnl / len(symbol_trade_list) if symbol_trade_list else 0
            }

        return symbol_stats
