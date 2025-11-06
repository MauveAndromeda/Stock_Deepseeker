"""
Configuration manager with environment support.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "trading"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 10


@dataclass
class BrokerConfig:
    """Broker configuration."""
    broker_type: str = "paper"
    api_key: str = ""
    api_secret: str = ""
    paper_trading: bool = True
    base_url: Optional[str] = None


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_size: float = 0.10  # 10% of portfolio
    max_sector_exposure: float = 0.30  # 30% per sector
    max_drawdown: float = -0.20  # 20%
    max_leverage: float = 1.0
    var_limit: float = 50000.0
    stop_loss_pct: float = 0.05  # 5%


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    initial_capital: float = 1000000.0
    commission: float = 0.001  # 10 bps
    slippage: float = 0.0005  # 5 bps
    start_date: str = "2020-01-01"
    end_date: str = "2023-12-31"


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    metrics_port: int = 8000
    log_level: str = "INFO"
    alert_email: Optional[str] = None
    slack_webhook: Optional[str] = None


@dataclass
class Config:
    """Main configuration object."""
    environment: str = "development"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_yaml(self) -> str:
        """Convert to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class ConfigManager:
    """
    Configuration manager with environment variable support.
    
    Features:
    - Load from YAML/JSON files
    - Environment variable overrides
    - Multiple environments (dev, staging, prod)
    - Validation
    - Hot reload
    """
    
    def __init__(self, config_path: Optional[str] = None, environment: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        
        self._config: Optional[Config] = None
        
        logger.info(f"Initialized ConfigManager for environment: {self.environment}")
    
    def load(self, config_path: Optional[str] = None) -> Config:
        """Load configuration from file."""
        path = config_path or self.config_path
        
        if not path:
            logger.info("No config file specified, using defaults")
            return Config(environment=self.environment)
        
        path_obj = Path(path)
        
        if not path_obj.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return Config(environment=self.environment)
        
        # Load file
        with open(path, 'r') as f:
            if path_obj.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path_obj.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {path_obj.suffix}")
        
        # Parse configuration
        config = self._parse_config(data)
        
        # Apply environment overrides
        config = self._apply_env_overrides(config)
        
        self._config = config
        
        logger.info(f"Loaded configuration from {path}")
        return config
    
    def save(self, config: Config, output_path: str):
        """Save configuration to file."""
        path_obj = Path(output_path)
        
        with open(output_path, 'w') as f:
            if path_obj.suffix in ['.yaml', '.yml']:
                yaml.dump(config.to_dict(), f, default_flow_style=False)
            elif path_obj.suffix == '.json':
                json.dump(config.to_dict(), f, indent=2)
            else:
                raise ValueError(f"Unsupported format: {path_obj.suffix}")
        
        logger.info(f"Saved configuration to {output_path}")
    
    def get(self) -> Config:
        """Get current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    def reload(self) -> Config:
        """Reload configuration from file."""
        return self.load(self.config_path)
    
    def _parse_config(self, data: dict) -> Config:
        """Parse configuration dictionary."""
        config = Config(
            environment=data.get('environment', self.environment)
        )
        
        # Parse database config
        if 'database' in data:
            db_data = data['database']
            config.database = DatabaseConfig(**db_data)
        
        # Parse broker config
        if 'broker' in data:
            broker_data = data['broker']
            config.broker = BrokerConfig(**broker_data)
        
        # Parse risk config
        if 'risk' in data:
            risk_data = data['risk']
            config.risk = RiskConfig(**risk_data)
        
        # Parse backtest config
        if 'backtest' in data:
            backtest_data = data['backtest']
            config.backtest = BacktestConfig(**backtest_data)
        
        # Parse monitoring config
        if 'monitoring' in data:
            monitoring_data = data['monitoring']
            config.monitoring = MonitoringConfig(**monitoring_data)
        
        # Store custom fields
        config.custom = {
            k: v for k, v in data.items()
            if k not in ['environment', 'database', 'broker', 'risk', 'backtest', 'monitoring']
        }
        
        return config
    
    def _apply_env_overrides(self, config: Config) -> Config:
        """Apply environment variable overrides."""
        # Database overrides
        if os.getenv('DB_HOST'):
            config.database.host = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'):
            config.database.port = int(os.getenv('DB_PORT'))
        if os.getenv('DB_NAME'):
            config.database.database = os.getenv('DB_NAME')
        if os.getenv('DB_USER'):
            config.database.username = os.getenv('DB_USER')
        if os.getenv('DB_PASSWORD'):
            config.database.password = os.getenv('DB_PASSWORD')
        
        # Broker overrides
        if os.getenv('BROKER_API_KEY'):
            config.broker.api_key = os.getenv('BROKER_API_KEY')
        if os.getenv('BROKER_API_SECRET'):
            config.broker.api_secret = os.getenv('BROKER_API_SECRET')
        
        # Monitoring overrides
        if os.getenv('LOG_LEVEL'):
            config.monitoring.log_level = os.getenv('LOG_LEVEL')
        
        return config


# Global config manager
_default_config_manager: Optional[ConfigManager] = None


def get_default_config_manager() -> ConfigManager:
    """Get global default config manager."""
    global _default_config_manager
    if _default_config_manager is None:
        _default_config_manager = ConfigManager()
    return _default_config_manager


def get_config() -> Config:
    """Get current configuration."""
    return get_default_config_manager().get()
