"""
Volatility arbitrage strategy trading realized vs implied volatility.
"""

from collections import deque

import numpy as np

from src.strategies.base import BaseStrategy, Signal, SignalType


class VolatilityArbitrageStrategy(BaseStrategy):
    """
    Volatility arbitrage strategy exploiting mispricing between
    realized and implied volatility.

    The strategy identifies situations where:
    - Implied volatility > Expected realized volatility → Sell volatility
    - Implied volatility < Expected realized volatility → Buy volatility

    In practice, this would involve options trading. This implementation
    provides a simplified version using volatility ETFs or long/short
    positions with dynamic hedging.

    Parameters:
        vol_lookback: Lookback period for realized volatility calculation
        forecast_horizon: Forecast horizon for volatility prediction
        entry_threshold: Threshold for implied vs realized vol spread (std devs)
        exit_threshold: Threshold for position exit
        max_positions: Maximum number of volatility pairs
        use_garch: Use GARCH model for volatility forecasting
        hedge_frequency: Days between delta hedging
    """

    def __init__(
        self,
        vol_lookback: int = 60,
        forecast_horizon: int = 21,
        entry_threshold: float = 1.5,
        exit_threshold: float = 0.5,
        max_positions: int = 10,
        use_garch: bool = False,
        hedge_frequency: int = 1,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.vol_lookback = vol_lookback
        self.forecast_horizon = forecast_horizon
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_positions = max_positions
        self.use_garch = use_garch
        self.hedge_frequency = hedge_frequency

        # State
        self.price_history: dict[str, deque] = {}
        self.implied_vol_history: dict[str, deque] = {}
        self.realized_vol: dict[str, float] = {}
        self.forecasted_vol: dict[str, float] = {}
        self.vol_positions: dict[str, tuple[float, float]] = {}  # symbol -> (entry_spread, entry_day)
        self.last_hedge_day = 0

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting VolatilityArbitrageStrategy with {self.max_positions} max positions"
        )
        self.logger.info(
            f"Entry threshold: {self.entry_threshold} std devs, "
            f"Vol lookback: {self.vol_lookback} days"
        )

    def on_data(self, data: dict) -> list[Signal]:
        """
        Generate volatility arbitrage signals.

        Args:
            data: Market data containing:
                - prices: Dict[symbol, price]
                - implied_vols: Dict[symbol, implied_vol] (if available)
                - options_data: Dict[symbol, options_chain] (optional)

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update price history
        if "prices" in data:
            for symbol, price in data["prices"].items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = deque(maxlen=self.vol_lookback * 2)
                self.price_history[symbol].append(price)

        # Update implied volatility
        if "implied_vols" in data:
            for symbol, iv in data["implied_vols"].items():
                if symbol not in self.implied_vol_history:
                    self.implied_vol_history[symbol] = deque(maxlen=252)
                self.implied_vol_history[symbol].append(iv)

        # Calculate realized and forecasted volatility
        self._update_volatility_estimates()

        # Generate trading signals
        signals = []

        # Check for new entry opportunities
        entry_signals = self._generate_entry_signals()
        signals.extend(entry_signals)

        # Check for exit signals
        exit_signals = self._generate_exit_signals()
        signals.extend(exit_signals)

        # Delta hedging
        if self.days_elapsed - self.last_hedge_day >= self.hedge_frequency:
            hedge_signals = self._generate_hedge_signals()
            signals.extend(hedge_signals)
            self.last_hedge_day = self.days_elapsed

        return signals

    def _update_volatility_estimates(self) -> None:
        """Calculate realized and forecasted volatility for all symbols."""
        for symbol in self.price_history.keys():
            prices = list(self.price_history[symbol])

            if len(prices) < self.vol_lookback:
                continue

            # Calculate realized volatility
            returns = np.diff(prices[-self.vol_lookback:]) / prices[-self.vol_lookback:-1]
            realized_vol = np.std(returns) * np.sqrt(252)  # Annualized
            self.realized_vol[symbol] = realized_vol

            # Forecast future volatility
            if self.use_garch:
                forecasted_vol = self._garch_forecast(returns)
            else:
                # Simple EWMA forecast
                forecasted_vol = self._ewma_forecast(returns)

            self.forecasted_vol[symbol] = forecasted_vol

    def _ewma_forecast(self, returns: np.ndarray) -> float:
        """
        Forecast volatility using Exponentially Weighted Moving Average.

        Args:
            returns: Historical returns

        Returns:
            Forecasted volatility (annualized)
        """
        lambda_param = 0.94  # RiskMetrics parameter
        weights = np.array([lambda_param ** i for i in range(len(returns))])
        weights = weights[::-1] / weights.sum()

        variance = np.sum(weights * returns ** 2)
        vol = np.sqrt(variance * 252)

        return vol

    def _garch_forecast(self, returns: np.ndarray) -> float:
        """
        Forecast volatility using GARCH(1,1) model.

        This is a simplified version. In production, use statsmodels or arch library.

        Args:
            returns: Historical returns

        Returns:
            Forecasted volatility (annualized)
        """
        # Simplified GARCH(1,1) parameters (typically estimated via MLE)
        omega = 0.000001  # Long-run variance
        alpha = 0.08      # Reaction to market shocks
        beta = 0.90       # Persistence

        # Calculate current variance estimate
        variance = np.var(returns)

        # One-step ahead forecast: h_t+1 = omega + alpha * r_t^2 + beta * h_t
        forecast_variance = omega + alpha * (returns[-1] ** 2) + beta * variance

        # Multi-step ahead (approximate)
        for _ in range(self.forecast_horizon):
            forecast_variance = omega + (alpha + beta) * forecast_variance

        vol = np.sqrt(forecast_variance * 252)

        return vol

    def _generate_entry_signals(self) -> list[Signal]:
        """Generate entry signals for vol arbitrage opportunities."""
        signals = []

        if len(self.vol_positions) >= self.max_positions:
            return signals

        # Calculate vol spreads
        vol_spreads = {}

        for symbol in self.forecasted_vol.keys():
            if symbol not in self.implied_vol_history or len(self.implied_vol_history[symbol]) == 0:
                continue

            implied_vol = self.implied_vol_history[symbol][-1]
            forecasted_vol = self.forecasted_vol[symbol]

            # Calculate spread (standardized)
            spread = implied_vol - forecasted_vol

            # Standardize by historical volatility of the spread
            if len(self.implied_vol_history[symbol]) >= 30:
                hist_implied = list(self.implied_vol_history[symbol])[-30:]
                hist_realized = [self.realized_vol.get(symbol, forecasted_vol)] * 30
                hist_spreads = np.array(hist_implied) - np.array(hist_realized)
                spread_std = np.std(hist_spreads)

                if spread_std > 0:
                    z_score = spread / spread_std
                    vol_spreads[symbol] = (spread, z_score)

        # Find significant mispricings
        for symbol, (spread, z_score) in vol_spreads.items():
            if symbol in self.vol_positions:
                continue

            # Entry conditions
            if abs(z_score) >= self.entry_threshold:
                if z_score > 0:
                    # Implied vol > Forecasted vol → Sell volatility
                    # In practice: sell options / short vol ETF
                    signal_type = SignalType.SELL
                    direction = "SELL_VOL"
                else:
                    # Implied vol < Forecasted vol → Buy volatility
                    # In practice: buy options / long vol ETF
                    signal_type = SignalType.BUY
                    direction = "BUY_VOL"

                signals.append(Signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=min(1.0, abs(z_score) / 3.0),  # Cap at 3 std devs
                    metadata={
                        "strategy": "vol_arbitrage",
                        "direction": direction,
                        "implied_vol": self.implied_vol_history[symbol][-1],
                        "forecasted_vol": self.forecasted_vol[symbol],
                        "spread": spread,
                        "z_score": z_score
                    }
                ))

                # Track position
                self.vol_positions[symbol] = (z_score, self.days_elapsed)

                if len(signals) + len(self.vol_positions) >= self.max_positions:
                    break

        return signals

    def _generate_exit_signals(self) -> list[Signal]:
        """Generate exit signals for existing vol positions."""
        signals = []

        for symbol in list(self.vol_positions.keys()):
            if symbol not in self.implied_vol_history or symbol not in self.forecasted_vol:
                continue

            entry_z_score, entry_day = self.vol_positions[symbol]

            # Calculate current spread
            implied_vol = self.implied_vol_history[symbol][-1]
            forecasted_vol = self.forecasted_vol[symbol]
            current_spread = implied_vol - forecasted_vol

            # Recalculate z-score
            if len(self.implied_vol_history[symbol]) >= 30:
                hist_implied = list(self.implied_vol_history[symbol])[-30:]
                hist_realized = [self.realized_vol.get(symbol, forecasted_vol)] * 30
                hist_spreads = np.array(hist_implied) - np.array(hist_realized)
                spread_std = np.std(hist_spreads)

                if spread_std > 0:
                    current_z_score = current_spread / spread_std
                else:
                    current_z_score = 0.0
            else:
                current_z_score = 0.0

            # Exit conditions
            exit_signal = False

            # 1. Spread has normalized
            if abs(current_z_score) < self.exit_threshold:
                exit_signal = True
                reason = "spread_normalized"

            # 2. Spread has reversed significantly
            elif np.sign(current_z_score) != np.sign(entry_z_score):
                exit_signal = True
                reason = "spread_reversed"

            # 3. Maximum holding period (e.g., 60 days)
            elif self.days_elapsed - entry_day > 60:
                exit_signal = True
                reason = "max_holding_period"

            if exit_signal:
                # Close position
                signal_type = SignalType.BUY if entry_z_score > 0 else SignalType.SELL

                signals.append(Signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=1.0,
                    metadata={
                        "strategy": "vol_arbitrage_exit",
                        "reason": reason,
                        "holding_days": self.days_elapsed - entry_day
                    }
                ))

                # Remove from tracking
                del self.vol_positions[symbol]

        return signals

    def _generate_hedge_signals(self) -> list[Signal]:
        """
        Generate delta hedging signals.

        For option positions, we would calculate delta and hedge.
        This is a placeholder for the hedging logic.
        """
        # In a full implementation, this would:
        # 1. Calculate current portfolio delta
        # 2. Generate hedge orders to maintain delta neutrality
        # 3. Rebalance gamma exposure if needed

        return []

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        metadata = signal.metadata
        if "z_score" in metadata:
            self.logger.info(
                f"Vol arbitrage entry: {metadata['direction']} {signal.symbol} "
                f"(IV={metadata['implied_vol']:.2%}, FV={metadata['forecasted_vol']:.2%}, "
                f"z={metadata['z_score']:.2f})"
            )
        else:
            self.logger.info(
                f"Vol arbitrage exit: {signal.signal_type.value} {signal.symbol} "
                f"(reason={metadata.get('reason', 'unknown')})"
            )

    def on_fill(self, symbol: str, quantity: float, price: float) -> None:
        """Handle order fill."""
        if quantity > 0:
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            if abs(self.positions[symbol]) < 1e-6:
                del self.positions[symbol]

    def on_stop(self) -> None:
        """Cleanup on strategy stop."""
        self.logger.info("Stopping VolatilityArbitrageStrategy")
        self.logger.info(f"Open vol positions: {len(self.vol_positions)}")
