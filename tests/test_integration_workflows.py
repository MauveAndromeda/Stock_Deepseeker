"""
Integration Workflow Tests
集成测试 - 完整工作流

Research-grade implementation (Under Development)
Tests complete end-to-end workflows with multi-agent decision making
"""

import asyncio
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.agents import (
    MarketContext,
    create_default_multi_agent_strategy,
    get_agent_registry,
)
from src.backtest.engine_v2 import BacktestConfig, BacktestEngineV2
from src.backtest.portfolio_v2 import PortfolioV2
from src.data.providers.base import PriceData
from src.risk import RiskLimit


class TestCompleteWorkflow:
    """测试完整的多智能体工作流"""

    @pytest.mark.asyncio
    async def test_full_agent_decision_workflow(self):
        """测试完整的智能体决策工作流"""
        # 创建标准化市场环境
        market_context = MarketContext(
            symbol="AAPL",
            timestamp=datetime.now(),
            current_price=150.0,
            price_change_pct=0.02,  # 上涨2%
            volume=1000000,
            technical_indicators={
                "SMA_20": 145.0,
                "SMA_50": 140.0,
                "RSI": 65.0,
                "trend_score": 1.0  # bullish
            },
            fundamentals={"PE_ratio": 25.0},
            sentiment={"score": 0.7}
        )

        # 创建策略
        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=False,  # 简化测试
            register_agents=True
        )

        # 验证智能体已注册
        registry = get_agent_registry()
        assert registry.get_agent_count() > 0

        # 收集决策
        decisions = []
        for agent in strategy.agents:
            decision = await agent.analyze(market_context)
            decisions.append(decision)
            
        # 验证决策结构
        assert len(decisions) > 0
        for decision in decisions:
            assert hasattr(decision, "action")
            assert hasattr(decision, "confidence")
            assert hasattr(decision, "reasoning")
            assert 0 <= decision.confidence <= 1

    @pytest.mark.asyncio  
    async def test_workflow_with_risk_management(self):
        """测试带风险管理的完整工作流"""
        # 创建严格的风险限制
        strict_limits = RiskLimit(
            max_position_size=0.10,  # 最大10%仓位
            max_drawdown=0.08,
            stop_loss_pct=0.05
        )

        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=False,
            register_agents=False
        )
        strategy.risk_manager.risk_limits = strict_limits

        # 模拟组合
        portfolio = PortfolioV2(initial_capital=100000)

        # 生成价格数据
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        prices = pd.DataFrame({
            "open": 100 + np.random.randn(60).cumsum(),
            "high": 105 + np.random.randn(60).cumsum(),
            "low": 95 + np.random.randn(60).cumsum(),
            "close": 100 + np.random.randn(60).cumsum(),
            "volume": np.random.randint(100000, 200000, 60)
        }, index=dates)

        data = {"TEST": prices}

        # 生成信号
        signals = strategy.generate_signals(
            date=dates[-1],
            data=data,
            portfolio=portfolio
        )

        # 验证风险管理生效
        if len(signals) > 0:
            for signal in signals:
                if "risk_adjusted" in signal.metadata:
                    # 如果有风险调整，验证调整的合理性
                    if signal.metadata["risk_adjusted"]:
                        adjustment = signal.metadata["risk_adjustment"]
                        assert adjustment["adjusted_size"] <= adjustment["original_size"]

    def test_no_lookahead_bias(self):
        """验证无前视偏差 - 关键测试"""
        # 创建价格数据
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        
        # 在T=50时有个大涨
        prices = np.ones(100) * 100
        prices[50:] = 150  # T=50后价格跳升到150
        
        df = pd.DataFrame({
            "open": prices,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.ones(100) * 100000
        }, index=dates)

        # 创建策略（无风险管理，简化测试）
        from src.agents.backtest_integration import MultiAgentStrategy
        strategy = MultiAgentStrategy(
            agents=[],
            use_expert_panel=False,
            enable_risk_management=False
        )

        portfolio = PortfolioV2(initial_capital=100000)

        # 在T=49生成信号（大涨前一天）
        # 策略只能看到T<=49的数据
        data_t49 = {"TEST": df.iloc[:50]}  # 只到T=49
        
        market_data = strategy._prepare_market_data("TEST", data_t49["TEST"], dates[49])
        
        # 验证市场数据只包含T=49及之前的信息
        assert market_data.current_price == 100.0  # 应该是100，不是150
        assert market_data.timestamp == dates[49]
        
        # T=49的数据不应该"看到"T=50的大涨
        assert abs(market_data.current_price - 100.0) < 1.0


