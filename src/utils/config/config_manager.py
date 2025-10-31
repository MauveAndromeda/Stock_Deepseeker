"""
Configuration Manager
Handles all system configuration with validation and environment management
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
import yaml
import json
from loguru import logger


class DatabaseConfig(BaseModel):
    """Database configuration"""
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="stock_deepseeker")
    postgres_user: str = Field(default="deepseeker")
    postgres_password: str

    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: Optional[str] = None

    mongo_host: str = Field(default="localhost")
    mongo_port: int = Field(default=27017)
    mongo_db: str = Field(default="deepseeker_alt_data")
    mongo_user: str = Field(default="deepseeker")
    mongo_password: Optional[str] = None


class APIConfig(BaseModel):
    """API keys configuration"""
    # Data providers
    alpha_vantage_key: Optional[str] = None
    polygon_key: Optional[str] = None
    finnhub_key: Optional[str] = None
    iex_cloud_key: Optional[str] = None
    quandl_key: Optional[str] = None
    news_api_key: Optional[str] = None

    # LLM
    openai_key: Optional[str] = None
    openai_model: str = Field(default="gpt-4")
    openai_max_tokens: int = Field(default=4096)
    openai_temperature: float = Field(default=0.3)
    anthropic_key: Optional[str] = None

    # Brokers
    alpaca_key: Optional[str] = None
    alpaca_secret: Optional[str] = None
    alpaca_base_url: str = Field(default="https://paper-api.alpaca.markets")

    ib_host: str = Field(default="127.0.0.1")
    ib_port: int = Field(default=7497)
    ib_client_id: int = Field(default=1)
    ib_account_id: Optional[str] = None


class TradingConfig(BaseModel):
    """Trading parameters configuration"""
    initial_capital: float = Field(default=100000.0, gt=0)
    max_position_size: float = Field(default=0.05, gt=0, lt=1)
    max_total_risk: float = Field(default=0.20, gt=0, lt=1)
    max_daily_loss: float = Field(default=0.03, gt=0, lt=1)
    max_drawdown: float = Field(default=0.15, gt=0, lt=1)
    position_stop_loss: float = Field(default=0.02, gt=0)
    trailing_stop: float = Field(default=0.03, gt=0)

    execution_delay_ms: int = Field(default=100, ge=0)
    max_slippage: float = Field(default=0.001, ge=0)
    use_limit_orders: bool = Field(default=True)

    @validator('max_position_size')
    def validate_position_size(cls, v):
        if v > 0.2:
            logger.warning(f"Position size {v} is quite large (>20%)")
        return v


class ModelConfig(BaseModel):
    """AI Model configuration"""
    # Transformer
    transformer_hidden_size: int = Field(default=512)
    transformer_num_layers: int = Field(default=6)
    transformer_num_heads: int = Field(default=8)
    transformer_dropout: float = Field(default=0.1, ge=0, lt=1)
    transformer_seq_length: int = Field(default=60, gt=0)

    # SAC
    sac_learning_rate: float = Field(default=0.0003, gt=0)
    sac_buffer_size: int = Field(default=1000000, gt=0)
    sac_batch_size: int = Field(default=256, gt=0)
    sac_gamma: float = Field(default=0.99, ge=0, lt=1)
    sac_tau: float = Field(default=0.005, gt=0, lt=1)

    # Training
    train_test_split: float = Field(default=0.8, gt=0, lt=1)
    validation_split: float = Field(default=0.1, gt=0, lt=1)
    random_seed: int = Field(default=42)

    # Device
    use_gpu: bool = Field(default=True)
    gpu_device: int = Field(default=0)


class DataConfig(BaseModel):
    """Data collection configuration"""
    sp500_update_interval: int = Field(default=86400)  # 24 hours
    price_data_interval: int = Field(default=60)  # 1 minute
    news_fetch_interval: int = Field(default=300)  # 5 minutes
    sentiment_update_interval: int = Field(default=600)  # 10 minutes

    historical_start_date: str = Field(default="2020-01-01")
    historical_lookback_days: int = Field(default=1000)


class MonitoringConfig(BaseModel):
    """Monitoring and alerting configuration"""
    prometheus_port: int = Field(default=9090)
    grafana_host: str = Field(default="localhost")
    grafana_port: int = Field(default=3000)

    sentry_dsn: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    slack_channel: str = Field(default="#trading-alerts")

    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_email: Optional[str] = None

    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class PerformanceConfig(BaseModel):
    """Performance optimization configuration"""
    num_workers: int = Field(default=8, gt=0)
    cache_enabled: bool = Field(default=True)
    cache_ttl: int = Field(default=3600)  # 1 hour


@dataclass
class Config:
    """Main configuration class"""

    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    timezone: str = "America/New_York"

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.environment not in ["development", "staging", "production"]:
            raise ValueError(f"Invalid environment: {self.environment}")

        if self.environment == "production" and self.debug:
            logger.warning("Debug mode is enabled in production!")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "log_level": self.log_level,
            "timezone": self.timezone,
            "database": self.database.dict(),
            "api": self.api.dict(),
            "trading": self.trading.dict(),
            "model": self.model.dict(),
            "data": self.data.dict(),
            "monitoring": self.monitoring.dict(),
            "performance": self.performance.dict(),
        }

    def save(self, path: Path):
        """Save configuration to file"""
        with open(path, 'w') as f:
            if path.suffix == '.json':
                json.dump(self.to_dict(), f, indent=2)
            elif path.suffix in ['.yaml', '.yml']:
                yaml.dump(self.to_dict(), f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        logger.info(f"Configuration saved to {path}")


class ConfigManager:
    """Manages system configuration"""

    _instance: Optional[Config] = None

    @classmethod
    def load(cls, env_file: Optional[Path] = None) -> Config:
        """Load configuration from environment"""
        if cls._instance is not None:
            return cls._instance

        # Load environment variables
        if env_file is None:
            env_file = Path(__file__).parent.parent.parent.parent / ".env"

        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loaded environment from {env_file}")
        else:
            logger.warning(f"Environment file not found: {env_file}")

        # Build configuration from environment
        config = Config(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            timezone=os.getenv("TIMEZONE", "America/New_York"),
        )

        # Database config
        config.database = DatabaseConfig(
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "stock_deepseeker"),
            postgres_user=os.getenv("POSTGRES_USER", "deepseeker"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD"),
        )

        # API config
        config.api = APIConfig(
            alpha_vantage_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
            polygon_key=os.getenv("POLYGON_API_KEY"),
            finnhub_key=os.getenv("FINNHUB_API_KEY"),
            openai_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
            alpaca_key=os.getenv("ALPACA_API_KEY"),
            alpaca_secret=os.getenv("ALPACA_SECRET_KEY"),
        )

        # Trading config
        config.trading = TradingConfig(
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "100000")),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.05")),
            max_total_risk=float(os.getenv("MAX_TOTAL_RISK", "0.20")),
        )

        # Model config
        config.model = ModelConfig(
            transformer_hidden_size=int(os.getenv("TRANSFORMER_HIDDEN_SIZE", "512")),
            sac_learning_rate=float(os.getenv("SAC_LEARNING_RATE", "0.0003")),
        )

        cls._instance = config
        logger.info("Configuration loaded successfully")
        return config

    @classmethod
    def get(cls) -> Config:
        """Get current configuration instance"""
        if cls._instance is None:
            return cls.load()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset configuration instance"""
        cls._instance = None


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = ConfigManager.load()
    return _config
