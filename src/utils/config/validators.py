"""
Configuration Validators
Validates configuration settings and ensures system integrity
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger

@dataclass
class ValidationResult:
    """Result of validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class ConfigValidator:
    """Validates system configuration"""

    @staticmethod
    def validate_trading_config(config: Any) -> ValidationResult:
        """Validate trading configuration"""
        errors = []
        warnings = []
        
        # Check initial capital
        if config.initial_capital <= 0:
            errors.append("Initial capital must be positive")
        elif config.initial_capital < 10000:
            warnings.append("Initial capital is quite low (<$10k)")
        
        # Check position sizing
        if config.max_position_size <= 0 or config.max_position_size > 1:
            errors.append("Max position size must be between 0 and 1")
        
        if config.max_position_size > 0.2:
            warnings.append("Max position size >20% is risky")
        
        # Check stop loss
        if config.position_stop_loss <= 0:
            errors.append("Stop loss must be positive")
        elif config.position_stop_loss > 0.1:
            warnings.append("Stop loss >10% is quite wide")
        
        # Check risk limits
        if config.max_daily_loss <= 0 or config.max_daily_loss > 1:
            errors.append("Max daily loss must be between 0 and 1")
        
        if config.max_drawdown <= 0 or config.max_drawdown > 1:
            errors.append("Max drawdown must be between 0 and 1")
        
        # Check commission and slippage
        if hasattr(config, 'commission'):
            if config.commission < 0 or config.commission > 0.01:
                errors.append("Commission seems incorrect")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_model_config(config: Any) -> ValidationResult:
        """Validate model configuration"""
        errors = []
        warnings = []
        
        # Transformer config
        if hasattr(config, 'transformer_hidden_size'):
            if config.transformer_hidden_size <= 0:
                errors.append("Hidden size must be positive")
            elif config.transformer_hidden_size > 2048:
                warnings.append("Very large hidden size may cause memory issues")
        
        if hasattr(config, 'transformer_num_heads'):
            if config.transformer_num_heads <= 0:
                errors.append("Number of heads must be positive")
            
            if hasattr(config, 'transformer_hidden_size'):
                if config.transformer_hidden_size % config.transformer_num_heads != 0:
                    errors.append("Hidden size must be divisible by number of heads")
        
        # SAC config
        if hasattr(config, 'sac_learning_rate'):
            if config.sac_learning_rate <= 0 or config.sac_learning_rate > 0.01:
                warnings.append("Learning rate might be too high/low")
        
        if hasattr(config, 'sac_gamma'):
            if config.sac_gamma <= 0 or config.sac_gamma > 1:
                errors.append("Gamma must be between 0 and 1")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_api_config(config: Any) -> ValidationResult:
        """Validate API configuration"""
        errors = []
        warnings = []
        
        # Check critical API keys
        critical_keys = ['alpaca_key', 'alpaca_secret']
        for key in critical_keys:
            if not hasattr(config, key) or not getattr(config, key):
                errors.append(f"Missing critical API key: {key}")
        
        # Check data provider keys
        data_keys = ['alpha_vantage_key', 'polygon_key', 'finnhub_key']
        missing_data_keys = sum(1 for k in data_keys if not hasattr(config, k) or not getattr(config, k))
        
        if missing_data_keys == len(data_keys):
            errors.append("No data provider API keys configured")
        elif missing_data_keys > 0:
            warnings.append(f"Missing {missing_data_keys}/{len(data_keys)} data provider keys")
        
        # Check LLM keys
        if not hasattr(config, 'openai_key') or not config.openai_key:
            warnings.append("OpenAI API key not configured - LLM features disabled")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_all(config: Any) -> ValidationResult:
        """Validate entire configuration"""
        all_errors = []
        all_warnings = []
        
        # Validate trading config
        if hasattr(config, 'trading'):
            result = ConfigValidator.validate_trading_config(config.trading)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        # Validate model config
        if hasattr(config, 'model'):
            result = ConfigValidator.validate_model_config(config.model)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        # Validate API config
        if hasattr(config, 'api'):
            result = ConfigValidator.validate_api_config(config.api)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        # Log results
        if all_errors:
            for error in all_errors:
                logger.error(f"Config validation error: {error}")
        
        if all_warnings:
            for warning in all_warnings:
                logger.warning(f"Config validation warning: {warning}")
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings
        )
