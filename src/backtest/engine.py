"""
回测引擎核心
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class BacktestMode(Enum):
    """回测模式"""
    VECTORIZED = "vectorized"  # 向量化回测
    EVENT_DRIVEN = "event_driven"  # 事件驱动回测


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str
    end_date: str
    initial_capital: float = 100000
    commission_rate: float = 0.001
    slippage_rate: float = 0.001
    mode: BacktestMode = BacktestMode.EVENT_DRIVEN
    benchmark: str = "SPY"
    
    # 风险参数
    max_position_size: float = 0.2
    stop_loss: float = 0.05
    take_profit: float = 0.15
    
    # 其他
    rebalance_frequency: str = "daily"  # daily, weekly, monthly


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    start_date: datetime
    end_date: datetime
    duration_days: int
    
    # 收益指标
    total_return: float
    annualized_return: float
    cumulative_returns: pd.Series = None
    
    # 风险指标
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # 其他指标
    beta: float = 0.0
    alpha: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    
    # 详细数据
    equity_curve: pd.DataFrame = None
    trades: List[Dict[str, Any]] = field(default_factory=list)
    positions: pd.DataFrame = None
    
    # 与基准对比
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    information_ratio: float = 0.0


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        
        # 回测状态
        self.capital = config.initial_capital
        self.positions: Dict[str, int] = {}
        self.cash = config.initial_capital
        
        # 历史记录
        self.equity_history: List[float] = []
        self.trades: List[Dict[str, Any]] = []
        self.daily_returns: List[float] = []
        
        # 数据
        self.market_data: Optional[pd.DataFrame] = None
        self.benchmark_data: Optional[pd.DataFrame] = None
    
    def load_data(
        self,
        market_data: pd.DataFrame,
        benchmark_data: Optional[pd.DataFrame] = None
    ):
        """加载回测数据"""
        # 确保数据按时间排序
        self.market_data = market_data.sort_index()
        
        if benchmark_data is not None:
            self.benchmark_data = benchmark_data.sort_index()
        
        # 过滤日期范围
        start_date = pd.to_datetime(self.config.start_date)
        end_date = pd.to_datetime(self.config.end_date)
        
        self.market_data = self.market_data[
            (self.market_data.index >= start_date) &
            (self.market_data.index <= end_date)
        ]
        
        if self.benchmark_data is not None:
            self.benchmark_data = self.benchmark_data[
                (self.benchmark_data.index >= start_date) &
                (self.benchmark_data.index <= end_date)
            ]
    
    def run(
        self,
        strategy: Callable,
        **strategy_params
    ) -> BacktestResult:
        """运行回测"""
        
        if self.market_data is None:
            raise ValueError("Market data not loaded")
        
        # 重置状态
        self._reset_state()
        
        # 根据模式选择回测方法
        if self.config.mode == BacktestMode.VECTORIZED:
            return self._run_vectorized(strategy, **strategy_params)
        else:
            return self._run_event_driven(strategy, **strategy_params)
    
    def _run_event_driven(
        self,
        strategy: Callable,
        **strategy_params
    ) -> BacktestResult:
        """事件驱动回测"""
        
        # 遍历每个交易日
        for timestamp, row in self.market_data.iterrows():
            # 构造当前市场数据
            current_data = {
                'timestamp': timestamp,
                'open': row.get('open'),
                'high': row.get('high'),
                'low': row.get('low'),
                'close': row.get('close'),
                'volume': row.get('volume'),
            }
            
            # 策略生成信号
            signals = strategy(current_data, self.positions, **strategy_params)
            
            # 执行信号
            self._execute_signals(signals, current_data)
            
            # 更新账户
            self._update_account(current_data)
            
            # 记录权益
            self.equity_history.append(self.capital)
        
        # 生成回测结果
        return self._generate_result()
    
    def _run_vectorized(
        self,
        strategy: Callable,
        **strategy_params
    ) -> BacktestResult:
        """向量化回测（适用于简单策略）"""
        
        # 计算策略信号
        signals = strategy(self.market_data, **strategy_params)
        
        # 计算收益
        returns = self.market_data['close'].pct_change()
        strategy_returns = signals.shift(1) * returns
        
        # 计算权益曲线
        equity_curve = (1 + strategy_returns).cumprod() * self.config.initial_capital
        self.equity_history = equity_curve.tolist()
        
        return self._generate_result()
    
    def _execute_signals(
        self,
        signals: Dict[str, Any],
        market_data: Dict[str, Any]
    ):
        """执行交易信号"""
        
        for symbol, signal in signals.items():
            action = signal.get('action')
            quantity = signal.get('quantity', 0)
            
            if action == 'buy' and quantity > 0:
                self._execute_buy(symbol, quantity, market_data)
            elif action == 'sell' and quantity > 0:
                self._execute_sell(symbol, quantity, market_data)
    
    def _execute_buy(
        self,
        symbol: str,
        quantity: int,
        market_data: Dict[str, Any]
    ):
        """执行买入"""
        
        price = market_data['close']
        
        # 应用滑点
        execution_price = price * (1 + self.config.slippage_rate)
        
        # 计算成本
        cost = quantity * execution_price
        commission = cost * self.config.commission_rate
        total_cost = cost + commission
        
        # 检查资金
        if total_cost > self.cash:
            return
        
        # 更新持仓
        current_position = self.positions.get(symbol, 0)
        self.positions[symbol] = current_position + quantity
        
        # 更新现金
        self.cash -= total_cost
        
        # 记录交易
        self.trades.append({
            'timestamp': market_data['timestamp'],
            'symbol': symbol,
            'action': 'buy',
            'quantity': quantity,
            'price': execution_price,
            'commission': commission,
            'total_cost': total_cost
        })
    
    def _execute_sell(
        self,
        symbol: str,
        quantity: int,
        market_data: Dict[str, Any]
    ):
        """执行卖出"""
        
        # 检查持仓
        current_position = self.positions.get(symbol, 0)
        if current_position < quantity:
            quantity = current_position
        
        if quantity <= 0:
            return
        
        price = market_data['close']
        
        # 应用滑点
        execution_price = price * (1 - self.config.slippage_rate)
        
        # 计算收入
        proceeds = quantity * execution_price
        commission = proceeds * self.config.commission_rate
        net_proceeds = proceeds - commission
        
        # 更新持仓
        self.positions[symbol] = current_position - quantity
        if self.positions[symbol] == 0:
            del self.positions[symbol]
        
        # 更新现金
        self.cash += net_proceeds
        
        # 记录交易
        self.trades.append({
            'timestamp': market_data['timestamp'],
            'symbol': symbol,
            'action': 'sell',
            'quantity': quantity,
            'price': execution_price,
            'commission': commission,
            'net_proceeds': net_proceeds
        })
    
    def _update_account(self, market_data: Dict[str, Any]):
        """更新账户状态"""
        
        # 计算持仓市值
        positions_value = 0.0
        for symbol, quantity in self.positions.items():
            price = market_data.get('close', 0)
            positions_value += quantity * price
        
        # 总权益 = 现金 + 持仓市值
        self.capital = self.cash + positions_value
    
    def _generate_result(self) -> BacktestResult:
        """生成回测结果"""
        
        if not self.equity_history:
            raise ValueError("No equity history")
        
        # 计算收益率序列
        equity_series = pd.Series(self.equity_history)
        returns = equity_series.pct_change().dropna()
        
        # 基本指标
        total_return = (self.capital - self.config.initial_capital) / self.config.initial_capital
        
        start_date = pd.to_datetime(self.config.start_date)
        end_date = pd.to_datetime(self.config.end_date)
        duration_days = (end_date - start_date).days
        years = duration_days / 365.25
        
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 风险指标
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        sharpe_ratio = (annualized_return / volatility if volatility > 0 else 0)
        
        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0
        
        # 交易统计
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in self.trades if t.get('pnl', 0) < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            trades=self.trades,
            cumulative_returns=cumulative
        )
        
        return result
    
    def _reset_state(self):
        """重置回测状态"""
        self.capital = self.config.initial_capital
        self.cash = self.config.initial_capital
        self.positions.clear()
        self.equity_history.clear()
        self.trades.clear()
        self.daily_returns.clear()
