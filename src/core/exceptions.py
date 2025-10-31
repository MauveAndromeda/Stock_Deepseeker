"""
异常处理系统
定义所有系统异常类型
"""

from typing import Optional, Any, Dict
from datetime import datetime


class TradingSystemError(Exception):
    """交易系统基础异常"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Args:
            message: 错误信息
            error_code: 错误代码
            details: 错误详情
            cause: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None
        }

    def __str__(self) -> str:
        parts = [f"{self.__class__.__name__}: {self.message}"]
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        if self.details:
            parts.append(f"Details: {self.details}")
        if self.cause:
            parts.append(f"Caused by: {self.cause}")
        return " ".join(parts)


class ConfigurationError(TradingSystemError):
    """配置错误"""
    pass


class DataError(TradingSystemError):
    """数据相关错误"""
    pass


class DataSourceError(DataError):
    """数据源错误"""
    pass


class DataQualityError(DataError):
    """数据质量错误"""
    pass


class DataValidationError(DataError):
    """数据验证错误"""
    pass


class ModelError(TradingSystemError):
    """模型相关错误"""
    pass


class ModelLoadError(ModelError):
    """模型加载错误"""
    pass


class ModelTrainingError(ModelError):
    """模型训练错误"""
    pass


class ModelPredictionError(ModelError):
    """模型预测错误"""
    pass


class ExecutionError(TradingSystemError):
    """执行相关错误"""
    pass


class OrderError(ExecutionError):
    """订单错误"""
    pass


class BrokerError(ExecutionError):
    """经纪商错误"""
    pass


class ConnectionError(ExecutionError):
    """连接错误"""
    pass


class RiskError(TradingSystemError):
    """风险相关错误"""
    pass


class RiskLimitExceededError(RiskError):
    """风险限额超出"""
    pass


class CircuitBreakerTriggeredError(RiskError):
    """熔断触发"""
    pass


class PositionLimitError(RiskError):
    """持仓限额错误"""
    pass


class AgentError(TradingSystemError):
    """智能体相关错误"""
    pass


class AgentCommunicationError(AgentError):
    """智能体通信错误"""
    pass


class AgentDecisionError(AgentError):
    """智能体决策错误"""
    pass


class BacktestError(TradingSystemError):
    """回测相关错误"""
    pass


class BacktestDataError(BacktestError):
    """回测数据错误"""
    pass


class BacktestExecutionError(BacktestError):
    """回测执行错误"""
    pass


class MonitoringError(TradingSystemError):
    """监控相关错误"""
    pass


class MetricsError(MonitoringError):
    """指标收集错误"""
    pass


class AlertError(MonitoringError):
    """告警错误"""
    pass


class APIError(TradingSystemError):
    """API相关错误"""
    pass


class AuthenticationError(APIError):
    """认证错误"""
    pass


class RateLimitError(APIError):
    """频率限制错误"""
    pass


class TimeoutError(TradingSystemError):
    """超时错误"""
    pass


class ValidationError(TradingSystemError):
    """验证错误"""
    pass


class StateError(TradingSystemError):
    """状态错误 - 系统在不正确的状态下执行操作"""
    pass


class ResourceError(TradingSystemError):
    """资源错误 - 系统资源不足"""
    pass


# 错误代码定义
class ErrorCode:
    """错误代码枚举"""

    # 配置错误 (1xxx)
    CONFIG_NOT_FOUND = "1001"
    CONFIG_INVALID = "1002"
    CONFIG_VALIDATION_FAILED = "1003"

    # 数据错误 (2xxx)
    DATA_SOURCE_UNAVAILABLE = "2001"
    DATA_QUALITY_LOW = "2002"
    DATA_MISSING = "2003"
    DATA_CORRUPTED = "2004"
    DATA_VALIDATION_FAILED = "2005"

    # 模型错误 (3xxx)
    MODEL_NOT_FOUND = "3001"
    MODEL_LOAD_FAILED = "3002"
    MODEL_TRAINING_FAILED = "3003"
    MODEL_PREDICTION_FAILED = "3004"
    MODEL_INVALID_INPUT = "3005"

    # 执行错误 (4xxx)
    ORDER_REJECTED = "4001"
    ORDER_FAILED = "4002"
    BROKER_UNAVAILABLE = "4003"
    INSUFFICIENT_FUNDS = "4004"
    INVALID_SYMBOL = "4005"
    MARKET_CLOSED = "4006"

    # 风险错误 (5xxx)
    RISK_LIMIT_EXCEEDED = "5001"
    CIRCUIT_BREAKER_TRIGGERED = "5002"
    POSITION_LIMIT_EXCEEDED = "5003"
    DRAWDOWN_LIMIT_EXCEEDED = "5004"
    VAR_LIMIT_EXCEEDED = "5005"

    # 智能体错误 (6xxx)
    AGENT_COMMUNICATION_FAILED = "6001"
    AGENT_DECISION_FAILED = "6002"
    AGENT_TIMEOUT = "6003"
    CONSENSUS_NOT_REACHED = "6004"

    # 回测错误 (7xxx)
    BACKTEST_DATA_INSUFFICIENT = "7001"
    BACKTEST_EXECUTION_FAILED = "7002"
    BACKTEST_INVALID_PERIOD = "7003"

    # 监控错误 (8xxx)
    METRICS_COLLECTION_FAILED = "8001"
    ALERT_SEND_FAILED = "8002"
    DASHBOARD_UNAVAILABLE = "8003"

    # API错误 (9xxx)
    API_AUTHENTICATION_FAILED = "9001"
    API_RATE_LIMIT_EXCEEDED = "9002"
    API_TIMEOUT = "9003"
    API_INVALID_REQUEST = "9004"


def error_handler(func):
    """错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TradingSystemError:
            raise
        except Exception as e:
            raise TradingSystemError(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                cause=e
            )
    return wrapper
