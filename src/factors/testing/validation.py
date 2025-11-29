"""
Out-of-sample validation framework.

Validates factor performance using walk-forward and cross-validation.
"""

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd

from src.factors import Factor
from src.factors.testing.backtester import FactorBacktester


@dataclass
class ValidationResult:
    """
    Out-of-sample validation result.

    Attributes:
        in_sample_metrics: Performance metrics on training data
        out_of_sample_metrics: Performance metrics on test data
        degradation: Performance degradation (out / in sample)
        validation_type: Type of validation performed
        train_periods: Number of training periods
        test_periods: Number of test periods
        fold_results: Results from individual folds (for CV)
    """
    in_sample_metrics: dict[str, float]
    out_of_sample_metrics: dict[str, float]
    degradation: dict[str, float]
    validation_type: str
    train_periods: int
    test_periods: int
    fold_results: list[dict] | None = None
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary report."""
        degradation_str = "\n".join([
            f"  {name}: {deg:.2%}"
            for name, deg in self.degradation.items()
        ])

        return f"""
Out-of-Sample Validation Report
{'=' * 60}
Validation Type: {self.validation_type}
Train Periods: {self.train_periods}
Test Periods: {self.test_periods}

In-Sample Metrics:
  Sharpe: {self.in_sample_metrics.get('sharpe', 0):.3f}
  IC: {self.in_sample_metrics.get('ic_mean', 0):.4f}
  Win Rate: {self.in_sample_metrics.get('win_rate', 0):.1%}

Out-of-Sample Metrics:
  Sharpe: {self.out_of_sample_metrics.get('sharpe', 0):.3f}
  IC: {self.out_of_sample_metrics.get('ic_mean', 0):.4f}
  Win Rate: {self.out_of_sample_metrics.get('win_rate', 0):.1%}

