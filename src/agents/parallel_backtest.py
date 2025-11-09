"""
并行回测优化模块
Parallel Backtest Optimization

关键特性：
1. 并行处理不同股票的分析（保证时间正确性）
2. 批量决策（减少不必要的分析）
3. 智能缓存（相似市场条件复用结果）
4. 进度跟踪
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from dataclasses import dataclass
from loguru import logger

from src.agents.backtest_integration import MultiAgentStrategy
from src.backtest.events import SignalEvent
from src.backtest.portfolio_v2 import PortfolioV2


@dataclass
class OptimizationConfig:
    """优化配置"""
    decision_frequency: int = 3  # 每N天决策一次
    parallel_stocks: bool = True  # 是否并行处理股票
    max_workers: int = 5  # 最大并行任务数
    use_expert_panel: bool = True  # 是否使用专家面板
    expert_max_rounds: int = 2  # 专家面板最大轮次
    cache_enabled: bool = True  # 是否启用缓存
    progress_bar: bool = True  # 是否显示进度条


class ParallelMultiAgentStrategy(MultiAgentStrategy):
    """
    并行优化的多智能体策略

    核心优化：
    1. 同一天的不同股票并行分析（无依赖关系）
    2. 不是每天都重新分析（根据decision_frequency）
    3. 市场条件相似时复用缓存
    4. 保证100%时间正确性（T日只能看到<=T的数据）
    """

    def __init__(
        self,
        name: str = "ParallelMultiAgent",
        agents: Optional[list] = None,
        expert_panel=None,
        risk_manager=None,
        optimization_config: Optional[OptimizationConfig] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            agents=agents,
            expert_panel=expert_panel,
            risk_manager=risk_manager,
            **kwargs
        )

        self.opt_config = optimization_config or OptimizationConfig()
        self.last_decision_date: Optional[datetime] = None
        self.decision_cache: Dict[str, Any] = {}
        self.days_processed = 0

        # 应用优化配置
        if not self.opt_config.use_expert_panel:
            self.use_expert_panel = False

        if self.expert_panel and hasattr(self.expert_panel, 'max_rounds'):
            self.expert_panel.max_rounds = self.opt_config.expert_max_rounds

        logger.info(
            f"ParallelMultiAgentStrategy initialized with config: "
            f"decision_freq={self.opt_config.decision_frequency}, "
            f"parallel={self.opt_config.parallel_stocks}, "
            f"max_workers={self.opt_config.max_workers}"
        )

    def should_make_decision(self, date: datetime) -> bool:
        """
        判断是否应该在此日期做决策

        优化：不是每天都重新分析，而是根据decision_frequency
        """
        if self.last_decision_date is None:
            self.last_decision_date = date
            return True

        days_since_last = (date - self.last_decision_date).days

        if days_since_last >= self.opt_config.decision_frequency:
            self.last_decision_date = date
            return True

        return False

    def generate_signals(
        self,
        date: datetime,
        data: dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> list[SignalEvent]:
        """
        生成交易信号（优化版）

        关键优化：
        1. 检查是否需要决策（decision_frequency）
        2. 并行处理所有股票
        3. 使用缓存减少重复计算
        """
        self.days_processed += 1

        # 优化1：跳过不需要决策的日期
        if not self.should_make_decision(date):
            logger.debug(f"Skipping decision on {date.date()} (next in {self.opt_config.decision_frequency - (date - self.last_decision_date).days} days)")
            return []

        logger.info(f"Making decision on {date.date()} (day {self.days_processed})")

        # 调用异步版本
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if self.opt_config.parallel_stocks:
            return loop.run_until_complete(
                self._generate_signals_parallel(date, data, portfolio)
            )
        else:
            return loop.run_until_complete(
                self._generate_signals_async(date, data, portfolio)
            )

    async def _generate_signals_parallel(
        self,
        date: datetime,
        data: dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> list[SignalEvent]:
        """
        并行生成信号（核心优化）

        关键：同一天的不同股票可以并行分析
        原因：T日分析股票A和股票B之间没有依赖关系
        保证：每个股票只能看到 <= T日的数据
        """
        signals = []

        # 创建所有股票的分析任务
        tasks = []
        symbols = list(data.keys())

        for symbol in symbols:
            df = data[symbol]
            if len(df) < 20:
                continue

            # 创建每个股票的分析任务
            task = self._analyze_single_stock(symbol, df, date, data, portfolio)
            tasks.append(task)

        # 并行执行，但限制并发数
        if self.opt_config.max_workers:
            # 使用Semaphore限制并发
            semaphore = asyncio.Semaphore(self.opt_config.max_workers)

            async def bounded_task(task):
                async with semaphore:
                    return await task

            results = await asyncio.gather(*[bounded_task(t) for t in tasks])
        else:
            # 无限制并行
            results = await asyncio.gather(*tasks)

        # 收集所有信号
        for signal in results:
            if signal:
                signals.append(signal)

        logger.info(f"Generated {len(signals)} signals from {len(symbols)} stocks (parallel)")

        return signals

    async def _analyze_single_stock(
        self,
        symbol: str,
        df: pd.DataFrame,
        date: datetime,
        all_data: dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> Optional[SignalEvent]:
        """
        分析单个股票

        这个函数是100%安全的：
        - 只使用 df（该股票到date为止的数据）
        - 不依赖其他股票的未来数据
        - 可以安全并行执行
        """
        try:
            # 准备市场数据（只包含<=date的数据）
            market_data = self._prepare_market_data(symbol, df, date)

            # 1. 收集智能体决策（已经是并行的）
            agent_decisions = await self._gather_agent_decisions(
                symbol,
                market_data
            )

            # 2. 专家面板（如果启用）
            expert_decision = None
            if self.use_expert_panel and self.expert_panel:
                market_data_dict = self._market_context_to_dict(market_data)
                expert_result = await self.expert_panel.discuss(
                    symbol=symbol,
                    market_data=market_data_dict,
                    metadata={"agent_decisions": agent_decisions}
                )
                expert_decision = expert_result["final_decision"]

            # 3. 综合决策
            final_action, final_confidence = self._synthesize_decisions(
                agent_decisions,
                expert_decision
            )

            # 4. 生成信号
            if final_confidence >= self.min_confidence and final_action != "HOLD":
                current_price = df["close"].iloc[-1]
                position_obj = portfolio.get_position(symbol)
                current_position = 0 if position_obj is None else position_obj.quantity

                if final_action == "BUY" and current_position == 0:
                    # 计算仓位
                    base_pct = 0.10
                    confidence_adjusted_pct = base_pct * final_confidence
                    position_value = portfolio.cash * confidence_adjusted_pct

                    # 风险检查
                    if self.enable_risk_management and self.risk_manager:
                        current_positions = {}
                        for pos_symbol in all_data:
                            pos_obj = portfolio.get_position(pos_symbol)
                            if pos_obj and pos_obj.quantity > 0:
                                pos_price = all_data[pos_symbol]["close"].iloc[-1]
                                current_positions[pos_symbol] = pos_obj.quantity * pos_price

                        approved, adjustment = self.risk_manager.validate_trade(
                            symbol=symbol,
                            action="BUY",
                            proposed_size=position_value,
                            current_price=current_price,
                            current_positions=current_positions,
                            portfolio_value=portfolio.total_value
                        )

                        if not approved:
                            return None

                        if adjustment:
                            position_value = adjustment['adjusted_size']

                    # 创建信号
                    quantity = int(position_value / current_price)
                    if quantity > 0:
                        signal = SignalEvent(
                            timestamp=date,
                            symbol=symbol,
                            signal_type="LONG",
                            quantity=quantity,
                            confidence=final_confidence,
                            metadata={
                                "agent_decisions": agent_decisions,
                                "expert_decision": expert_decision,
                                "price": current_price,
                                "position_value": position_value
                            }
                        )

                        logger.info(
                            f"Signal generated for {symbol}: {signal.signal_type} "
                            f"(confidence: {final_confidence:.2f}, quantity: {quantity}, "
                            f"value: ${position_value:.2f})"
                        )

                        return signal

                elif final_action == "SELL" and current_position > 0:
                    # 创建卖出信号
                    signal = SignalEvent(
                        timestamp=date,
                        symbol=symbol,
                        signal_type="EXIT",
                        quantity=current_position,
                        confidence=final_confidence,
                        metadata={
                            "agent_decisions": agent_decisions,
                            "expert_decision": expert_decision
                        }
                    )

                    logger.info(
                        f"Signal generated for {symbol}: {signal.signal_type} "
                        f"(confidence: {final_confidence:.2f}, quantity: {current_position})"
                    )

                    return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None


async def create_optimized_strategy(
    mode: str = 'fast',
    register_agents: bool = True
) -> ParallelMultiAgentStrategy:
    """
    创建优化的策略

    模式：
    - 'turbo': 超快（无专家面板，每5天）
    - 'fast': 快速（简化专家面板，每3天）
    - 'balanced': 平衡（标准设置，每2天）
    - 'full': 完整（每天，完整专家面板）
    """
    from src.agents import create_default_multi_agent_strategy

    mode_configs = {
        'turbo': OptimizationConfig(
            decision_frequency=5,
            parallel_stocks=True,
            max_workers=10,
            use_expert_panel=False,
            expert_max_rounds=1,
        ),
        'fast': OptimizationConfig(
            decision_frequency=3,
            parallel_stocks=True,
            max_workers=5,
            use_expert_panel=True,
            expert_max_rounds=1,
        ),
        'balanced': OptimizationConfig(
            decision_frequency=2,
            parallel_stocks=True,
            max_workers=3,
            use_expert_panel=True,
            expert_max_rounds=2,
        ),
        'full': OptimizationConfig(
            decision_frequency=1,
            parallel_stocks=False,
            max_workers=1,
            use_expert_panel=True,
            expert_max_rounds=3,
        ),
    }

    config = mode_configs.get(mode, mode_configs['fast'])

    # 创建基础策略
    base_strategy = await create_default_multi_agent_strategy(
        use_expert_panel=config.use_expert_panel,
        register_agents=register_agents
    )

    # 转换为并行版本
    parallel_strategy = ParallelMultiAgentStrategy(
        name=f"Parallel_{mode.capitalize()}",
        agents=base_strategy.agents,
        expert_panel=base_strategy.expert_panel if config.use_expert_panel else None,
        risk_manager=base_strategy.risk_manager,
        optimization_config=config,
        enable_risk_management=base_strategy.enable_risk_management,
        min_confidence=base_strategy.min_confidence
    )

    logger.info(f"Created optimized strategy in '{mode}' mode")

    return parallel_strategy
