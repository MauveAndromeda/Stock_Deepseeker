"""
增强型交易策略
集成Alpha因子、Regime检测、动态风险管理
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.models.alpha_factors import AlphaFactorLibrary, FactorCombiner
from src.risk.regime_detection import MarketRegimeDetector, MarketRegime
from src.agents.base import Agent, AgentDecision, Action
from src.agents.expert import ExpertPanel, VotingStrategy


@dataclass
class StrategySignal:
    """策略信号"""
    symbol: str
    action: Action
    confidence: float
    target_position: float  # 目标仓位比例
    stop_loss: float  # 止损价格
    take_profit: float  # 止盈价格
    reasoning: str
    timestamp: datetime


class EnhancedTradingStrategy:
    """增强型交易策略"""

    def __init__(
        self,
        initial_capital: float = 100000,
        risk_free_rate: float = 0.02
    ):
        """
        初始化策略

        Args:
            initial_capital: 初始资金
            risk_free_rate: 无风险利率
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

        # 初始化子系统
        self.factor_library = AlphaFactorLibrary()
        self.factor_combiner = FactorCombiner()
        self.regime_detector = MarketRegimeDetector()

        # 状态追踪
        self.portfolio = {
            'cash': initial_capital,
            'positions': {},  # {symbol: quantity}
            'entry_prices': {},  # {symbol: price}
            'stop_losses': {},  # {symbol: price}
            'take_profits': {}  # {symbol: price}
        }

        # 性能追踪
        self.equity_curve = []
        self.trades = []
        self.current_regime = None

    def calculate_factors(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        计算所有股票的因子

        Args:
            market_data: {symbol: DataFrame} 市场数据

        Returns:
            {symbol: factor_DataFrame} 因子矩阵
        """
        all_factors = {}

        for symbol, data in market_data.items():
            try:
                # 准备数据
                factor_data = {
                    'close': data['Close'],
                    'volume': data['Volume'],
                    'open': data['Open'],
                    'high': data['High'],
                    'low': data['Low']
                }

                # 计算因子
                factors = self.factor_library.compute_all_factors(factor_data)
                all_factors[symbol] = factors

            except Exception as e:
                print(f"Error calculating factors for {symbol}: {e}")
                continue

        return all_factors

    def rank_stocks_by_factors(
        self,
        factor_data: Dict[str, pd.DataFrame],
        date: pd.Timestamp,
        top_n: int = 5
    ) -> List[Tuple[str, float]]:
        """
        根据因子值排序股票

        Args:
            factor_data: 因子数据
            date: 当前日期
            top_n: 选择前N只

        Returns:
            [(symbol, composite_score), ...] 排序后的股票列表
        """
        scores = {}

        for symbol, factors in factor_data.items():
            try:
                # 获取当前日期的因子值
                if date not in factors.index:
                    continue

                current_factors = factors.loc[date]

                # 计算综合评分（简化：等权重）
                # 只使用数值型且非NaN的因子
                valid_factors = current_factors.dropna()

                if len(valid_factors) > 0:
                    # 综合评分 = 所有因子的平均值（已标准化）
                    composite_score = valid_factors.mean()
                    scores[symbol] = composite_score

            except Exception as e:
                continue

        # 排序
        ranked_stocks = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return ranked_stocks

    def detect_market_regime(
        self,
        market_data: pd.DataFrame
    ) -> MarketRegime:
        """
        检测市场regime

        Args:
            market_data: 市场指数数据（SPY等）

        Returns:
            当前regime
        """
        state = self.regime_detector.detect_regime(
            market_data,
            method='ensemble'
        )

        self.current_regime = state.regime
        return state.regime

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        regime: MarketRegime,
        factor_score: float
    ) -> Tuple[int, float, float]:
        """
        计算仓位大小、止损和止盈

        Args:
            symbol: 股票代码
            current_price: 当前价格
            regime: 市场regime
            factor_score: 因子评分

        Returns:
            (quantity, stop_loss, take_profit)
        """
        # 获取regime参数
        params = self.regime_detector.get_regime_parameters(regime)

        # 计算总资产
        total_value = self.portfolio['cash']
        for pos_symbol, quantity in self.portfolio['positions'].items():
            if quantity > 0:
                total_value += quantity * current_price  # 简化：用当前价

        # 基础仓位（基于regime）
        base_position_ratio = params['max_position']

        # 因子调整（因子评分越高，仓位越大）
        # factor_score 已标准化，范围约 -3 到 +3
        factor_adjustment = 1.0 + (factor_score * 0.1)  # -30% 到 +30%
        factor_adjustment = np.clip(factor_adjustment, 0.5, 1.5)

        # 最终仓位比例
        position_ratio = base_position_ratio * factor_adjustment

        # 计算数量
        position_value = total_value * position_ratio
        quantity = int(position_value / current_price)

        # 止损和止盈
        stop_loss_pct = params['stop_loss']
        take_profit_pct = params['take_profit']

        stop_loss = current_price * (1 - stop_loss_pct)
        take_profit = current_price * (1 + take_profit_pct)

        return quantity, stop_loss, take_profit

    def generate_signals(
        self,
        market_data: Dict[str, pd.DataFrame],
        market_index: pd.DataFrame,
        current_date: pd.Timestamp,
        agent_panel: Optional[ExpertPanel] = None
    ) -> List[StrategySignal]:
        """
        生成交易信号

        Args:
            market_data: 股票数据
            market_index: 市场指数数据
            current_date: 当前日期
            agent_panel: 智能体面板（可选）

        Returns:
            信号列表
        """
        signals = []

        # 1. 检测市场regime
        regime = self.detect_market_regime(market_index.loc[:current_date])

        # 2. 计算因子
        factor_data = self.calculate_factors(market_data)

        # 3. 根据因子排序选股
        top_stocks = self.rank_stocks_by_factors(
            factor_data,
            current_date,
            top_n=10  # 先筛选出前10只
        )

        # 4. 为每只股票生成信号
        for symbol, factor_score in top_stocks:
            try:
                # 获取当前价格
                if current_date not in market_data[symbol].index:
                    continue

                current_price = market_data[symbol].loc[current_date, 'Close']
                current_position = self.portfolio['positions'].get(symbol, 0)

                # 计算仓位
                quantity, stop_loss, take_profit = self.calculate_position_size(
                    symbol,
                    current_price,
                    regime,
                    factor_score
                )

                # 决定动作
                if current_position == 0 and quantity > 0:
                    # 新建仓位
                    action = Action.BUY
                    confidence = 0.7 + min(0.25, factor_score * 0.1)

                elif current_position > 0:
                    # 检查止损/止盈
                    if symbol in self.portfolio['stop_losses']:
                        if current_price <= self.portfolio['stop_losses'][symbol]:
                            # 触发止损
                            action = Action.SELL
                            confidence = 0.95
                            quantity = current_position
                            reasoning = f"触发止损: {current_price:.2f} <= {self.portfolio['stop_losses'][symbol]:.2f}"

                            signals.append(StrategySignal(
                                symbol=symbol,
                                action=action,
                                confidence=confidence,
                                target_position=0,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reasoning=reasoning,
                                timestamp=current_date
                            ))
                            continue

                    if symbol in self.portfolio['take_profits']:
                        if current_price >= self.portfolio['take_profits'][symbol]:
                            # 触发止盈
                            action = Action.SELL
                            confidence = 0.95
                            quantity = current_position
                            reasoning = f"触发止盈: {current_price:.2f} >= {self.portfolio['take_profits'][symbol]:.2f}"

                            signals.append(StrategySignal(
                                symbol=symbol,
                                action=action,
                                confidence=confidence,
                                target_position=0,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reasoning=reasoning,
                                timestamp=current_date
                            ))
                            continue

                    # 正常持有或调整
                    if factor_score < -1.0:
                        # 因子变差，卖出
                        action = Action.SELL
                        confidence = 0.75
                        quantity = current_position
                    else:
                        # 继续持有
                        action = Action.HOLD
                        confidence = 0.6
                        quantity = 0

                else:
                    # 因子评分不够好或regime不合适
                    action = Action.HOLD
                    confidence = 0.5
                    quantity = 0

                # 创建信号
                if action != Action.HOLD or current_position > 0:
                    reasoning = f"Regime={regime.value}, Factor={factor_score:.2f}, Position={current_position}"

                    signal = StrategySignal(
                        symbol=symbol,
                        action=action,
                        confidence=confidence,
                        target_position=quantity,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reasoning=reasoning,
                        timestamp=current_date
                    )

                    signals.append(signal)

            except Exception as e:
                print(f"Error generating signal for {symbol}: {e}")
                continue

        return signals

    def execute_signal(
        self,
        signal: StrategySignal,
        current_price: float
    ) -> Optional[Dict]:
        """
        执行交易信号

        Args:
            signal: 交易信号
            current_price: 当前价格

        Returns:
            交易记录
        """
        symbol = signal.symbol
        action = signal.action

        if action == Action.BUY:
            # 买入
            quantity = signal.target_position
            cost = quantity * current_price

            if self.portfolio['cash'] >= cost and quantity > 0:
                # 执行买入
                self.portfolio['cash'] -= cost
                self.portfolio['positions'][symbol] = \
                    self.portfolio['positions'].get(symbol, 0) + quantity
                self.portfolio['entry_prices'][symbol] = current_price
                self.portfolio['stop_losses'][symbol] = signal.stop_loss
                self.portfolio['take_profits'][symbol] = signal.take_profit

                # 记录交易
                trade = {
                    'timestamp': signal.timestamp,
                    'symbol': symbol,
                    'action': 'BUY',
                    'quantity': quantity,
                    'price': current_price,
                    'value': cost,
                    'reasoning': signal.reasoning
                }

                self.trades.append(trade)
                return trade

        elif action == Action.SELL:
            # 卖出
            if symbol in self.portfolio['positions']:
                quantity = self.portfolio['positions'][symbol]

                if quantity > 0:
                    # 执行卖出
                    proceeds = quantity * current_price
                    self.portfolio['cash'] += proceeds
                    self.portfolio['positions'][symbol] = 0

                    # 计算盈亏
                    entry_price = self.portfolio['entry_prices'].get(symbol, current_price)
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

                    # 清理止损止盈
                    if symbol in self.portfolio['stop_losses']:
                        del self.portfolio['stop_losses'][symbol]
                    if symbol in self.portfolio['take_profits']:
                        del self.portfolio['take_profits'][symbol]
                    if symbol in self.portfolio['entry_prices']:
                        del self.portfolio['entry_prices'][symbol]

                    # 记录交易
                    trade = {
                        'timestamp': signal.timestamp,
                        'symbol': symbol,
                        'action': 'SELL',
                        'quantity': quantity,
                        'price': current_price,
                        'value': proceeds,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'reasoning': signal.reasoning
                    }

                    self.trades.append(trade)
                    return trade

        return None

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算投资组合总价值"""
        total_value = self.portfolio['cash']

        for symbol, quantity in self.portfolio['positions'].items():
            if quantity > 0 and symbol in current_prices:
                total_value += quantity * current_prices[symbol]

        return total_value

    def get_performance_metrics(self) -> Dict:
        """计算性能指标"""
        if not self.equity_curve:
            return {}

        equity_series = pd.Series(self.equity_curve)
        returns = equity_series.pct_change().dropna()

        # 总收益
        total_return = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0]

        # 年化收益
        n_days = len(equity_series)
        years = n_days / 252
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 最大回撤
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_drawdown = drawdown.min()

        # 波动率
        volatility = returns.std() * np.sqrt(252)

        # 夏普比率
        excess_returns = returns - self.risk_free_rate / 252
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        # 交易统计
        if self.trades:
            trades_with_pnl = [t for t in self.trades if 'pnl' in t]
            if trades_with_pnl:
                winning_trades = [t for t in trades_with_pnl if t['pnl'] > 0]
                win_rate = len(winning_trades) / len(trades_with_pnl)

                total_wins = sum(t['pnl'] for t in winning_trades)
                total_losses = abs(sum(t['pnl'] for t in trades_with_pnl if t['pnl'] < 0))
                profit_factor = total_wins / total_losses if total_losses > 0 else 0
            else:
                win_rate = 0
                profit_factor = 0
        else:
            win_rate = 0
            profit_factor = 0

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'final_equity': equity_series.iloc[-1],
        }


# 使用示例
if __name__ == "__main__":
    print("Enhanced Trading Strategy initialized")
    print("Features:")
    print("  ✓ 100+ Alpha Factors")
    print("  ✓ Market Regime Detection (6 types)")
    print("  ✓ Dynamic Risk Management")
    print("  ✓ Stop-Loss & Take-Profit")
    print("  ✓ Factor-based Stock Selection")
