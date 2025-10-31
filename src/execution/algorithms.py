"""
高级执行算法
VWAP, TWAP, Implementation Shortfall等
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import numpy as np

from src.execution.engine import Order, OrderType, OrderSide


class AlgorithmType(Enum):
    """算法类型"""
    VWAP = "vwap"  # Volume Weighted Average Price
    TWAP = "twap"  # Time Weighted Average Price
    POV = "pov"  # Percentage of Volume
    IS = "is"  # Implementation Shortfall
    ICEBERG = "iceberg"  # 冰山订单
    SNIPER = "sniper"  # 狙击订单


@dataclass
class AlgorithmConfig:
    """算法配置"""
    algorithm_type: AlgorithmType
    start_time: datetime
    end_time: datetime
    total_quantity: int
    participation_rate: float = 0.1  # 参与率（0-1）
    max_slice_size: Optional[int] = None  # 最大切片大小
    min_slice_size: int = 1  # 最小切片大小
    urgency: float = 0.5  # 紧急度（0-1）
    price_limit: Optional[float] = None  # 价格限制
    randomize: bool = True  # 是否随机化
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlgorithmSlice:
    """算法切片"""
    slice_id: str
    parent_order_id: str
    quantity: int
    target_time: datetime
    limit_price: Optional[float] = None
    status: str = "pending"  # pending, submitted, filled, cancelled
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)


class ExecutionAlgorithm(ABC):
    """执行算法基类"""

    def __init__(self, config: AlgorithmConfig):
        self.config = config
        self.slices: List[AlgorithmSlice] = []
        self.filled_quantity = 0
        self.total_cost = 0.0
        self.start_time = datetime.now()

    @abstractmethod
    def generate_slices(self, market_data: Dict) -> List[AlgorithmSlice]:
        """生成订单切片"""
        pass

    @abstractmethod
    def should_adjust(self, market_data: Dict) -> bool:
        """是否需要调整策略"""
        pass

    def get_completion_rate(self) -> float:
        """获取完成率"""
        return self.filled_quantity / self.config.total_quantity if self.config.total_quantity > 0 else 0

    def get_avg_price(self) -> float:
        """获取平均成交价"""
        return self.total_cost / self.filled_quantity if self.filled_quantity > 0 else 0


class VWAPAlgorithm(ExecutionAlgorithm):
    """
    VWAP算法
    根据历史成交量分布来分配订单
    """

    def __init__(self, config: AlgorithmConfig):
        super().__init__(config)
        self.volume_profile = None

    def generate_slices(self, market_data: Dict) -> List[AlgorithmSlice]:
        """根据成交量曲线生成切片"""

        # 获取历史成交量曲线（如果没有，使用标准U型曲线）
        if 'volume_profile' in market_data:
            self.volume_profile = market_data['volume_profile']
        else:
            self.volume_profile = self._generate_standard_volume_profile()

        # 计算时间间隔
        duration = (self.config.end_time - self.config.start_time).total_seconds()
        num_slices = max(10, int(duration / 60))  # 每分钟一个切片

        slices = []
        remaining_quantity = self.config.total_quantity

        for i in range(num_slices):
            # 计算这个时间段的目标成交量比例
            volume_weight = self.volume_profile[i] if i < len(self.volume_profile) else 1.0

            # 计算切片数量
            if i == num_slices - 1:
                # 最后一个切片，全部剩余
                slice_quantity = remaining_quantity
            else:
                slice_quantity = int(self.config.total_quantity * volume_weight)
                slice_quantity = max(self.config.min_slice_size, slice_quantity)

            # 随机化
            if self.config.randomize:
                slice_quantity = int(slice_quantity * np.random.uniform(0.8, 1.2))

            slice_quantity = min(slice_quantity, remaining_quantity)

            if slice_quantity <= 0:
                continue

            # 计算目标时间
            time_offset = timedelta(seconds=duration * i / num_slices)
            target_time = self.config.start_time + time_offset

            slice = AlgorithmSlice(
                slice_id=f"{self.config.algorithm_type.value}_{i}",
                parent_order_id="vwap_parent",
                quantity=slice_quantity,
                target_time=target_time,
                limit_price=self.config.price_limit
            )

            slices.append(slice)
            remaining_quantity -= slice_quantity

            if remaining_quantity <= 0:
                break

        self.slices = slices
        return slices

    def _generate_standard_volume_profile(self) -> List[float]:
        """生成标准U型成交量曲线"""
        num_intervals = 24  # 一天24个半小时
        profile = []

        for i in range(num_intervals):
            # U型曲线：开盘和收盘时成交量大
            if i < 2 or i >= 22:
                weight = 1.5  # 开盘/收盘高峰
            elif 10 <= i < 14:
                weight = 0.6  # 午间低谷
            else:
                weight = 1.0  # 正常时段

            profile.append(weight)

        # 归一化
        total = sum(profile)
        profile = [w / total for w in profile]

        return profile

    def should_adjust(self, market_data: Dict) -> bool:
        """检查是否需要调整"""
        # 如果价格偏离VWAP过多，可能需要调整
        current_vwap = market_data.get('vwap')
        current_price = market_data.get('close')

        if current_vwap and current_price:
            deviation = abs(current_price - current_vwap) / current_vwap
            return deviation > 0.01  # 1%偏差触发调整

        return False


class TWAPAlgorithm(ExecutionAlgorithm):
    """
    TWAP算法
    在指定时间内均匀分配订单
    """

    def generate_slices(self, market_data: Dict) -> List[AlgorithmSlice]:
        """均匀时间切片"""

        duration = (self.config.end_time - self.config.start_time).total_seconds()
        num_slices = max(5, int(duration / 60))  # 每分钟一个切片

        # 均匀分配数量
        base_quantity = self.config.total_quantity // num_slices
        remainder = self.config.total_quantity % num_slices

        slices = []

        for i in range(num_slices):
            # 计算切片数量
            slice_quantity = base_quantity
            if i < remainder:
                slice_quantity += 1

            # 随机化（±20%）
            if self.config.randomize:
                slice_quantity = int(slice_quantity * np.random.uniform(0.8, 1.2))

            slice_quantity = max(self.config.min_slice_size, slice_quantity)

            # 限制最大切片大小
            if self.config.max_slice_size:
                slice_quantity = min(slice_quantity, self.config.max_slice_size)

            # 计算目标时间
            time_offset = timedelta(seconds=duration * i / num_slices)
            target_time = self.config.start_time + time_offset

            slice = AlgorithmSlice(
                slice_id=f"{self.config.algorithm_type.value}_{i}",
                parent_order_id="twap_parent",
                quantity=slice_quantity,
                target_time=target_time,
                limit_price=self.config.price_limit
            )

            slices.append(slice)

        self.slices = slices
        return slices

    def should_adjust(self, market_data: Dict) -> bool:
        """TWAP通常不需要动态调整"""
        # 除非价格触及限价
        if self.config.price_limit:
            current_price = market_data.get('close')
            if current_price and abs(current_price - self.config.price_limit) / self.config.price_limit < 0.005:
                return True

        return False


class ImplementationShortfall(ExecutionAlgorithm):
    """
    Implementation Shortfall算法
    平衡市场冲击和时间风险
    """

    def __init__(self, config: AlgorithmConfig):
        super().__init__(config)
        self.decision_price = None  # 决策价格
        self.risk_aversion = 1.0 - config.urgency  # 风险厌恶系数

    def generate_slices(self, market_data: Dict) -> List[AlgorithmSlice]:
        """基于Implementation Shortfall最优化生成切片"""

        # 记录决策价格
        if self.decision_price is None:
            self.decision_price = market_data.get('close')

        # 获取市场参数
        volatility = market_data.get('volatility', 0.02)  # 日波动率
        avg_volume = market_data.get('avg_volume', 1000000)  # 平均成交量
        current_volume = market_data.get('volume', avg_volume)

        # 估计价格冲击参数
        # 永久冲击 = gamma * (quantity / daily_volume)
        # 临时冲击 = eta * (rate / instant_volume)
        gamma = 0.5  # 永久冲击系数
        eta = 0.1  # 临时冲击系数

        # 计算最优执行速率
        duration_hours = (self.config.end_time - self.config.start_time).total_seconds() / 3600

        # Almgren-Chriss模型的最优速率
        kappa = np.sqrt(self.risk_aversion * volatility ** 2 / (gamma * eta))
        optimal_duration = kappa * duration_hours

        # 根据紧急度调整
        adjusted_duration = optimal_duration * (2 - self.config.urgency)
        num_slices = max(3, int(adjusted_duration * 10))  # 每0.1小时一个切片

        slices = []
        remaining_quantity = self.config.total_quantity

        for i in range(num_slices):
            # 指数衰减的执行速率
            decay_factor = np.exp(-i / (num_slices * 0.3))
            base_quantity = remaining_quantity * decay_factor * 0.2

            # 调整为整数
            slice_quantity = int(base_quantity)
            slice_quantity = max(self.config.min_slice_size, slice_quantity)

            if self.config.max_slice_size:
                slice_quantity = min(slice_quantity, self.config.max_slice_size)

            # 最后一个切片
            if i == num_slices - 1:
                slice_quantity = remaining_quantity

            slice_quantity = min(slice_quantity, remaining_quantity)

            if slice_quantity <= 0:
                break

            # 计算目标时间
            time_offset = timedelta(seconds=(self.config.end_time - self.config.start_time).total_seconds() * i / num_slices)
            target_time = self.config.start_time + time_offset

            slice = AlgorithmSlice(
                slice_id=f"is_{i}",
                parent_order_id="is_parent",
                quantity=slice_quantity,
                target_time=target_time,
                limit_price=self.config.price_limit
            )

            slices.append(slice)
            remaining_quantity -= slice_quantity

            if remaining_quantity <= 0:
                break

        self.slices = slices
        return slices

    def should_adjust(self, market_data: Dict) -> bool:
        """根据市场变化动态调整"""
        # 如果价格变化超过预期，需要调整
        if self.decision_price:
            current_price = market_data.get('close')
            if current_price:
                price_change = abs(current_price - self.decision_price) / self.decision_price
                # 价格变化超过1%触发调整
                return price_change > 0.01

        return False

    def calculate_shortfall(self, execution_price: float) -> float:
        """计算实施缺口"""
        if self.decision_price:
            return execution_price - self.decision_price
        return 0.0


class POVAlgorithm(ExecutionAlgorithm):
    """
    POV (Percentage of Volume) 算法
    按市场成交量的固定比例执行
    """

    def generate_slices(self, market_data: Dict) -> List[AlgorithmSlice]:
        """根据参与率生成切片"""

        # 获取市场参数
        avg_volume = market_data.get('avg_volume', 1000000)
        duration_seconds = (self.config.end_time - self.config.start_time).total_seconds()

        # 预估执行期间的总成交量
        estimated_market_volume = avg_volume * (duration_seconds / (6.5 * 3600))  # 6.5小时交易日

        # 根据参与率计算目标数量
        target_quantity = int(estimated_market_volume * self.config.participation_rate)
        target_quantity = min(target_quantity, self.config.total_quantity)

        # 分割为切片
        num_slices = max(5, int(duration_seconds / 60))  # 每分钟一个切片
        slice_quantity = target_quantity // num_slices

        slices = []
        remaining_quantity = self.config.total_quantity

        for i in range(num_slices):
            # 根据市场成交量动态调整（需要实时数据）
            current_slice_qty = min(slice_quantity, remaining_quantity)

            if current_slice_qty <= 0:
                break

            time_offset = timedelta(seconds=duration_seconds * i / num_slices)
            target_time = self.config.start_time + time_offset

            slice = AlgorithmSlice(
                slice_id=f"pov_{i}",
                parent_order_id="pov_parent",
                quantity=current_slice_qty,
                target_time=target_time,
                limit_price=self.config.price_limit
            )

            slices.append(slice)
            remaining_quantity -= current_slice_qty

        self.slices = slices
        return slices

    def should_adjust(self, market_data: Dict) -> bool:
        """根据实时成交量调整"""
        # 如果市场成交量发生显著变化，需要调整参与率
        current_volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume', 1)

        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # 成交量变化超过50%时调整
        return abs(volume_ratio - 1.0) > 0.5


class AlgorithmFactory:
    """算法工厂"""

    _algorithm_classes = {
        AlgorithmType.VWAP: VWAPAlgorithm,
        AlgorithmType.TWAP: TWAPAlgorithm,
        AlgorithmType.IS: ImplementationShortfall,
        AlgorithmType.POV: POVAlgorithm,
    }

    @classmethod
    def create_algorithm(
        cls,
        algorithm_type: AlgorithmType,
        config: AlgorithmConfig
    ) -> ExecutionAlgorithm:
        """创建执行算法"""
        if algorithm_type not in cls._algorithm_classes:
            raise ValueError(f"Unsupported algorithm type: {algorithm_type}")

        algorithm_class = cls._algorithm_classes[algorithm_type]
        return algorithm_class(config)

    @classmethod
    def get_recommended_algorithm(
        cls,
        order_size: int,
        market_data: Dict,
        urgency: float = 0.5
    ) -> AlgorithmType:
        """
        推荐算法

        Args:
            order_size: 订单大小
            market_data: 市场数据
            urgency: 紧急度

        Returns:
            推荐的算法类型
        """
        avg_volume = market_data.get('avg_volume', 1000000)
        volatility = market_data.get('volatility', 0.02)

        # 订单占日成交量的比例
        size_ratio = order_size / avg_volume if avg_volume > 0 else 0

        # 小订单且紧急：TWAP或POV
        if size_ratio < 0.01 and urgency > 0.7:
            return AlgorithmType.TWAP

        # 大订单：VWAP或IS
        if size_ratio > 0.05:
            if volatility > 0.03:
                # 高波动：Implementation Shortfall
                return AlgorithmType.IS
            else:
                # 低波动：VWAP
                return AlgorithmType.VWAP

        # 中等订单：POV
        return AlgorithmType.POV