class TestMarketScenarios:
    """测试各种市场场景"""

    def create_scenario_data(self, scenario_type: str, days: int = 100):
        """创建不同市场场景的数据"""
        dates = pd.date_range("2024-01-01", periods=days, freq="D")
        
        if scenario_type == "bull":
            # 牛市：持续上涨
            trend = np.linspace(0, 30, days)
            noise = np.random.randn(days) * 2
            prices = 100 + trend + noise
            
        elif scenario_type == "bear":
            # 熊市：持续下跌
            trend = np.linspace(0, -30, days)
            noise = np.random.randn(days) * 2
            prices = 100 + trend + noise
            
        elif scenario_type == "volatile":
            # 高波动
            prices = 100 + np.random.randn(days) * 10
            
        elif scenario_type == "crash":
            # 崩盘：前半段正常，后半段暴跌
            prices = np.ones(days) * 100
            prices[:days//2] += np.random.randn(days//2)
            prices[days//2:] = 100 - np.linspace(0, 40, days//2)
            
        else:  # 'sideways'
            # 横盘
            prices = 100 + np.random.randn(days) * 3

        return pd.DataFrame({
            "open": prices,
            "high": prices * 1.03,
            "low": prices * 0.97,
            "close": prices,
            "volume": np.random.randint(50000, 150000, days)
        }, index=dates)

    def test_bull_market_scenario(self):
        """测试牛市场景"""
        df = self.create_scenario_data("bull", 60)
        
        # 验证上涨趋势
        assert df["close"].iloc[-1] > df["close"].iloc[0]
        
        # 计算市场环境
        from src.agents.backtest_integration import MultiAgentStrategy
        strategy = MultiAgentStrategy(agents=[], use_expert_panel=False)
        
        market_ctx = strategy._prepare_market_data("TEST", df, df.index[-1])
        
        # 牛市特征：价格高于均线
        assert market_ctx.technical_indicators["trend_score"] > 0
        
    def test_bear_market_scenario(self):
        """测试熊市场景"""
        df = self.create_scenario_data("bear", 60)
        
        # 验证下跌趋势
        assert df["close"].iloc[-1] < df["close"].iloc[0]
        
        from src.agents.backtest_integration import MultiAgentStrategy
        strategy = MultiAgentStrategy(agents=[], use_expert_panel=False)
        
        market_ctx = strategy._prepare_market_data("TEST", df, df.index[-1])
        
        # 熊市特征
        assert market_ctx.price_change_pct < 0 or market_ctx.technical_indicators["trend_score"] < 0

    def test_crash_scenario(self):
        """测试崩盘场景"""
        df = self.create_scenario_data("crash", 60)
        
        # 验证崩盘：后半段大幅下跌
        first_half_avg = df["close"].iloc[:30].mean()
        second_half_avg = df["close"].iloc[30:].mean()
        decline_pct = (second_half_avg - first_half_avg) / first_half_avg
        assert decline_pct < -0.15  # 下跌超过15%


class TestPerformanceMetrics:
    """测试性能指标跟踪"""

    @pytest.mark.asyncio
    async def test_agent_performance_tracking(self):
        """测试智能体性能跟踪"""
        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=False,
            register_agents=True
        )

        # 每个智能体应该有性能指标
        for agent in strategy.agents:
            metrics = agent.get_performance_metrics()
            assert metrics is not None
            assert hasattr(metrics, "total_decisions")
            assert hasattr(metrics, "avg_confidence")

    def test_risk_manager_history(self):
        """测试风险管理器历史记录"""
        from src.risk import RiskManager
        
        risk_manager = RiskManager()
        
        # 执行几次检查
        for i in range(10):
            risk_manager.check_position_limits(
                symbol=f"TEST{i}",
                proposed_size=15000,
                current_positions={},
                portfolio_value=100000
            )
        
        # 验证历史记录
        summary = risk_manager.get_check_history_summary()
        assert summary["total_checks"] == 10
        assert summary["approval_rate"] + summary["adjustment_rate"] + summary["rejection_rate"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
