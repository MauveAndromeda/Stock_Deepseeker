"""
配置管理系统
支持多环境、动态配置、配置验证
"""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from copy import deepcopy


class Environment(Enum):
    """运行环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class TradingMode(Enum):
    """交易模式"""
    PAPER = "paper"  # 模拟交易
    LIVE = "live"    # 实盘交易
    BACKTEST = "backtest"  # 回测


class DataSource(Enum):
    """数据源枚举"""
    YAHOO = "yahoo"
    ALPACA = "alpaca"
    ALPHA_VANTAGE = "alpha_vantage"
    IEX = "iex"
    POLYGON = "polygon"


@dataclass
class ModelConfig:
    """AI模型配置"""
    # Transformer配置
    transformer_hidden_size: int = 512
    transformer_num_layers: int = 8
    transformer_num_heads: int = 8
    transformer_dropout: float = 0.1
    transformer_max_seq_length: int = 512

    # SAC配置
    sac_learning_rate: float = 3e-4
    sac_buffer_size: int = 1000000
    sac_batch_size: int = 256
    sac_gamma: float = 0.99
    sac_tau: float = 0.005
    sac_alpha: float = 0.2
    sac_auto_entropy_tuning: bool = True

    # ChatGPT-5配置
    gpt5_model: str = "gpt-5-nano"
    gpt5_api_key: str = ""
    gpt5_max_tokens: int = 4096
    gpt5_temperature: float = 0.7
    gpt5_top_p: float = 0.9

    # 训练配置
    training_epochs: int = 100
    training_batch_size: int = 128
    training_learning_rate: float = 1e-4
    training_warmup_steps: int = 1000
    training_gradient_clip: float = 1.0

    # 模型保存
    model_save_dir: str = "models/checkpoints"
    model_save_frequency: int = 1000

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        if self.transformer_hidden_size <= 0:
            errors.append("transformer_hidden_size must be positive")

        if self.transformer_num_layers <= 0:
            errors.append("transformer_num_layers must be positive")

        if not 0 <= self.transformer_dropout <= 1:
            errors.append("transformer_dropout must be between 0 and 1")

        if not 0 < self.sac_learning_rate < 1:
            errors.append("sac_learning_rate must be between 0 and 1")

        if self.sac_buffer_size <= 0:
            errors.append("sac_buffer_size must be positive")

        if not self.gpt5_api_key:
            errors.append("gpt5_api_key is required")

        return errors


@dataclass
class DataConfig:
    """数据配置"""
    # 数据源
    primary_source: str = "yahoo"
    backup_sources: List[str] = field(default_factory=lambda: ["alpaca", "polygon"])

    # 数据范围
    symbols: List[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL"])
    lookback_days: int = 252  # 1年交易日

    # 数据更新
    update_interval_seconds: int = 60
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    # 特征工程
    technical_indicators: List[str] = field(default_factory=lambda: [
        "SMA_20", "SMA_50", "SMA_200",
        "EMA_12", "EMA_26",
        "RSI_14", "RSI_28",
        "MACD", "MACD_Signal", "MACD_Hist",
        "BB_Upper", "BB_Middle", "BB_Lower",
        "ATR_14", "ADX_14",
        "OBV", "Volume_SMA_20",
        "Stochastic_K", "Stochastic_D",
        "Williams_R", "CCI",
    ])

    fundamental_features: List[str] = field(default_factory=lambda: [
        "PE_Ratio", "PB_Ratio", "PS_Ratio",
        "Debt_to_Equity", "ROE", "ROA",
        "Profit_Margin", "EPS_Growth",
        "Revenue_Growth", "Free_Cash_Flow",
    ])

    sentiment_sources: List[str] = field(default_factory=lambda: [
        "twitter", "reddit", "news", "sec_filings"
    ])

    # 数据质量
    min_data_quality_score: float = 0.95
    handle_missing_data: str = "interpolate"  # interpolate, forward_fill, drop
    outlier_detection: bool = True
    outlier_method: str = "iqr"  # iqr, zscore, isolation_forest

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        if not self.symbols:
            errors.append("symbols list cannot be empty")

        if self.lookback_days <= 0:
            errors.append("lookback_days must be positive")

        if self.update_interval_seconds <= 0:
            errors.append("update_interval_seconds must be positive")

        if not 0 <= self.min_data_quality_score <= 1:
            errors.append("min_data_quality_score must be between 0 and 1")

        return errors


@dataclass
class RiskConfig:
    """风险管理配置"""
    # 仓位限制
    max_position_size: float = 0.10  # 单个持仓最大10%
    max_total_exposure: float = 1.0  # 总敞口100%
    max_sector_exposure: float = 0.30  # 单个行业最大30%
    max_correlation: float = 0.70  # 最大相关性

    # 止损止盈
    stop_loss_pct: float = 0.02  # 2% 止损
    take_profit_pct: float = 0.05  # 5% 止盈
    trailing_stop_pct: float = 0.015  # 1.5% 移动止损

    # 风险限额
    max_daily_loss: float = 0.03  # 日最大亏损3%
    max_weekly_loss: float = 0.10  # 周最大亏损10%
    max_drawdown: float = 0.20  # 最大回撤20%

    # VaR配置
    var_confidence: float = 0.95  # 95% VaR
    var_lookback_days: int = 252
    expected_shortfall: bool = True

    # 风控动作
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: float = 0.05  # 5%触发熔断
    auto_hedge_enabled: bool = True
    hedge_ratio: float = 0.5

    # 压力测试
    stress_test_enabled: bool = True
    stress_scenarios: List[str] = field(default_factory=lambda: [
        "market_crash", "flash_crash", "sector_rotation",
        "volatility_spike", "liquidity_crisis"
    ])

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        if not 0 < self.max_position_size <= 1:
            errors.append("max_position_size must be between 0 and 1")

        if not 0 < self.max_total_exposure <= 2:
            errors.append("max_total_exposure must be between 0 and 2")

        if self.stop_loss_pct <= 0:
            errors.append("stop_loss_pct must be positive")

        if self.take_profit_pct <= 0:
            errors.append("take_profit_pct must be positive")

        if not 0 < self.var_confidence < 1:
            errors.append("var_confidence must be between 0 and 1")

        return errors


@dataclass
class ExecutionConfig:
    """交易执行配置"""
    # 经纪商
    broker: str = "alpaca"  # alpaca, interactive_brokers, binance
    broker_api_key: str = ""
    broker_secret_key: str = ""
    broker_base_url: str = ""

    # 订单类型
    default_order_type: str = "limit"  # market, limit, stop, stop_limit
    limit_order_offset_pct: float = 0.001  # 限价单偏移0.1%

    # 执行优化
    smart_order_routing: bool = True
    minimize_market_impact: bool = True
    vwap_execution: bool = True
    twap_execution: bool = False

    # 订单分拆
    enable_order_splitting: bool = True
    max_order_size_pct: float = 0.01  # 单笔订单最大1% ADV
    split_large_orders: bool = True
    child_order_delay_seconds: int = 5

    # 滑点控制
    max_slippage_pct: float = 0.002  # 最大滑点0.2%
    slippage_model: str = "adaptive"  # fixed, adaptive, market_based

    # 佣金
    commission_per_share: float = 0.001
    commission_min: float = 1.0
    commission_pct: float = 0.0

    # 重试机制
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 1
    exponential_backoff: bool = True

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        if not self.broker:
            errors.append("broker is required")

        if not self.broker_api_key:
            errors.append("broker_api_key is required")

        if not self.broker_secret_key:
            errors.append("broker_secret_key is required")

        if self.max_order_size_pct <= 0:
            errors.append("max_order_size_pct must be positive")

        if self.max_slippage_pct <= 0:
            errors.append("max_slippage_pct must be positive")

        return errors


@dataclass
class AgentConfig:
    """多智能体配置"""
    # 智能体数量
    num_retail_agents: int = 200
    num_institutional_agents: int = 50
    num_expert_agents: int = 5

    # 智能体类型分布
    retail_types: Dict[str, float] = field(default_factory=lambda: {
        "momentum_chaser": 0.25,
        "panic_seller": 0.20,
        "herd_follower": 0.20,
        "value_seeker": 0.20,
        "technical_trader": 0.15,
    })

    institutional_types: Dict[str, float] = field(default_factory=lambda: {
        "quantitative": 0.30,
        "value_investor": 0.20,
        "trend_follower": 0.20,
        "high_frequency": 0.20,
        "index_fund": 0.10,
    })

    # 智能体学习
    agent_learning_enabled: bool = True
    agent_learning_rate: float = 0.01
    agent_memory_size: int = 1000
    agent_experience_replay: bool = True

    # 协作机制
    enable_communication: bool = True
    communication_protocol: str = "broadcast"  # broadcast, p2p, hierarchical
    consensus_threshold: float = 0.70

    # 决策权重
    retail_weight: float = 0.30
    institutional_weight: float = 0.50
    expert_weight: float = 0.20

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        if self.num_retail_agents <= 0:
            errors.append("num_retail_agents must be positive")

        if self.num_institutional_agents <= 0:
            errors.append("num_institutional_agents must be positive")

        if not abs(sum(self.retail_types.values()) - 1.0) < 0.01:
            errors.append("retail_types must sum to 1.0")

        if not abs(sum(self.institutional_types.values()) - 1.0) < 0.01:
            errors.append("institutional_types must sum to 1.0")

        total_weight = self.retail_weight + self.institutional_weight + self.expert_weight
        if not abs(total_weight - 1.0) < 0.01:
            errors.append("agent weights must sum to 1.0")

        return errors


@dataclass
class MonitoringConfig:
    """监控配置"""
    # 日志
    log_level: str = "INFO"
    log_file: str = "logs/trading_system.log"
    log_rotation: str = "1 day"
    log_retention: str = "30 days"
    log_format: str = "json"

    # 指标收集
    metrics_enabled: bool = True
    metrics_interval_seconds: int = 60
    metrics_retention_days: int = 90

    # 性能监控
    track_latency: bool = True
    track_throughput: bool = True
    track_resource_usage: bool = True

    # 告警
    alerting_enabled: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["email", "slack", "pagerduty"])
    alert_email: str = ""
    alert_slack_webhook: str = ""

    # 实时监控
    dashboard_enabled: bool = True
    dashboard_port: int = 8080
    dashboard_host: str = "0.0.0.0"

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            errors.append(f"log_level must be one of {valid_log_levels}")

        if self.metrics_interval_seconds <= 0:
            errors.append("metrics_interval_seconds must be positive")

        if self.dashboard_port <= 0 or self.dashboard_port > 65535:
            errors.append("dashboard_port must be between 1 and 65535")

        return errors


@dataclass
class Config:
    """主配置类"""
    # 环境
    environment: Environment = Environment.DEVELOPMENT
    trading_mode: TradingMode = TradingMode.PAPER

    # 子配置
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # 系统配置
    system_name: str = "Stock Deepseeker"
    system_version: str = "3.0.0"
    timezone: str = "America/New_York"

    # 性能配置
    num_workers: int = 4
    async_enabled: bool = True
    cache_enabled: bool = True

    def validate(self) -> List[str]:
        """验证所有配置"""
        errors = []

        errors.extend(self.model.validate())
        errors.extend(self.data.validate())
        errors.extend(self.risk.validate())
        errors.extend(self.execution.validate())
        errors.extend(self.agent.validate())
        errors.extend(self.monitoring.validate())

        if self.num_workers <= 0:
            errors.append("num_workers must be positive")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """从字典创建配置"""
        config = cls()

        if 'environment' in data:
            config.environment = Environment(data['environment'])
        if 'trading_mode' in data:
            config.trading_mode = TradingMode(data['trading_mode'])

        if 'model' in data:
            config.model = ModelConfig(**data['model'])
        if 'data' in data:
            config.data = DataConfig(**data['data'])
        if 'risk' in data:
            config.risk = RiskConfig(**data['risk'])
        if 'execution' in data:
            config.execution = ExecutionConfig(**data['execution'])
        if 'agent' in data:
            config.agent = AgentConfig(**data['agent'])
        if 'monitoring' in data:
            config.monitoring = MonitoringConfig(**data['monitoring'])

        # 系统配置
        for key in ['system_name', 'system_version', 'timezone', 'num_workers',
                    'async_enabled', 'cache_enabled']:
            if key in data:
                setattr(config, key, data[key])

        return config


class ConfigManager:
    """配置管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._config: Optional[Config] = None
            self._config_path: Optional[Path] = None
            self._watchers: List[callable] = []
            self._initialized = True

    def load_config(self, config_path: Union[str, Path]) -> Config:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径（支持 .yaml, .json）

        Returns:
            Config对象

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误或验证失败
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # 读取配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif config_path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")

        # 环境变量覆盖
        self._apply_env_overrides(data)

        # 创建配置对象
        config = Config.from_dict(data)

        # 验证配置
        errors = config.validate()
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        self._config = config
        self._config_path = config_path

        # 通知watchers
        self._notify_watchers()

        return config

    def _apply_env_overrides(self, data: Dict[str, Any]):
        """应用环境变量覆盖"""
        # 环境
        if env := os.getenv('TRADING_ENVIRONMENT'):
            data['environment'] = env
        if mode := os.getenv('TRADING_MODE'):
            data['trading_mode'] = mode

        # API密钥
        if gpt5_key := os.getenv('GPT5_API_KEY'):
            if 'model' not in data:
                data['model'] = {}
            data['model']['gpt5_api_key'] = gpt5_key

        if broker_key := os.getenv('BROKER_API_KEY'):
            if 'execution' not in data:
                data['execution'] = {}
            data['execution']['broker_api_key'] = broker_key

        if broker_secret := os.getenv('BROKER_SECRET_KEY'):
            if 'execution' not in data:
                data['execution'] = {}
            data['execution']['broker_secret_key'] = broker_secret

    def get_config(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._config

    def update_config(self, updates: Dict[str, Any]):
        """
        动态更新配置

        Args:
            updates: 要更新的配置项
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")

        config_dict = self._config.to_dict()
        config_dict.update(updates)

        new_config = Config.from_dict(config_dict)

        # 验证新配置
        errors = new_config.validate()
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        self._config = new_config
        self._notify_watchers()

    def watch_config(self, callback: callable):
        """
        注册配置变更监听器

        Args:
            callback: 回调函数，接收Config对象作为参数
        """
        self._watchers.append(callback)

    def _notify_watchers(self):
        """通知所有watchers配置已更新"""
        for watcher in self._watchers:
            try:
                watcher(self._config)
            except Exception as e:
                print(f"Error notifying config watcher: {e}")

    def save_config(self, output_path: Optional[Union[str, Path]] = None):
        """
        保存配置到文件

        Args:
            output_path: 输出路径，默认为原配置文件路径
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")

        output_path = Path(output_path) if output_path else self._config_path

        if output_path is None:
            raise ValueError("output_path must be specified if config was not loaded from file")

        config_dict = self._config.to_dict()

        # 转换枚举为字符串
        config_dict['environment'] = self._config.environment.value
        config_dict['trading_mode'] = self._config.trading_mode.value

        with open(output_path, 'w', encoding='utf-8') as f:
            if output_path.suffix in ['.yaml', '.yml']:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            elif output_path.suffix == '.json':
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Unsupported output format: {output_path.suffix}")