Performance Degradation:
{degradation_str}
"""


class OutOfSampleValidator:
    """
    Validates factor performance out-of-sample.

    Methods:
    1. Walk-forward validation
    2. K-fold cross-validation
    3. Time-series split validation
    """

    def __init__(
        self,
        backtester: FactorBacktester | None = None,
        train_test_split: float = 0.7,  # 70% train, 30% test
        min_train_periods: int = 252,  # 1 year minimum training
        min_test_periods: int = 63,  # 3 months minimum testing
    ) -> None:
        """
        Initialize validator.

        Args:
            backtester: FactorBacktester instance
            train_test_split: Proportion of data for training
            min_train_periods: Minimum training periods
            min_test_periods: Minimum testing periods
        """
        self.backtester = backtester or FactorBacktester()
        self.train_test_split = train_test_split
        self.min_train_periods = min_train_periods
        self.min_test_periods = min_test_periods

        logger.info("Initialized OutOfSampleValidator")

    def validate_walk_forward(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        window_size: int = 252,  # Rolling window size
        step_size: int = 63,  # Step between windows
        universe: list[str] | None = None
    ) -> ValidationResult:
        """
        Perform walk-forward validation.

        Train on rolling window, test on next period.

        Args:
            factor: Factor to validate
            price_data: Price data
            start_date: Validation start
            end_date: Validation end
            window_size: Training window size
            step_size: Step between windows
            universe: Optional universe

        Returns:
            ValidationResult
        """
        logger.info(
            f"Walk-forward validation: window={window_size}D, step={step_size}D"
        )

        dates = sorted(price_data.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        fold_results = []

        for i in range(window_size, len(dates) - step_size, step_size):
            # Training period
            train_start = dates[i - window_size]
            train_end = dates[i - 1]

            # Test period
            test_start = dates[i]
            test_end = dates[min(i + step_size - 1, len(dates) - 1)]

            # Backtest on training data
            train_result = self.backtester.backtest(
                factor, price_data, train_start, train_end, universe
            )

            # Backtest on test data
            test_result = self.backtester.backtest(
                factor, price_data, test_start, test_end, universe
            )

            fold_results.append({
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "train_sharpe": train_result.sharpe_ratio,
                "test_sharpe": test_result.sharpe_ratio,
                "train_ic": train_result.ic_mean,
                "test_ic": test_result.ic_mean,
                "train_win_rate": train_result.win_rate,
                "test_win_rate": test_result.win_rate,
            })

        if len(fold_results) == 0:
            return self._empty_result("walk_forward")

        # Aggregate results
        in_sample_metrics = {
            "sharpe": np.mean([f["train_sharpe"] for f in fold_results]),
            "ic_mean": np.mean([f["train_ic"] for f in fold_results]),
            "win_rate": np.mean([f["train_win_rate"] for f in fold_results]),
        }

        out_of_sample_metrics = {
            "sharpe": np.mean([f["test_sharpe"] for f in fold_results]),
            "ic_mean": np.mean([f["test_ic"] for f in fold_results]),
            "win_rate": np.mean([f["test_win_rate"] for f in fold_results]),
        }

        degradation = self._calculate_degradation(
            in_sample_metrics, out_of_sample_metrics
        )

        result = ValidationResult(
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
            degradation=degradation,
            validation_type="walk_forward",
            train_periods=window_size,
            test_periods=step_size,
            fold_results=fold_results,
        )

        logger.info(
            f"Walk-forward complete: {len(fold_results)} folds, "
            f"Sharpe degradation={degradation.get('sharpe', 0):.1%}"
        )

        return result

    def validate_kfold(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        n_folds: int = 5,
        universe: list[str] | None = None
    ) -> ValidationResult:
        """
        Perform k-fold cross-validation.

        Args:
            factor: Factor to validate
            price_data: Price data
            start_date: Start date
            end_date: End date
            n_folds: Number of folds
            universe: Optional universe

        Returns:
            ValidationResult
        """
        logger.info(f"K-fold validation: {n_folds} folds")

        dates = sorted(price_data.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        # Split dates into folds
        fold_size = len(dates) // n_folds
        folds = []

        for i in range(n_folds):
            fold_start_idx = i * fold_size
            if i == n_folds - 1:
                fold_end_idx = len(dates)
            else:
                fold_end_idx = (i + 1) * fold_size

            folds.append(dates[fold_start_idx:fold_end_idx])

        fold_results = []

        for test_fold_idx in range(n_folds):
            # Test fold
            test_dates = folds[test_fold_idx]
            test_start = test_dates[0]
            test_end = test_dates[-1]

            # Training folds (all other folds)
            train_dates = []
            for i in range(n_folds):
                if i != test_fold_idx:
                    train_dates.extend(folds[i])

            if len(train_dates) < self.min_train_periods:
                continue

            train_start = train_dates[0]
            train_end = train_dates[-1]

            # Backtest on training data
            train_result = self.backtester.backtest(
                factor, price_data, train_start, train_end, universe
            )

            # Backtest on test data
            test_result = self.backtester.backtest(
                factor, price_data, test_start, test_end, universe
            )

            fold_results.append({
                "fold": test_fold_idx,
                "train_sharpe": train_result.sharpe_ratio,
                "test_sharpe": test_result.sharpe_ratio,
                "train_ic": train_result.ic_mean,
                "test_ic": test_result.ic_mean,
                "train_win_rate": train_result.win_rate,
                "test_win_rate": test_result.win_rate,
            })

        if len(fold_results) == 0:
            return self._empty_result("kfold")

        # Aggregate results
        in_sample_metrics = {
            "sharpe": np.mean([f["train_sharpe"] for f in fold_results]),
            "ic_mean": np.mean([f["train_ic"] for f in fold_results]),
            "win_rate": np.mean([f["train_win_rate"] for f in fold_results]),
        }

        out_of_sample_metrics = {
            "sharpe": np.mean([f["test_sharpe"] for f in fold_results]),
            "ic_mean": np.mean([f["test_ic"] for f in fold_results]),
            "win_rate": np.mean([f["test_win_rate"] for f in fold_results]),
        }

        degradation = self._calculate_degradation(
            in_sample_metrics, out_of_sample_metrics
        )

        result = ValidationResult(
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
            degradation=degradation,
            validation_type="kfold",
            train_periods=int(len(dates) * (n_folds - 1) / n_folds),
            test_periods=int(len(dates) / n_folds),
            fold_results=fold_results,
        )

        logger.info(
            f"K-fold complete: Sharpe degradation={degradation.get('sharpe', 0):.1%}"
        )

        return result

    def validate_simple_split(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        universe: list[str] | None = None
    ) -> ValidationResult:
        """
        Simple train/test split validation.

        Args:
            factor: Factor to validate
            price_data: Price data
            start_date: Start date
            end_date: End date
            universe: Optional universe

        Returns:
            ValidationResult
        """
        logger.info(f"Simple split validation: {self.train_test_split:.0%} train")

        dates = sorted(price_data.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        # Split point
        split_idx = int(len(dates) * self.train_test_split)

        train_start = dates[0]
        train_end = dates[split_idx - 1]
        test_start = dates[split_idx]
        test_end = dates[-1]

        # Backtest on training data
        train_result = self.backtester.backtest(
            factor, price_data, train_start, train_end, universe
        )

        # Backtest on test data
        test_result = self.backtester.backtest(
            factor, price_data, test_start, test_end, universe
        )

        in_sample_metrics = {
            "sharpe": train_result.sharpe_ratio,
            "ic_mean": train_result.ic_mean,
            "ic_ir": train_result.ic_ir,
            "win_rate": train_result.win_rate,
            "max_drawdown": train_result.max_drawdown,
        }

        out_of_sample_metrics = {
            "sharpe": test_result.sharpe_ratio,
            "ic_mean": test_result.ic_mean,
            "ic_ir": test_result.ic_ir,
            "win_rate": test_result.win_rate,
            "max_drawdown": test_result.max_drawdown,
        }

        degradation = self._calculate_degradation(
            in_sample_metrics, out_of_sample_metrics
        )

        result = ValidationResult(
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
            degradation=degradation,
            validation_type="simple_split",
            train_periods=split_idx,
            test_periods=len(dates) - split_idx,
        )

        logger.info(
            f"Simple split complete: Sharpe degradation={degradation.get('sharpe', 0):.1%}"
        )

        return result

    def stability_analysis(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        window_size: int = 252,
        step_size: int = 21,
        universe: list[str] | None = None
    ) -> pd.DataFrame:
        """
        Analyze stability of factor performance over time.

        Args:
            factor: Factor to analyze
            price_data: Price data
            start_date: Start date
            end_date: End date
            window_size: Rolling window size
            step_size: Step between windows
            universe: Optional universe

        Returns:
            DataFrame with rolling metrics
        """
        logger.info(f"Stability analysis: {window_size}D windows")

        dates = sorted(price_data.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        stability_results = []

        for i in range(window_size, len(dates), step_size):
            window_start = dates[i - window_size]
            window_end = dates[i - 1]

            result = self.backtester.backtest(
                factor, price_data, window_start, window_end, universe
            )

            stability_results.append({
                "date": window_end,
                "sharpe": result.sharpe_ratio,
                "ic_mean": result.ic_mean,
                "ic_ir": result.ic_ir,
                "win_rate": result.win_rate,
                "max_drawdown": result.max_drawdown,
            })

        df = pd.DataFrame(stability_results).set_index("date")

        # Calculate stability metrics
        stability_metrics = {
            "sharpe_mean": df["sharpe"].mean(),
            "sharpe_std": df["sharpe"].std(),
            "sharpe_cv": df["sharpe"].std() / abs(df["sharpe"].mean()) if df["sharpe"].mean() != 0 else np.inf,
            "positive_sharpe_ratio": (df["sharpe"] > 0).mean(),
            "ic_mean": df["ic_mean"].mean(),
            "ic_std": df["ic_mean"].std(),
        }

        logger.info(
            f"Stability analysis complete: Sharpe CV={stability_metrics['sharpe_cv']:.2f}"
        )

        return df

    def robustness_test(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        universe: list[str] | None = None,
        n_bootstrap: int = 100
    ) -> dict[str, pd.Series]:
        """
        Test robustness using bootstrap resampling.

        Args:
            factor: Factor to test
            price_data: Price data
            start_date: Start date
            end_date: End date
            universe: Optional universe
            n_bootstrap: Number of bootstrap samples

        Returns:
            Dict of metric distributions
        """
        logger.info(f"Robustness test: {n_bootstrap} bootstrap samples")

        # Original backtest
        original_result = self.backtester.backtest(
            factor, price_data, start_date, end_date, universe
        )

        # Get rebalancing dates
        dates = sorted(price_data.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        # Bootstrap samples
        bootstrap_results = []

        for i in range(n_bootstrap):
            # Resample dates with replacement
            sampled_indices = np.random.choice(
                len(dates), size=len(dates), replace=True
            )
            sampled_dates = sorted([dates[idx] for idx in sampled_indices])

            # Create filtered data
            mask = price_data.index.get_level_values(0).isin(sampled_dates)
            sampled_data = price_data[mask]

            if len(sampled_dates) < 20:
                continue

            # Backtest on sampled data
            try:
                result = self.backtester.backtest(
                    factor, sampled_data,
                    sampled_dates[0], sampled_dates[-1],
                    universe
                )

                bootstrap_results.append({
                    "sharpe": result.sharpe_ratio,
                    "ic_mean": result.ic_mean,
                    "ic_ir": result.ic_ir,
                    "win_rate": result.win_rate,
                })
            except (ValueError, KeyError, TypeError, ZeroDivisionError):
                continue

        # Convert to distributions
        distributions = {}
        for metric in ["sharpe", "ic_mean", "ic_ir", "win_rate"]:
            distributions[metric] = pd.Series([r[metric] for r in bootstrap_results])

        logger.info(
            f"Robustness test complete: "
            f"Sharpe 95% CI=[{distributions['sharpe'].quantile(0.025):.3f}, "
            f"{distributions['sharpe'].quantile(0.975):.3f}]"
        )

        return distributions

    def _calculate_degradation(
        self,
        in_sample: dict[str, float],
        out_of_sample: dict[str, float]
    ) -> dict[str, float]:
        """Calculate performance degradation."""
        degradation = {}

        for metric in in_sample:
            if metric in out_of_sample:
                is_val = in_sample[metric]
                oos_val = out_of_sample[metric]

                if abs(is_val) > 1e-9:
                    deg = (oos_val - is_val) / abs(is_val)
                else:
                    deg = 0.0

                degradation[metric] = deg

        return degradation

    def _empty_result(self, validation_type: str) -> ValidationResult:
        """Return empty validation result."""
        return ValidationResult(
            in_sample_metrics={},
            out_of_sample_metrics={},
            degradation={},
            validation_type=validation_type,
            train_periods=0,
            test_periods=0,
        )
