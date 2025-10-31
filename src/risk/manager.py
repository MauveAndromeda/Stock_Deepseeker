"""
风险管理器
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


class RiskLevel(Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimit:
    """风险限额"""
    max_position_size: float = 0.10
    max_total_exposure: float = 1.0
    max_sector_exposure: float = 0.30
    max_correlation: float = 0.70
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    max_daily_loss: float = 0.03
    max_weekly_loss: float = 0.10
    max_drawdown: float = 0.20
    var_limit_95: float = 0.05
    circuit_breaker_threshold: float = 0.05


@dataclass
class RiskMetrics:
    """风险指标"""
    current_exposure: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    volatility: float = 0.0
    beta: float = 0.0
    correlation_risk: float = 0.0
    concentration_risk: float = 0.0
    liquidity_risk: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    timestamp: datetime = None


class RiskManager:
    """风险管理器"""
    
    def __init__(
        self,
        initial_capital: float,
        risk_limits: Optional[RiskLimit] = None
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_limits = risk_limits or RiskLimit()
        
        # 历史数据
        self.returns_history: List[float] = []
        self.capital_history: List[float] = [initial_capital]
        self.drawdown_history: List[float] = []
        
        # 当前状态
        self.positions: Dict[str, Any] = {}
        self.daily_pnl: float = 0.0
        self.weekly_pnl: float = 0.0
        self.peak_capital: float = initial_capital
        
        # 风控状态
        self.circuit_breaker_triggered: bool = False
        self.trading_halted: bool = False
        self.risk_events: List[Dict[str, Any]] = []
    
    def check_order_risk(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        portfolio: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """检查订单风险"""
        
        # 1. 检查熔断
        if self.circuit_breaker_triggered:
            return False, "Circuit breaker is active"
        
        # 2. 检查交易暂停
        if self.trading_halted:
            return False, "Trading is halted"
        
        # 3. 检查单个持仓限额
        position_value = quantity * price
        position_pct = position_value / self.current_capital
        
        if position_pct > self.risk_limits.max_position_size:
            return False, f"Position size {position_pct:.2%} exceeds limit {self.risk_limits.max_position_size:.2%}"
        
        # 4. 检查总敞口
        total_exposure = self._calculate_total_exposure(portfolio, symbol, quantity, price, side)
        exposure_pct = total_exposure / self.current_capital
        
        if exposure_pct > self.risk_limits.max_total_exposure:
            return False, f"Total exposure {exposure_pct:.2%} exceeds limit {self.risk_limits.max_total_exposure:.2%}"
        
        # 5. 检查日亏损限额
        if self.daily_pnl < -self.current_capital * self.risk_limits.max_daily_loss:
            return False, f"Daily loss limit exceeded"
        
        # 6. 检查最大回撤
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if current_drawdown > self.risk_limits.max_drawdown:
            return False, f"Max drawdown {current_drawdown:.2%} exceeded"
        
        return True, "Risk check passed"
    
    def update_portfolio_risk(
        self,
        portfolio: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> RiskMetrics:
        """更新投资组合风险"""
        
        # 计算当前资本
        total_value = portfolio.get('total_value', self.current_capital)
        self.current_capital = total_value
        
        # 更新峰值资本
        if total_value > self.peak_capital:
            self.peak_capital = total_value
        
        # 计算收益率
        if len(self.capital_history) > 0:
            returns = (total_value - self.capital_history[-1]) / self.capital_history[-1]
            self.returns_history.append(returns)
        
        self.capital_history.append(total_value)
        
        # 计算风险指标
        metrics = self._calculate_risk_metrics(portfolio, market_data)
        
        # 检查风险级别
        self._check_risk_levels(metrics)
        
        return metrics
    
    def _calculate_risk_metrics(
        self,
        portfolio: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> RiskMetrics:
        """计算风险指标"""
        
        metrics = RiskMetrics(timestamp=datetime.now())
        
        # 当前敞口
        metrics.current_exposure = self._calculate_portfolio_exposure(portfolio)
        
        # VaR
        if len(self.returns_history) >= 30:
            returns = np.array(self.returns_history[-252:])  # 最近一年
            metrics.var_95 = -np.percentile(returns, 5)
            metrics.var_99 = -np.percentile(returns, 1)
            
            # Expected Shortfall
            var_95_threshold = np.percentile(returns, 5)
            losses_beyond_var = returns[returns <= var_95_threshold]
            metrics.expected_shortfall = -np.mean(losses_beyond_var) if len(losses_beyond_var) > 0 else 0
        
        # 夏普比率
        if len(self.returns_history) >= 30:
            returns = np.array(self.returns_history[-252:])
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            metrics.sharpe_ratio = (avg_return / std_return * np.sqrt(252) 
                                   if std_return > 0 else 0)
            
            # 索提诺比率
            downside_returns = returns[returns < 0]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 1e-10
            metrics.sortino_ratio = avg_return / downside_std * np.sqrt(252)
        
        # 最大回撤
        if len(self.capital_history) > 1:
            capital_series = np.array(self.capital_history)
            running_max = np.maximum.accumulate(capital_series)
            drawdowns = (capital_series - running_max) / running_max
            metrics.max_drawdown = abs(np.min(drawdowns))
            metrics.current_drawdown = abs(drawdowns[-1])
        
        # 波动率
        if len(self.returns_history) >= 20:
            returns = np.array(self.returns_history[-252:])
            metrics.volatility = np.std(returns) * np.sqrt(252)
        
        # 集中度风险
        metrics.concentration_risk = self._calculate_concentration_risk(portfolio)
        
        # 相关性风险
        metrics.correlation_risk = self._calculate_correlation_risk(portfolio)
        
        # 流动性风险
        metrics.liquidity_risk = self._calculate_liquidity_risk(portfolio, market_data)
        
        # 综合风险级别
        metrics.risk_level = self._assess_risk_level(metrics)
        
        return metrics
    
    def _calculate_total_exposure(
        self,
        portfolio: Dict[str, Any],
        new_symbol: str,
        new_quantity: int,
        new_price: float,
        side: str
    ) -> float:
        """计算总敞口"""
        total_value = 0.0
        
        # 现有持仓
        for symbol, position in portfolio.get('positions', {}).items():
            total_value += abs(position.get('quantity', 0) * position.get('current_price', 0))
        
        # 新订单
        if side == 'buy':
            total_value += new_quantity * new_price
        else:
            # 卖出订单减少敞口
            existing_qty = portfolio.get('positions', {}).get(new_symbol, {}).get('quantity', 0)
            if existing_qty >= new_quantity:
                total_value -= new_quantity * new_price
        
        return total_value
    
    def _calculate_portfolio_exposure(self, portfolio: Dict[str, Any]) -> float:
        """计算投资组合敞口"""
        total_value = 0.0
        
        for position in portfolio.get('positions', {}).values():
            total_value += abs(position.get('quantity', 0) * position.get('current_price', 0))
        
        return total_value / self.current_capital if self.current_capital > 0 else 0
    
    def _calculate_concentration_risk(self, portfolio: Dict[str, Any]) -> float:
        """计算集中度风险"""
        if not portfolio.get('positions'):
            return 0.0
        
        position_values = []
        for position in portfolio['positions'].values():
            value = position.get('quantity', 0) * position.get('current_price', 0)
            position_values.append(abs(value))
        
        if not position_values:
            return 0.0
        
        total_value = sum(position_values)
        if total_value == 0:
            return 0.0
        
        # 赫芬达尔指数
        hhi = sum((v / total_value) ** 2 for v in position_values)
        
        return hhi
    
    def _calculate_correlation_risk(self, portfolio: Dict[str, Any]) -> float:
        """计算相关性风险"""
        # 简化版：假设相关性为0.5
        return 0.5
    
    def _calculate_liquidity_risk(
        self,
        portfolio: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> float:
        """计算流动性风险"""
        # 基于成交量的流动性评估
        total_risk = 0.0
        count = 0
        
        for symbol, position in portfolio.get('positions', {}).items():
            volume = market_data.get(symbol, {}).get('volume', 1000000)
            position_size = abs(position.get('quantity', 0))
            
            # 流动性风险 = 持仓量 / 日均成交量
            liquidity_risk = position_size / volume if volume > 0 else 1.0
            total_risk += min(1.0, liquidity_risk)
            count += 1
        
        return total_risk / count if count > 0 else 0
    
    def _assess_risk_level(self, metrics: RiskMetrics) -> RiskLevel:
        """评估风险级别"""
        risk_score = 0
        
        # VaR
        if metrics.var_95 > self.risk_limits.var_limit_95:
            risk_score += 3
        elif metrics.var_95 > self.risk_limits.var_limit_95 * 0.7:
            risk_score += 2
        elif metrics.var_95 > self.risk_limits.var_limit_95 * 0.5:
            risk_score += 1
        
        # 回撤
        if metrics.current_drawdown > self.risk_limits.max_drawdown:
            risk_score += 3
        elif metrics.current_drawdown > self.risk_limits.max_drawdown * 0.7:
            risk_score += 2
        elif metrics.current_drawdown > self.risk_limits.max_drawdown * 0.5:
            risk_score += 1
        
        # 波动率
        if metrics.volatility > 0.5:
            risk_score += 2
        elif metrics.volatility > 0.3:
            risk_score += 1
        
        # 集中度
        if metrics.concentration_risk > 0.5:
            risk_score += 2
        elif metrics.concentration_risk > 0.3:
            risk_score += 1
        
        # 判断级别
        if risk_score >= 8:
            return RiskLevel.CRITICAL
        elif risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _check_risk_levels(self, metrics: RiskMetrics):
        """检查风险级别并触发相应动作"""
        
        # 检查熔断
        if metrics.current_drawdown > self.risk_limits.circuit_breaker_threshold:
            if not self.circuit_breaker_triggered:
                self.circuit_breaker_triggered = True
                self.risk_events.append({
                    'type': 'circuit_breaker',
                    'timestamp': datetime.now(),
                    'drawdown': metrics.current_drawdown
                })
        
        # 关键风险级别 - 暂停交易
        if metrics.risk_level == RiskLevel.CRITICAL:
            if not self.trading_halted:
                self.trading_halted = True
                self.risk_events.append({
                    'type': 'trading_halted',
                    'timestamp': datetime.now(),
                    'metrics': metrics
                })
    
    def reset_circuit_breaker(self):
        """重置熔断"""
        self.circuit_breaker_triggered = False
    
    def resume_trading(self):
        """恢复交易"""
        self.trading_halted = False
    
    def get_risk_report(self) -> Dict[str, Any]:
        """生成风险报告"""
        return {
            'current_capital': self.current_capital,
            'initial_capital': self.initial_capital,
            'return_rate': (self.current_capital - self.initial_capital) / self.initial_capital,
            'peak_capital': self.peak_capital,
            'circuit_breaker_triggered': self.circuit_breaker_triggered,
            'trading_halted': self.trading_halted,
            'risk_events': self.risk_events,
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl,
        }
