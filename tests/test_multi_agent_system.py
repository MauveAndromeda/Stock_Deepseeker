"""
Multi-Agent System Tests
测试多智能体系统的各个组件

Research-grade implementation (Under Development)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.ai.model_unified import ModelRouter, ModelConfig, ModelProvider, ModelTier
from src.agents.enhanced_base import MomentumChaserAgent, ValueSeekerAgent
from src.agents.base import AgentType, Action
from src.agents.langgraph_workflow import ExpertPanelWorkflow
from src.agents.backtest_integration import MultiAgentStrategy, create_default_multi_agent_strategy
from src.backtest.portfolio_v2 import PortfolioV2
from src.data.providers.base import PriceData


class TestMULayer:
    """测试MU（模型统一）层"""

    def test_model_config_creation(self):
        """测试模型配置创建"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            tier=ModelTier.FAST,
            cost_per_1k_tokens=0.00015
        )
        assert config.provider == ModelProvider.OPENAI
        assert config.tier == ModelTier.FAST

    @pytest.mark.asyncio
    async def test_router_initialization(self):
        """测试路由器初始化"""
        router = ModelRouter()
        # 不依赖API密钥也能初始化
        assert router is not None
        assert router.models is not None


class TestEnhancedAgents:
    """测试增强的智能体"""

    @pytest.mark.asyncio
    async def test_agent_creation(self):
        """测试智能体创建"""
        agent = MomentumChaserAgent(
            agent_id="test_momentum",
            agent_type=AgentType.MOMENTUM_CHASER,
            initial_capital=100000
        )
        assert agent.agent_id == "test_momentum"
        assert agent.agent_type == AgentType.MOMENTUM_CHASER

    @pytest.mark.asyncio
    async def test_agent_prompt_template(self):
        """测试prompt模板"""
        agent = ValueSeekerAgent(
            agent_id="test_value",
            agent_type=AgentType.VALUE_SEEKER
        )
        prompt_template = agent._create_prompt_template()
        assert prompt_template is not None
        assert 'value' in prompt_template.template.lower()

    def test_agent_personality(self):
        """测试性格特征"""
        agent = MomentumChaserAgent(
            agent_id="test",
            agent_type=AgentType.MOMENTUM_CHASER
        )
        personality = agent._get_personality_traits()
        assert len(personality) > 0
        assert 'momentum' in personality.lower() or 'aggressive' in personality.lower()


class TestLangGraphWorkflow:
    """测试LangGraph工作流"""

    def test_workflow_creation(self):
        """测试工作流创建"""
        workflow = ExpertPanelWorkflow(max_rounds=2)
        assert workflow.max_rounds == 2
        assert workflow.workflow is not None

    @pytest.mark.asyncio
    async def test_workflow_state(self):
        """测试工作流状态管理"""
        workflow = ExpertPanelWorkflow(max_rounds=1)

        market_data = {
            'price': 150.0,
            'change_pct': 0.02,
            'volume': 1000000
        }

        # 注意：实际运行需要API密钥，这里只测试结构
        # 在没有API密钥的环境中会优雅降级
        try:
            result = await workflow.discuss(
                symbol="TEST",
                market_data=market_data
            )
            # 如果成功，检查结果结构
            assert 'symbol' in result
            assert 'final_decision' in result
        except Exception as e:
            # 预期在没有API密钥时会失败
            assert 'API' in str(e) or 'key' in str(e).lower()


class TestBacktestIntegration:
    """测试回测集成"""

    @pytest.mark.asyncio
    async def test_strategy_creation(self):
        """测试策略创建"""
        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=False  # 禁用以避免API调用
        )
        assert strategy is not None
        assert len(strategy.agents) > 0
        assert strategy.name == "MultiAgent_Default"

    def test_market_data_preparation(self):
        """测试市场数据准备"""
        # 创建模拟数据
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 105,
            'low': np.random.randn(100).cumsum() + 95,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)

        strategy = MultiAgentStrategy(
            name="test",
            agents=[],
            use_expert_panel=False
        )

        market_data = strategy._prepare_market_data(
            symbol="TEST",
            df=df,
            date=dates[-1]
        )

        assert 'symbol' in market_data
        assert 'price' in market_data
        assert 'indicators' in market_data
        assert market_data['symbol'] == "TEST"

    @pytest.mark.asyncio
    async def test_decision_synthesis(self):
        """测试决策综合"""
        strategy = MultiAgentStrategy(
            name="test",
            agents=[],
            use_expert_panel=False,
            consensus_threshold=0.5
        )

        # 模拟智能体决策
        agent_decisions = [
            {'action': 'BUY', 'confidence': 0.8, 'agent_id': 'a1'},
            {'action': 'BUY', 'confidence': 0.7, 'agent_id': 'a2'},
            {'action': 'HOLD', 'confidence': 0.6, 'agent_id': 'a3'}
        ]

        action, confidence = strategy._synthesize_decisions(
            agent_decisions,
            expert_decision=None
        )

        assert action == 'BUY'  # 多数投BUY
        assert confidence > 0


class TestEndToEnd:
    """端到端测试"""

    def generate_mock_price_data(self, symbol: str, days: int = 100) -> PriceData:
        """生成模拟价格数据"""
        dates = pd.bdate_range(end=datetime.now(), periods=days)
        prices = 100 * (1 + np.random.randn(days) * 0.02).cumprod()

        df = pd.DataFrame({
            'open': prices * (1 + np.random.randn(days) * 0.01),
            'high': prices * (1 + np.abs(np.random.randn(days)) * 0.02),
            'low': prices * (1 - np.abs(np.random.randn(days)) * 0.02),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, days)
        }, index=dates)

        return PriceData(
            symbol=symbol,
            data=df,
            start_date=dates[0].to_pydatetime(),
            end_date=dates[-1].to_pydatetime(),
            adjusted=True
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_without_llm(self):
        """测试完整流程（不调用LLM）"""
        # 创建策略（不使用专家面板以避免API调用）
        strategy = MultiAgentStrategy(
            name="test_pipeline",
            agents=[],  # 空智能体列表
            use_expert_panel=False
        )

        # 创建模拟数据
        price_data = self.generate_mock_price_data("TEST", days=60)
        data = {"TEST": price_data.data}

        # 创建组合
        portfolio = PortfolioV2(
            initial_capital=100000,
            commission_rate=0.001,
            slippage_rate=0.0005
        )

        # 生成信号
        signals = await strategy.generate_signals(
            date=price_data.end_date,
            data=data,
            portfolio=portfolio
        )

        # 验证
        assert isinstance(signals, list)
        # 由于没有智能体，应该不生成信号
        assert len(signals) == 0

        # 检查性能总结
        summary = strategy.get_performance_summary()
        assert 'total_signals' in summary
        assert 'decision_count' in summary


# 运行测试的便捷函数
def run_tests():
    """运行所有测试"""
    pytest.main([__file__, '-v', '--tb=short'])


if __name__ == "__main__":
    run_tests()
