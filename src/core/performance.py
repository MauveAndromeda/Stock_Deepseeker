"""Performance analysis utilities used across the test-suite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class PerformanceAnalyzer:
    """Compute common portfolio statistics from return series."""

    trading_days_per_year: int = 252

    # ------------------------------------------------------------------
    # Core metrics
    # ------------------------------------------------------------------
    def calculate_total_return(self, returns: Iterable[float] | pd.Series) -> float:
        series = self._to_series(returns)
        if series.empty:
            return 0.0
        compounded = (1 + series).prod()
        return float(compounded - 1)

    def calculate_sharpe_ratio(
        self,
        returns: Iterable[float] | pd.Series,
        risk_free_rate: float = 0.0
    ) -> float:
        series = self._to_series(returns)
        if series.empty:
            return 0.0

        excess = series - risk_free_rate / self.trading_days_per_year
        std = excess.std()
        if std == 0 or np.isnan(std):
            return 0.0

        mean = excess.mean()
        return float(np.sqrt(self.trading_days_per_year) * mean / std)

    def calculate_max_drawdown(
        self,
        returns: Iterable[float] | pd.Series
    ) -> float:
        series = self._to_series(returns)
        if series.empty:
            return 0.0

        equity = (1 + series).cumprod()
        running_max = equity.cummax()
        drawdowns = equity / running_max - 1.0
        return float(drawdowns.min())

    def calculate_win_rate(self, returns: Iterable[float] | pd.Series) -> float:
        series = self._to_series(returns)
        if series.empty:
            return 0.0

        wins = (series > 0).sum()
        total = len(series)
        return float(wins / total) if total else 0.0

    def calculate_sortino_ratio(
        self,
        returns: Iterable[float] | pd.Series,
        risk_free_rate: float = 0.0
    ) -> float:
        series = self._to_series(returns)
        if series.empty:
            return 0.0

        excess = series - risk_free_rate / self.trading_days_per_year
        downside = excess[excess < 0]
        if downside.empty:
            return float("inf")

        downside_std = downside.std()
        if downside_std == 0 or np.isnan(downside_std):
            return 0.0

        mean_excess = excess.mean()
        return float(np.sqrt(self.trading_days_per_year) * mean_excess / downside_std)

    # ------------------------------------------------------------------
    # Composite helper
    # ------------------------------------------------------------------
    def analyze(
        self,
        returns: Iterable[float] | pd.Series,
        risk_free_rate: float = 0.0
    ) -> dict[str, float]:
        series = self._to_series(returns)
        return {
            "total_return": self.calculate_total_return(series),
            "sharpe_ratio": self.calculate_sharpe_ratio(series, risk_free_rate),
            "max_drawdown": self.calculate_max_drawdown(series),
            "win_rate": self.calculate_win_rate(series),
            "sortino_ratio": self.calculate_sortino_ratio(series, risk_free_rate),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _to_series(data: Iterable[float] | pd.Series) -> pd.Series:
        if isinstance(data, pd.Series):
            return data.astype(float)

        values = list(data)
        if not values:
            return pd.Series(dtype=float)

        return pd.Series(values, dtype=float)


__all__ = ["PerformanceAnalyzer"]

