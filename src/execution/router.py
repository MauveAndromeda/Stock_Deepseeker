"""
订单路由系统
智能路由订单到不同的执行场所和算法
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np

from src.execution.engine import Order, OrderType, OrderStatus


class ExecutionVenue(Enum):
    """执行场所"""
    NYSE = "NYSE"  # 纽约证券交易所
    NASDAQ = "NASDAQ"  # 纳斯达克
    ARCA = "ARCA"  # NYSE Arca
    BATS = "BATS"  # BATS
    IEX = "IEX"  # IEX
    DARK_POOL = "DARK_POOL"  # 暗池
    INTERNAL = "INTERNAL"  # 内部撮合


class RoutingStrategy(Enum):
    """路由策略"""
    BEST_PRICE = "best_price"  # 最优价格
    BEST_LIQUIDITY = "best_liquidity"  # 最优流动性
    MINIMIZE_IMPACT = "minimize_impact"  # 最小化市场冲击
    SPEED = "speed"  # 最快执行
    SMART = "smart"  # 智能路由
    VWAP = "vwap"  # 成交量加权
    TWAP = "twap"  # 时间加权


@dataclass
class VenueQuote:
    """场所报价"""
    venue: ExecutionVenue
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    latency_ms: float  # 延迟（毫秒）
    fee_per_share: float  # 每股费用
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def spread(self) -> float:
        """价差"""
        return self.ask_price - self.bid_price

    @property
    def mid_price(self) -> float:
        """中间价"""
        return (self.bid_price + self.ask_price) / 2


@dataclass
class RoutingDecision:
    """路由决策"""
    order_id: str
    venue: ExecutionVenue
    algorithm: Optional[str] = None
    estimated_cost: float = 0.0
    estimated_impact: float = 0.0
    confidence: float = 0.8
    reasoning: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class OrderRouter:
    """订单路由器"""

    def __init__(
        self,
        default_strategy: RoutingStrategy = RoutingStrategy.SMART,
        enable_dark_pools: bool = True,
        max_venues: int = 5
    ):
        """
        初始化路由器

        Args:
            default_strategy: 默认路由策略
            enable_dark_pools: 是否启用暗池
            max_venues: 最大路由场所数
        """
        self.default_strategy = default_strategy
        self.enable_dark_pools = enable_dark_pools
        self.max_venues = max_venues

        # 场所配置
        self.venue_configs = self._init_venue_configs()

        # 路由历史
        self.routing_history: List[RoutingDecision] = []

        # 场所性能统计
        self.venue_stats: Dict[ExecutionVenue, Dict[str, float]] = {}

    def _init_venue_configs(self) -> Dict[ExecutionVenue, Dict[str, Any]]:
        """初始化场所配置"""
        configs = {
            ExecutionVenue.NYSE: {
                "fee_per_share": 0.0025,
                "avg_latency_ms": 2.0,
                "min_order_size": 1,
                "max_order_size": 1000000,
                "supports_limit": True,
                "supports_market": True,
            },
            ExecutionVenue.NASDAQ: {
                "fee_per_share": 0.0030,
                "avg_latency_ms": 1.5,
                "min_order_size": 1,
                "max_order_size": 1000000,
                "supports_limit": True,
                "supports_market": True,
            },
            ExecutionVenue.ARCA: {
                "fee_per_share": 0.0020,
                "avg_latency_ms": 2.5,
                "min_order_size": 1,
                "max_order_size": 500000,
                "supports_limit": True,
                "supports_market": True,
            },
            ExecutionVenue.BATS: {
                "fee_per_share": 0.0018,
                "avg_latency_ms": 1.8,
                "min_order_size": 1,
                "max_order_size": 500000,
                "supports_limit": True,
                "supports_market": True,
            },
            ExecutionVenue.IEX: {
                "fee_per_share": 0.0009,
                "avg_latency_ms": 3.0,
                "min_order_size": 1,
                "max_order_size": 100000,
                "supports_limit": True,
                "supports_market": False,
            },
            ExecutionVenue.DARK_POOL: {
                "fee_per_share": 0.0015,
                "avg_latency_ms": 5.0,
                "min_order_size": 100,
                "max_order_size": 1000000,
                "supports_limit": True,
                "supports_market": False,
            },
        }

        return configs

    def route_order(
        self,
        order: Order,
        market_data: Dict,
        strategy: Optional[RoutingStrategy] = None
    ) -> RoutingDecision:
        """
        路由订单

        Args:
            order: 订单
            market_data: 市场数据
            strategy: 路由策略（可选）

        Returns:
            路由决策
        """
        strategy = strategy or self.default_strategy

        # 获取场所报价
        venue_quotes = self._get_venue_quotes(order.symbol, market_data)

        # 根据策略选择场所
        if strategy == RoutingStrategy.BEST_PRICE:
            decision = self._route_best_price(order, venue_quotes)
        elif strategy == RoutingStrategy.BEST_LIQUIDITY:
            decision = self._route_best_liquidity(order, venue_quotes)
        elif strategy == RoutingStrategy.MINIMIZE_IMPACT:
            decision = self._route_minimize_impact(order, venue_quotes)
        elif strategy == RoutingStrategy.SPEED:
            decision = self._route_fastest(order, venue_quotes)
        elif strategy == RoutingStrategy.SMART:
            decision = self._route_smart(order, venue_quotes, market_data)
        else:
            decision = self._route_smart(order, venue_quotes, market_data)

        # 记录路由历史
        self.routing_history.append(decision)

        return decision

    def _get_venue_quotes(
        self,
        symbol: str,
        market_data: Dict
    ) -> List[VenueQuote]:
        """获取各场所报价（模拟）"""
        base_bid = market_data.get('bid', market_data.get('close', 100))
        base_ask = market_data.get('ask', base_bid * 1.001)

        quotes = []

        for venue, config in self.venue_configs.items():
            # 跳过暗池（如果禁用）
            if venue == ExecutionVenue.DARK_POOL and not self.enable_dark_pools:
                continue

            # 模拟价格变化
            bid_variation = np.random.uniform(-0.0005, 0.0005)
            ask_variation = np.random.uniform(-0.0005, 0.0005)

            bid_price = base_bid * (1 + bid_variation)
            ask_price = base_ask * (1 + ask_variation)

            # 模拟流动性
            base_size = market_data.get('volume', 100000) // 100
            bid_size = int(base_size * np.random.uniform(0.8, 1.2))
            ask_size = int(base_size * np.random.uniform(0.8, 1.2))

            quote = VenueQuote(
                venue=venue,
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=bid_size,
                ask_size=ask_size,
                latency_ms=config['avg_latency_ms'] * np.random.uniform(0.9, 1.1),
                fee_per_share=config['fee_per_share']
            )

            quotes.append(quote)

        return quotes

    def _route_best_price(
        self,
        order: Order,
        quotes: List[VenueQuote]
    ) -> RoutingDecision:
        """最优价格路由"""
        if order.side == "buy":
            # 买单：选择最低卖价
            best_quote = min(quotes, key=lambda q: q.ask_price)
            cost = best_quote.ask_price
        else:
            # 卖单：选择最高买价
            best_quote = max(quotes, key=lambda q: q.bid_price)
            cost = best_quote.bid_price

        estimated_cost = cost + best_quote.fee_per_share

        return RoutingDecision(
            order_id=order.order_id,
            venue=best_quote.venue,
            estimated_cost=estimated_cost,
            confidence=0.9,
            reasoning=f"最优价格: {cost:.4f}"
        )

    def _route_best_liquidity(
        self,
        order: Order,
        quotes: List[VenueQuote]
    ) -> RoutingDecision:
        """最优流动性路由"""
        if order.side == "buy":
            # 买单：选择卖方流动性最大
            best_quote = max(quotes, key=lambda q: q.ask_size)
            available_liquidity = best_quote.ask_size
        else:
            # 卖单：选择买方流动性最大
            best_quote = max(quotes, key=lambda q: q.bid_size)
            available_liquidity = best_quote.bid_size

        return RoutingDecision(
            order_id=order.order_id,
            venue=best_quote.venue,
            estimated_cost=best_quote.mid_price + best_quote.fee_per_share,
            confidence=0.85,
            reasoning=f"最优流动性: {available_liquidity} 股"
        )

    def _route_minimize_impact(
        self,
        order: Order,
        quotes: List[VenueQuote]
    ) -> RoutingDecision:
        """最小化市场冲击"""
        # 计算每个场所的预期冲击
        impact_scores = []

        for quote in quotes:
            available = quote.ask_size if order.side == "buy" else quote.bid_size
            # 冲击 = (订单量 / 可用量) * 价差
            if available > 0:
                impact = (order.quantity / available) * quote.spread
            else:
                impact = float('inf')

            impact_scores.append((quote, impact))

        # 选择冲击最小的场所
        best_quote, min_impact = min(impact_scores, key=lambda x: x[1])

        return RoutingDecision(
            order_id=order.order_id,
            venue=best_quote.venue,
            estimated_cost=best_quote.mid_price + best_quote.fee_per_share,
            estimated_impact=min_impact,
            confidence=0.88,
            reasoning=f"最小冲击: {min_impact:.6f}"
        )

    def _route_fastest(
        self,
        order: Order,
        quotes: List[VenueQuote]
    ) -> RoutingDecision:
        """最快执行路由"""
        # 选择延迟最低的场所
        best_quote = min(quotes, key=lambda q: q.latency_ms)

        return RoutingDecision(
            order_id=order.order_id,
            venue=best_quote.venue,
            estimated_cost=best_quote.mid_price + best_quote.fee_per_share,
            confidence=0.92,
            reasoning=f"最快执行: {best_quote.latency_ms:.2f}ms"
        )

    def _route_smart(
        self,
        order: Order,
        quotes: List[VenueQuote],
        market_data: Dict
    ) -> RoutingDecision:
        """智能路由（综合考虑多个因素）"""

        # 计算综合得分
        scores = []

        for quote in quotes:
            # 价格得分（0-1，越低越好）
            if order.side == "buy":
                price_score = 1 - (quote.ask_price - min(q.ask_price for q in quotes)) / (
                    max(q.ask_price for q in quotes) - min(q.ask_price for q in quotes) + 1e-9
                )
            else:
                price_score = (quote.bid_price - min(q.bid_price for q in quotes)) / (
                    max(q.bid_price for q in quotes) - min(q.bid_price for q in quotes) + 1e-9
                )

            # 流动性得分（0-1）
            available = quote.ask_size if order.side == "buy" else quote.bid_size
            max_liquidity = max(
                q.ask_size if order.side == "buy" else q.bid_size for q in quotes
            )
            liquidity_score = available / (max_liquidity + 1e-9)

            # 速度得分（0-1）
            min_latency = min(q.latency_ms for q in quotes)
            max_latency = max(q.latency_ms for q in quotes)
            speed_score = 1 - (quote.latency_ms - min_latency) / (max_latency - min_latency + 1e-9)

            # 成本得分（0-1）
            min_fee = min(q.fee_per_share for q in quotes)
            max_fee = max(q.fee_per_share for q in quotes)
            cost_score = 1 - (quote.fee_per_share - min_fee) / (max_fee - min_fee + 1e-9)

            # 加权综合得分
            weights = {
                'price': 0.4,
                'liquidity': 0.3,
                'speed': 0.15,
                'cost': 0.15
            }

            total_score = (
                price_score * weights['price'] +
                liquidity_score * weights['liquidity'] +
                speed_score * weights['speed'] +
                cost_score * weights['cost']
            )

            scores.append((quote, total_score))

        # 选择得分最高的场所
        best_quote, best_score = max(scores, key=lambda x: x[1])

        return RoutingDecision(
            order_id=order.order_id,
            venue=best_quote.venue,
            estimated_cost=best_quote.mid_price + best_quote.fee_per_share,
            confidence=best_score,
            reasoning=f"智能路由: 综合得分={best_score:.3f}"
        )

    def get_routing_statistics(self) -> Dict[str, Any]:
        """获取路由统计"""
        if not self.routing_history:
            return {}

        venue_counts = {}
        for decision in self.routing_history:
            venue = decision.venue.value
            venue_counts[venue] = venue_counts.get(venue, 0) + 1

        return {
            "total_routes": len(self.routing_history),
            "venue_distribution": venue_counts,
            "avg_confidence": np.mean([d.confidence for d in self.routing_history])
        }
