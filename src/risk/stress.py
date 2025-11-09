"""
压力测试引擎
模拟极端市场情景
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np


class ScenarioType(Enum):
    """情景类型"""
    HISTORICAL = "historical"  # 历史情景
    HYPOTHETICAL = "hypothetical"  # 假设情景
    SENSITIVITY = "sensitivity"  # 敏感性分析
    REVERSE = "reverse"  # 逆向压力测试


class CrisisEvent(Enum):
    """历史危机事件"""
    BLACK_MONDAY_1987 = "black_monday_1987"  # 黑色星期一
    DOT_COM_BUBBLE_2000 = "dot_com_bubble_2000"  # 互联网泡沫
    FINANCIAL_CRISIS_2008 = "financial_crisis_2008"  # 金融危机
    FLASH_CRASH_2010 = "flash_crash_2010"  # 闪电崩盘
    COVID_CRASH_2020 = "covid_crash_2020"  # 新冠崩盘
    CUSTOM = "custom"  # 自定义


@dataclass
class MarketShock:
    """市场冲击"""
    equity_shock: float  # 股票冲击（百分比变化）
    volatility_shock: float  # 波动率冲击（乘数）
    correlation_shock: float  # 相关性冲击（变化量）
    liquidity_shock: float  # 流动性冲击（买卖价差倍数）
    duration_days: int = 1  # 持续天数


@dataclass
class StressScenario:
    """压力情景"""
    scenario_id: str
    name: str
    description: str
    scenario_type: ScenarioType
    market_shocks: dict[str, MarketShock]  # {asset: shock}
    probability: float | None = None  # 发生概率
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class StressTestResult:
    """压力测试结果"""
    scenario: StressScenario
    initial_portfolio_value: float
    stressed_portfolio_value: float
    loss: float
    loss_percentage: float
    position_losses: dict[str, float]  # 各持仓的损失
    risk_metrics: dict[str, float]  # 风险指标
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def survived(self) -> bool:
        """是否存活（损失不超过50%）"""
        return self.loss_percentage > -50.0


class StressTestEngine:
    """压力测试引擎"""

    def __init__(self):
        """初始化压力测试引擎"""
        self.scenarios: dict[str, StressScenario] = {}
        self.historical_scenarios = self._create_historical_scenarios()
        self.test_results: list[StressTestResult] = []

    def _create_historical_scenarios(self) -> dict[str, StressScenario]:
        """创建历史情景"""
        scenarios = {}

        # 1987年黑色星期一
        scenarios[CrisisEvent.BLACK_MONDAY_1987.value] = StressScenario(
            scenario_id="black_monday_1987",
            name="1987年黑色星期一",
            description="道琼斯指数单日暴跌22.6%",
            scenario_type=ScenarioType.HISTORICAL,
            market_shocks={
                "SPY": MarketShock(
                    equity_shock=-0.226,
                    volatility_shock=5.0,
                    correlation_shock=0.3,
                    liquidity_shock=3.0,
                    duration_days=1
                )
            },
            probability=0.001
        )

        # 2000年互联网泡沫破裂
        scenarios[CrisisEvent.DOT_COM_BUBBLE_2000.value] = StressScenario(
            scenario_id="dot_com_bubble_2000",
            name="2000年互联网泡沫",
            description="纳斯达克累计下跌78%",
            scenario_type=ScenarioType.HISTORICAL,
            market_shocks={
                "QQQ": MarketShock(
                    equity_shock=-0.78,
                    volatility_shock=2.5,
                    correlation_shock=0.2,
                    liquidity_shock=2.0,
                    duration_days=900
                ),
                "SPY": MarketShock(
                    equity_shock=-0.49,
                    volatility_shock=1.8,
                    correlation_shock=0.15,
                    liquidity_shock=1.5,
                    duration_days=900
                )
            },
            probability=0.01
        )

        # 2008年金融危机
        scenarios[CrisisEvent.FINANCIAL_CRISIS_2008.value] = StressScenario(
            scenario_id="financial_crisis_2008",
            name="2008年金融危机",
            description="标普500下跌57%，金融股重创",
            scenario_type=ScenarioType.HISTORICAL,
            market_shocks={
                "SPY": MarketShock(
                    equity_shock=-0.57,
                    volatility_shock=4.0,
                    correlation_shock=0.4,
                    liquidity_shock=5.0,
                    duration_days=517
                ),
                "XLF": MarketShock(  # 金融板块
                    equity_shock=-0.82,
                    volatility_shock=6.0,
                    correlation_shock=0.5,
                    liquidity_shock=10.0,
                    duration_days=517
                )
            },
            probability=0.02
        )

        # 2010年闪电崩盘
        scenarios[CrisisEvent.FLASH_CRASH_2010.value] = StressScenario(
            scenario_id="flash_crash_2010",
            name="2010年闪电崩盘",
            description="36分钟内暴跌9%",
            scenario_type=ScenarioType.HISTORICAL,
            market_shocks={
                "SPY": MarketShock(
                    equity_shock=-0.09,
                    volatility_shock=10.0,
                    correlation_shock=0.6,
                    liquidity_shock=20.0,
                    duration_days=0.025  # 36分钟
                )
            },
            probability=0.005
        )

        # 2020年新冠崩盘
        scenarios[CrisisEvent.COVID_CRASH_2020.value] = StressScenario(
            scenario_id="covid_crash_2020",
            name="2020年新冠崩盘",
            description="标普500一个月内下跌34%",
            scenario_type=ScenarioType.HISTORICAL,
            market_shocks={
                "SPY": MarketShock(
                    equity_shock=-0.34,
                    volatility_shock=5.0,
                    correlation_shock=0.35,
                    liquidity_shock=4.0,
                    duration_days=33
                )
            },
            probability=0.02
        )

        return scenarios

    def create_hypothetical_scenario(
        self,
        scenario_id: str,
        name: str,
        description: str,
        market_shocks: dict[str, MarketShock],
        probability: float | None = None
    ) -> StressScenario:
        """创建假设情景"""
        scenario = StressScenario(
            scenario_id=scenario_id,
            name=name,
            description=description,
            scenario_type=ScenarioType.HYPOTHETICAL,
            market_shocks=market_shocks,
            probability=probability
        )

        self.scenarios[scenario_id] = scenario
        return scenario

    def create_sensitivity_scenario(
        self,
        factor: str,
        shock_levels: list[float]
    ) -> list[StressScenario]:
        """
        创建敏感性分析情景

        Args:
            factor: 因子名称（如'equity', 'volatility'）
            shock_levels: 冲击水平列表

        Returns:
            情景列表
        """
        scenarios = []

        for level in shock_levels:
            scenario_id = f"sensitivity_{factor}_{level}"

            if factor == "equity":
                shock = MarketShock(
                    equity_shock=level,
                    volatility_shock=1.0,
                    correlation_shock=0.0,
                    liquidity_shock=1.0
                )
            elif factor == "volatility":
                shock = MarketShock(
                    equity_shock=0.0,
                    volatility_shock=level,
                    correlation_shock=0.0,
                    liquidity_shock=1.0
                )
            elif factor == "correlation":
                shock = MarketShock(
                    equity_shock=0.0,
                    volatility_shock=1.0,
                    correlation_shock=level,
                    liquidity_shock=1.0
                )
            else:
                raise ValueError(f"Unknown factor: {factor}")

            scenario = StressScenario(
                scenario_id=scenario_id,
                name=f"{factor}敏感性: {level}",
                description=f"{factor}变化{level}的影响",
                scenario_type=ScenarioType.SENSITIVITY,
                market_shocks={"default": shock}
            )

            scenarios.append(scenario)
            self.scenarios[scenario_id] = scenario

        return scenarios

    def run_stress_test(
        self,
        scenario: StressScenario,
        portfolio: dict[str, dict],
        market_data: dict[str, dict]
    ) -> StressTestResult:
        """
        运行压力测试

        Args:
            scenario: 压力情景
            portfolio: 投资组合 {symbol: {'quantity': int, 'price': float}}
            market_data: 市场数据 {symbol: {'price': float, 'volatility': float}}

        Returns:
            压力测试结果
        """
        # 计算初始投资组合价值
        initial_value = sum(
            pos["quantity"] * pos["price"]
            for pos in portfolio.values()
        )

        # 计算压力后的投资组合价值
        stressed_value = 0.0
        position_losses = {}

        for symbol, position in portfolio.items():
            current_price = position["price"]
            quantity = position["quantity"]

            # 获取市场冲击（如果有特定的，否则使用默认）
            if symbol in scenario.market_shocks:
                shock = scenario.market_shocks[symbol]
            elif "default" in scenario.market_shocks:
                shock = scenario.market_shocks["default"]
            else:
                # 使用通用冲击（SPY）
                shock = scenario.market_shocks.get(
                    "SPY",
                    MarketShock(0, 1.0, 0, 1.0)
                )

            # 应用股票冲击
            stressed_price = current_price * (1 + shock.equity_shock)

            # 应用流动性冲击（买卖价差扩大）
            if shock.liquidity_shock > 1.0:
                # 假设卖出时需要承受额外的价差成本
                spread_cost = current_price * 0.001 * (shock.liquidity_shock - 1.0)
                stressed_price -= spread_cost

            # 计算持仓价值
            position_value = quantity * stressed_price
            stressed_value += position_value

            # 记录持仓损失
            position_loss = position_value - (quantity * current_price)
            position_losses[symbol] = position_loss

        # 计算总损失
        total_loss = stressed_value - initial_value
        loss_percentage = (total_loss / initial_value * 100) if initial_value > 0 else 0

        # 计算风险指标
        risk_metrics = self._calculate_risk_metrics(
            scenario,
            initial_value,
            stressed_value,
            portfolio,
            market_data
        )

        result = StressTestResult(
            scenario=scenario,
            initial_portfolio_value=initial_value,
            stressed_portfolio_value=stressed_value,
            loss=total_loss,
            loss_percentage=loss_percentage,
            position_losses=position_losses,
            risk_metrics=risk_metrics
        )

        # 保存结果
        self.test_results.append(result)

        return result

    def _calculate_risk_metrics(
        self,
        scenario: StressScenario,
        initial_value: float,
        stressed_value: float,
        portfolio: dict,
        market_data: dict
    ) -> dict[str, float]:
        """计算风险指标"""

        # 最大回撤
        max_drawdown = (initial_value - stressed_value) / initial_value if initial_value > 0 else 0

        # 风险集中度（最大持仓占比）
        position_values = {
            symbol: pos["quantity"] * pos["price"]
            for symbol, pos in portfolio.items()
        }
        max_position = max(position_values.values()) if position_values else 0
        concentration = max_position / initial_value if initial_value > 0 else 0

        # 平均冲击
        avg_shock = np.mean([
            shock.equity_shock
            for shock in scenario.market_shocks.values()
        ])

        return {
            "max_drawdown": max_drawdown,
            "concentration": concentration,
            "avg_shock": avg_shock,
            "num_positions": len(portfolio),
            "diversification_ratio": 1.0 / np.sqrt(len(portfolio)) if len(portfolio) > 0 else 0
        }

    def run_multiple_scenarios(
        self,
        portfolio: dict[str, dict],
        market_data: dict[str, dict],
        scenario_ids: list[str] | None = None
    ) -> list[StressTestResult]:
        """
        运行多个情景的压力测试

        Args:
            portfolio: 投资组合
            market_data: 市场数据
            scenario_ids: 情景ID列表（None表示所有）

        Returns:
            测试结果列表
        """
        results = []

        # 选择情景
        if scenario_ids is None:
            # 运行所有历史情景
            scenarios_to_test = list(self.historical_scenarios.values())
        else:
            scenarios_to_test = [
                self.historical_scenarios.get(sid) or self.scenarios.get(sid)
                for sid in scenario_ids
                if sid in self.historical_scenarios or sid in self.scenarios
            ]

        # 运行测试
        for scenario in scenarios_to_test:
            if scenario:
                result = self.run_stress_test(scenario, portfolio, market_data)
                results.append(result)

        return results

    def reverse_stress_test(
        self,
        portfolio: dict[str, dict],
        market_data: dict[str, dict],
        target_loss_percentage: float = -20.0
    ) -> StressScenario:
        """
        逆向压力测试：找到导致目标损失的情景

        Args:
            portfolio: 投资组合
            market_data: 市场数据
            target_loss_percentage: 目标损失百分比

        Returns:
            导致目标损失的情景
        """
        # 二分搜索找到合适的冲击水平
        low, high = -1.0, 0.0
        tolerance = 0.01  # 1%容差

        best_shock = 0.0

        for _ in range(20):  # 最多20次迭代
            mid = (low + high) / 2

            # 创建测试情景
            test_scenario = StressScenario(
                scenario_id="reverse_test",
                name="逆向压力测试",
                description=f"寻找{target_loss_percentage}%损失的情景",
                scenario_type=ScenarioType.REVERSE,
                market_shocks={
                    "default": MarketShock(
                        equity_shock=mid,
                        volatility_shock=1.0 + abs(mid),
                        correlation_shock=abs(mid) * 0.5,
                        liquidity_shock=1.0 + abs(mid) * 2
                    )
                }
            )

            # 运行测试
            result = self.run_stress_test(test_scenario, portfolio, market_data)

            # 检查是否接近目标
            if abs(result.loss_percentage - target_loss_percentage) < tolerance:
                best_shock = mid
                break

            # 调整搜索范围
            if result.loss_percentage > target_loss_percentage:
                # 损失太小，需要更大的负冲击
                high = mid
            else:
                # 损失太大，需要更小的负冲击
                low = mid

            best_shock = mid

        # 创建最终情景
        final_scenario = StressScenario(
            scenario_id="reverse_stress_result",
            name="逆向压力测试结果",
            description=f"导致{target_loss_percentage}%损失的市场冲击: {best_shock:.2%}",
            scenario_type=ScenarioType.REVERSE,
            market_shocks={
                "default": MarketShock(
                    equity_shock=best_shock,
                    volatility_shock=1.0 + abs(best_shock),
                    correlation_shock=abs(best_shock) * 0.5,
                    liquidity_shock=1.0 + abs(best_shock) * 2
                )
            }
        )

        return final_scenario

    def get_worst_case_scenario(
        self,
        results: list[StressTestResult]
    ) -> StressTestResult:
        """获取最坏情景"""
        return min(results, key=lambda r: r.loss_percentage)

    def get_summary_statistics(
        self,
        results: list[StressTestResult]
    ) -> dict[str, float]:
        """获取汇总统计"""
        if not results:
            return {}

        losses = [r.loss for r in results]
        loss_percentages = [r.loss_percentage for r in results]

        return {
            "num_scenarios": len(results),
            "avg_loss": np.mean(losses),
            "max_loss": np.min(losses),  # 最大损失（最小值）
            "median_loss": np.median(losses),
            "avg_loss_percentage": np.mean(loss_percentages),
            "max_loss_percentage": np.min(loss_percentages),
            "num_survived": sum(1 for r in results if r.survived),
            "survival_rate": sum(1 for r in results if r.survived) / len(results)
        }
