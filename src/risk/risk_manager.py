"""
Risk Management System
风险管理系统 - 生产级实现

Research-grade implementation (Under Development)
Implements comprehensive risk controls for trading decisions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger
import numpy as np
import pandas as pd


class RiskCheckResult(Enum):
    """风险检查结果"""
    APPROVED = "approved"  # 通过风险检查
    REJECTED = "rejected"  # 未通过风险检查
    ADJUSTED = "adjusted"  # 调整后通过


@dataclass
class RiskMetrics:
    """风险指标"""
    portfolio_var_95: float  # 95% VaR
    portfolio_var_99: float  # 99% VaR
    max_drawdown: float  # 最大回撤
    current_drawdown: float  # 当前回撤
    position_concentration: dict[str, float]  # 仓位集中度
    leverage: float  # 杠杆率
    sharpe_ratio: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskLimit:
    """风险限制"""
    max_position_size: float = 0.2  # 单个仓位最大占比 (20%)
    max_sector_concentration: float = 0.4  # 单个行业最大占比 (40%)
    max_portfolio_var_95: float = 0.05  # 组合最大VaR 95% (5%)
    max_drawdown: float = 0.15  # 最大回撤限制 (15%)
    max_leverage: float = 1.0  # 最大杠杆率
    min_cash_reserve: float = 0.1  # 最小现金储备 (10%)
    stop_loss_pct: float = 0.08  # 止损百分比 (8%)


@dataclass
class RiskAdjustment:
    """风险调整结果"""
    original_size: float
    adjusted_size: float
    adjustment_reason: str
    risk_score: float  # 0-1, 越高风险越大
    warnings: list[str] = field(default_factory=list)


class VaRCalculator:
    """VaR（风险价值）计算器"""

    @staticmethod
    def historical_var(
        returns: np.ndarray,
        confidence_level: float = 0.95,
        horizon_days: int = 1
    ) -> float:
        """
        历史模拟法计算VaR

        Args:
            returns: 历史收益率序列
            confidence_level: 置信水平 (0.95 or 0.99)
            horizon_days: 持有期（天）

        Returns:
            VaR值（正数表示潜在损失）
        """
        if len(returns) == 0:
            return 0.0

        # 计算分位数
        percentile = (1 - confidence_level) * 100
        var = -np.percentile(returns, percentile)

        # 调整为指定持有期
        var_horizon = var * np.sqrt(horizon_days)

        return float(var_horizon)

    @staticmethod
    def parametric_var(
        returns: np.ndarray,
        confidence_level: float = 0.95,
        horizon_days: int = 1
    ) -> float:
        """
        参数法（正态分布假设）计算VaR

        Args:
            returns: 历史收益率序列
            confidence_level: 置信水平
            horizon_days: 持有期

        Returns:
            VaR值
        """
        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Z分数
        from scipy import stats
        z_score = stats.norm.ppf(1 - confidence_level)

        # VaR计算
        var = -(mean_return + z_score * std_return)
        var_horizon = var * np.sqrt(horizon_days)

        return float(var_horizon)


class RiskManager:
    """
    风险管理器
    集成VaR、止损、仓位限制、集中度检查
    """

    def __init__(
        self,
        risk_limits: RiskLimit | None = None,
        var_lookback_days: int = 252,  # 1年
        var_method: str = "historical"  # 'historical' or 'parametric'
    ):
        self.risk_limits = risk_limits or RiskLimit()
        self.var_lookback_days = var_lookback_days
        self.var_method = var_method
        self.var_calculator = VaRCalculator()

        # 风险检查历史
        self.check_history: list[dict] = []

        logger.info(f"RiskManager initialized with limits: {self.risk_limits}")

    def calculate_portfolio_var(
        self,
        portfolio_returns: pd.Series,
        confidence_level: float = 0.95
    ) -> float:
        """
        计算组合VaR

        Args:
            portfolio_returns: 组合历史收益率
            confidence_level: 置信水平

        Returns:
            VaR值
        """
        if len(portfolio_returns) == 0:
            return 0.0

        # 使用最近的数据
        recent_returns = portfolio_returns.iloc[-self.var_lookback_days:].values

        if self.var_method == "historical":
            var = self.var_calculator.historical_var(recent_returns, confidence_level)
        else:
            var = self.var_calculator.parametric_var(recent_returns, confidence_level)

        return var

    def calculate_position_risk(
        self,
        symbol: str,
        price_history: pd.Series,
        position_size: float,
        portfolio_value: float
    ) -> dict[str, float]:
        """
        计算单个仓位的风险指标

        Args:
            symbol: 股票代码
            price_history: 价格历史
            position_size: 拟议仓位大小（金额）
            portfolio_value: 组合总价值

        Returns:
            风险指标字典
        """
        # 计算收益率
        returns = price_history.pct_change().dropna()

        if len(returns) < 20:
            logger.warning(f"{symbol}: Insufficient price history for risk calculation")
            return {
                "var_95": 0.0,
                "var_99": 0.0,
                "volatility": 0.0,
                "position_pct": position_size / portfolio_value if portfolio_value > 0 else 0
            }

        recent_returns = returns.iloc[-self.var_lookback_days:].values

        var_95 = self.var_calculator.historical_var(recent_returns, 0.95)
        var_99 = self.var_calculator.historical_var(recent_returns, 0.99)
        volatility = float(np.std(recent_returns) * np.sqrt(252))  # 年化波动率

        return {
            "var_95": var_95,
            "var_99": var_99,
            "volatility": volatility,
            "position_pct": position_size / portfolio_value if portfolio_value > 0 else 0
        }

    def check_position_limits(
        self,
        symbol: str,
        proposed_size: float,
        current_positions: dict[str, float],
        portfolio_value: float,
        price_history: pd.Series | None = None
    ) -> tuple[RiskCheckResult, RiskAdjustment]:
        """
        检查仓位限制

        Args:
            symbol: 股票代码
            proposed_size: 拟议仓位金额
            current_positions: 当前持仓 {symbol: value}
            portfolio_value: 组合总价值
            price_history: 价格历史（可选，用于VaR计算）

        Returns:
            (检查结果, 风险调整)
        """
        warnings = []
        risk_score = 0.0

        # 1. 检查单个仓位占比
        position_pct = proposed_size / portfolio_value if portfolio_value > 0 else 0
        if position_pct > self.risk_limits.max_position_size:
            # 调整仓位
            adjusted_size = portfolio_value * self.risk_limits.max_position_size
            warnings.append(
                f"Position size {position_pct:.1%} exceeds limit "
                f"{self.risk_limits.max_position_size:.1%}, adjusted to {adjusted_size:.2f}"
            )
            result = RiskCheckResult.ADJUSTED
            risk_score += 0.3
        else:
            adjusted_size = proposed_size
            result = RiskCheckResult.APPROVED

        # 2. 检查现金储备
        total_positions = sum(current_positions.values()) + adjusted_size
        cash_reserve = (portfolio_value - total_positions) / portfolio_value
        if cash_reserve < self.risk_limits.min_cash_reserve:
            # 进一步调整以保持现金储备
            max_allowed = portfolio_value * (1 - self.risk_limits.min_cash_reserve) - sum(current_positions.values())
            if max_allowed < adjusted_size:
                adjusted_size = max(0, max_allowed)
                warnings.append(
                    f"Adjusted position to maintain {self.risk_limits.min_cash_reserve:.1%} cash reserve"
                )
                result = RiskCheckResult.ADJUSTED
                risk_score += 0.2

        # 3. 如果有价格历史，检查VaR
        if price_history is not None and len(price_history) >= 20:
            position_risk = self.calculate_position_risk(
                symbol, price_history, adjusted_size, portfolio_value
            )
            # 如果波动率过高，进一步降低仓位
            if position_risk["volatility"] > 0.5:  # 年化波动率 > 50%
                adjusted_size *= 0.7  # 降低30%
                warnings.append(f"High volatility {position_risk['volatility']:.1%}, reduced position by 30%")
                result = RiskCheckResult.ADJUSTED
                risk_score += 0.3

        # 4. 检查是否完全拒绝
        if adjusted_size <= 0 or position_pct > self.risk_limits.max_position_size * 1.5:
            result = RiskCheckResult.REJECTED
            adjusted_size = 0
            warnings.append("Position rejected due to excessive risk")
            risk_score = 1.0

        adjustment = RiskAdjustment(
            original_size=proposed_size,
            adjusted_size=adjusted_size,
            adjustment_reason="; ".join(warnings) if warnings else "No adjustment needed",
            risk_score=min(risk_score, 1.0),
            warnings=warnings
        )

        # 记录检查历史
        self.check_history.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "result": result.value,
            "original_size": proposed_size,
            "adjusted_size": adjusted_size,
            "risk_score": risk_score
        })

        return result, adjustment

    def check_concentration_risk(
        self,
        positions: dict[str, float],
        sectors: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        检查集中度风险

        Args:
            positions: 持仓 {symbol: value}
            sectors: 行业映射 {symbol: sector}

        Returns:
            集中度分析结果
        """
        if not positions:
            return {
                "total_value": 0,
                "position_count": 0,
                "max_position_pct": 0,
                "herfindahl_index": 0,
                "concentration_warnings": []
            }

        total_value = sum(positions.values())
        position_count = len(positions)

        # 计算各仓位占比
        position_pcts = {sym: val / total_value for sym, val in positions.items()}

        # 最大单一仓位
        max_position_pct = max(position_pcts.values())

        # Herfindahl指数（集中度指标，0-1，越高越集中）
        herfindahl_index = sum(pct ** 2 for pct in position_pcts.values())

        warnings = []

        # 检查单个仓位集中度
        if max_position_pct > self.risk_limits.max_position_size:
            warnings.append(
                f"Max position concentration {max_position_pct:.1%} "
                f"exceeds limit {self.risk_limits.max_position_size:.1%}"
            )

        # 检查行业集中度
        sector_concentration = {}
        if sectors:
            for symbol, value in positions.items():
                sector = sectors.get(symbol, "Unknown")
                sector_concentration[sector] = sector_concentration.get(sector, 0) + value

            for sector, value in sector_concentration.items():
                sector_pct = value / total_value
                if sector_pct > self.risk_limits.max_sector_concentration:
                    warnings.append(
                        f"Sector '{sector}' concentration {sector_pct:.1%} "
                        f"exceeds limit {self.risk_limits.max_sector_concentration:.1%}"
                    )

        return {
            "total_value": total_value,
            "position_count": position_count,
            "max_position_pct": max_position_pct,
            "herfindahl_index": herfindahl_index,
            "sector_concentration": sector_concentration if sectors else {},
            "concentration_warnings": warnings,
            "is_concentrated": len(warnings) > 0
        }

    def check_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        current_price: float
    ) -> tuple[bool, float]:
        """
        检查止损

        Args:
            symbol: 股票代码
            entry_price: 入场价格
            current_price: 当前价格

        Returns:
            (是否触发止损, 损失百分比)
        """
        if entry_price <= 0:
            return False, 0.0

        loss_pct = (current_price - entry_price) / entry_price

        triggered = loss_pct <= -self.risk_limits.stop_loss_pct

        if triggered:
            logger.warning(
                f"{symbol} stop loss triggered: "
                f"entry={entry_price:.2f}, current={current_price:.2f}, "
                f"loss={loss_pct:.2%}"
            )

        return triggered, loss_pct

    def get_risk_metrics(
        self,
        portfolio_value: float,
        positions: dict[str, float],
        portfolio_returns: pd.Series | None = None,
        peak_value: float | None = None
    ) -> RiskMetrics:
        """
        获取完整的风险指标

        Args:
            portfolio_value: 组合当前价值
            positions: 持仓
            portfolio_returns: 组合收益率序列
            peak_value: 历史最高价值

        Returns:
            风险指标
        """
        # VaR计算
        var_95 = 0.0
        var_99 = 0.0
        if portfolio_returns is not None and len(portfolio_returns) > 0:
            var_95 = self.calculate_portfolio_var(portfolio_returns, 0.95)
            var_99 = self.calculate_portfolio_var(portfolio_returns, 0.99)

        # 回撤计算
        current_drawdown = 0.0
        max_drawdown = 0.0
        if peak_value and peak_value > 0:
            current_drawdown = (peak_value - portfolio_value) / peak_value
            max_drawdown = current_drawdown  # 简化，实际应跟踪历史最大回撤

        # 集中度
        concentration = self.check_concentration_risk(positions)

        # 杠杆率
        total_positions = sum(positions.values())
        leverage = total_positions / portfolio_value if portfolio_value > 0 else 0.0

        # Sharpe ratio（如果有收益率数据）
        sharpe_ratio = None
        if portfolio_returns is not None and len(portfolio_returns) > 20:
            mean_return = portfolio_returns.mean()
            std_return = portfolio_returns.std()
            if std_return > 0:
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252)  # 年化

        return RiskMetrics(
            portfolio_var_95=var_95,
            portfolio_var_99=var_99,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            position_concentration=concentration,
            leverage=leverage,
            sharpe_ratio=sharpe_ratio
        )

    def validate_trade(
        self,
        symbol: str,
        action: str,  # 'BUY' or 'SELL'
        proposed_size: float,
        current_price: float,
        portfolio_value: float,
        current_positions: dict[str, float],
        price_history: pd.Series | None = None,
        entry_prices: dict[str, float] | None = None
    ) -> tuple[bool, RiskAdjustment | None]:
        """
        验证交易（综合风险检查）

        Args:
            symbol: 股票代码
            action: 交易动作
            proposed_size: 拟议交易金额
            current_price: 当前价格
            portfolio_value: 组合价值
            current_positions: 当前持仓
            price_history: 价格历史
            entry_prices: 入场价格

        Returns:
            (是否批准, 风险调整)
        """
        # 卖出操作：检查止损
        if action == "SELL" and symbol in current_positions:
            if entry_prices and symbol in entry_prices:
                stop_loss_triggered, loss_pct = self.check_stop_loss(
                    symbol, entry_prices[symbol], current_price
                )
                if stop_loss_triggered:
                    logger.info(f"{symbol} approved for sale due to stop loss: {loss_pct:.2%}")
                    return True, None

        # 买入操作：检查仓位限制
        if action == "BUY":
            result, adjustment = self.check_position_limits(
                symbol, proposed_size, current_positions, portfolio_value, price_history
            )

            if result == RiskCheckResult.REJECTED:
                logger.warning(f"{symbol} trade rejected: {adjustment.adjustment_reason}")
                return False, adjustment
            if result == RiskCheckResult.ADJUSTED:
                logger.info(f"{symbol} trade adjusted: {adjustment.adjustment_reason}")
                return True, adjustment
            return True, adjustment

        # 默认批准
        return True, None

    def get_check_history_summary(self) -> dict[str, Any]:
        """获取检查历史摘要"""
        if not self.check_history:
            return {
                "total_checks": 0,
                "approved": 0,
                "adjusted": 0,
                "rejected": 0,
                "avg_risk_score": 0.0
            }

        total = len(self.check_history)
        approved = sum(1 for c in self.check_history if c["result"] == "approved")
        adjusted = sum(1 for c in self.check_history if c["result"] == "adjusted")
        rejected = sum(1 for c in self.check_history if c["result"] == "rejected")
        avg_risk_score = np.mean([c["risk_score"] for c in self.check_history])

        return {
            "total_checks": total,
            "approved": approved,
            "adjusted": adjusted,
            "rejected": rejected,
            "avg_risk_score": float(avg_risk_score),
            "approval_rate": approved / total if total > 0 else 0,
            "adjustment_rate": adjusted / total if total > 0 else 0,
            "rejection_rate": rejected / total if total > 0 else 0
        }
