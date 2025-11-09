"""
Configuration validator.
"""

from dataclasses import dataclass

from src.config.manager import Config


@dataclass
class ValidationError:
    """Validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning


class ConfigValidator:
    """
    Configuration validator.
    
    Validates configuration for correctness and security.
    """

    def __init__(self):
        """Initialize validator."""
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def validate(self, config: Config) -> bool:
        """
        Validate configuration.
        
        Returns True if valid, False otherwise.
        """
        self.errors = []
        self.warnings = []

        # Validate database config
        self._validate_database(config)

        # Validate broker config
        self._validate_broker(config)

        # Validate risk config
        self._validate_risk(config)

        # Validate backtest config
        self._validate_backtest(config)

        return len(self.errors) == 0

    def _validate_database(self, config: Config):
        """Validate database configuration."""
        db = config.database

        if not db.host:
            self.errors.append(ValidationError("database.host", "Host is required"))

        if db.port <= 0 or db.port > 65535:
            self.errors.append(ValidationError("database.port", "Invalid port number"))

        if not db.database:
            self.errors.append(ValidationError("database.database", "Database name is required"))

        if config.environment == "production" and not db.password:
            self.warnings.append(ValidationError(
                "database.password",
                "No password set for production database",
                severity="warning"
            ))

    def _validate_broker(self, config: Config):
        """Validate broker configuration."""
        broker = config.broker

        if broker.broker_type not in ["paper", "alpaca", "interactive_brokers", "td_ameritrade"]:
            self.errors.append(ValidationError(
                "broker.broker_type",
                f"Invalid broker type: {broker.broker_type}"
            ))

        if broker.broker_type != "paper":
            if not broker.api_key:
                self.errors.append(ValidationError("broker.api_key", "API key required for real broker"))

            if not broker.api_secret:
                self.errors.append(ValidationError("broker.api_secret", "API secret required for real broker"))

        if config.environment == "production" and broker.paper_trading:
            self.warnings.append(ValidationError(
                "broker.paper_trading",
                "Paper trading enabled in production",
                severity="warning"
            ))

    def _validate_risk(self, config: Config):
        """Validate risk configuration."""
        risk = config.risk

        if risk.max_position_size <= 0 or risk.max_position_size > 1:
            self.errors.append(ValidationError(
                "risk.max_position_size",
                "Max position size must be between 0 and 1"
            ))

        if risk.max_sector_exposure <= 0 or risk.max_sector_exposure > 1:
            self.errors.append(ValidationError(
                "risk.max_sector_exposure",
                "Max sector exposure must be between 0 and 1"
            ))

        if risk.max_drawdown >= 0:
            self.errors.append(ValidationError(
                "risk.max_drawdown",
                "Max drawdown must be negative"
            ))

        if risk.max_leverage < 1:
            self.errors.append(ValidationError(
                "risk.max_leverage",
                "Max leverage must be >= 1"
            ))

        if risk.var_limit <= 0:
            self.errors.append(ValidationError(
                "risk.var_limit",
                "VaR limit must be positive"
            ))

    def _validate_backtest(self, config: Config):
        """Validate backtest configuration."""
        bt = config.backtest

        if bt.initial_capital <= 0:
            self.errors.append(ValidationError(
                "backtest.initial_capital",
                "Initial capital must be positive"
            ))

        if bt.commission < 0:
            self.errors.append(ValidationError(
                "backtest.commission",
                "Commission must be non-negative"
            ))

        if bt.slippage < 0:
            self.errors.append(ValidationError(
                "backtest.slippage",
                "Slippage must be non-negative"
            ))

        # Validate dates
        from datetime import datetime
        try:
            start = datetime.strptime(bt.start_date, "%Y-%m-%d")
            end = datetime.strptime(bt.end_date, "%Y-%m-%d")

            if start >= end:
                self.errors.append(ValidationError(
                    "backtest.dates",
                    "Start date must be before end date"
                ))
        except ValueError as e:
            self.errors.append(ValidationError(
                "backtest.dates",
                f"Invalid date format: {e}"
            ))

    def get_errors(self) -> list[ValidationError]:
        """Get validation errors."""
        return self.errors

    def get_warnings(self) -> list[ValidationError]:
        """Get validation warnings."""
        return self.warnings

    def print_errors(self):
        """Print validation errors."""
        if self.errors:
            print("\n❌ Validation Errors:")
            for error in self.errors:
                print(f"  - {error.field}: {error.message}")

        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"  - {warning.field}: {warning.message}")
