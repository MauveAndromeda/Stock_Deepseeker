"""
Trading Environment for Reinforcement Learning
Gym-compatible environment for stock trading
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict
from loguru import logger


class TradingEnvironment(gym.Env):
    """
    Stock Trading Environment
    Supports continuous action space for position sizing
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        max_position: float = 1.0,
        reward_scaling: float = 1e-4,
    ):
        """
        Args:
            df: DataFrame with OHLCV and features
            initial_balance: Initial account balance
            commission: Commission rate (e.g., 0.001 = 0.1%)
            slippage: Slippage rate
            max_position: Maximum position size (1.0 = 100% of equity)
            reward_scaling: Scaling factor for rewards
        """
        super().__init__()

        self.df = df.copy()
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        self.max_position = max_position
        self.reward_scaling = reward_scaling

        # State space: features from DataFrame
        self.num_features = len(df.columns)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.num_features,),
            dtype=np.float32,
        )

        # Action space: continuous [-1, 1]
        # -1 = full short, 0 = neutral, 1 = full long
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        )

        # Episode state
        self.current_step = 0
        self.balance = initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.equity_curve = []
        self.trade_history = []

        logger.info(
            f"Trading environment initialized: "
            f"{len(df)} steps, {self.num_features} features"
        )

    def reset(
        self, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> Tuple[np.ndarray, dict]:
        """Reset environment to initial state"""
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.equity_curve = [self.initial_balance]
        self.trade_history = []

        return self._get_observation(), self._get_info()

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """
        Execute one trading step

        Args:
            action: Trading action [-1, 1]

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Get current price
        current_price = self.df.iloc[self.current_step]["close"]

        # Execute trade
        action_value = np.clip(action[0], -1.0, 1.0)
        reward = self._execute_trade(action_value, current_price)

        # Move to next step
        self.current_step += 1

        # Check if episode is done
        terminated = self.current_step >= len(self.df) - 1
        truncated = False

        # Get new observation
        observation = self._get_observation()
        info = self._get_info()

        # Track equity
        total_equity = self._calculate_total_equity(current_price)
        self.equity_curve.append(total_equity)

        return observation, reward, terminated, truncated, info

    def _execute_trade(self, action: float, price: float) -> float:
        """
        Execute trade and calculate reward

        Args:
            action: Desired position [-1, 1]
            price: Current price

        Returns:
            Reward value
        """
        # Calculate previous equity
        prev_equity = self._calculate_total_equity(price)

        # Calculate position change
        target_position = action * self.max_position
        position_change = target_position - self.position

        # Execute trade if position changes
        if abs(position_change) > 0.01:  # Minimum trade size
            # Calculate trade cost
            trade_value = abs(position_change) * price * self.balance
            trade_cost = trade_value * (self.commission + self.slippage)

            # Update balance (subtract trade cost)
            self.balance -= trade_cost

            # Update position
            self.position = target_position

            # Track trade
            self.trade_history.append(
                {
                    "step": self.current_step,
                    "action": action,
                    "position": self.position,
                    "price": price,
                    "cost": trade_cost,
                }
            )

        # Calculate new equity
        new_equity = self._calculate_total_equity(price)

        # Calculate reward (change in equity)
        reward = (new_equity - prev_equity) * self.reward_scaling

        # Add penalty for excessive trading
        if abs(position_change) > 0.5:
            reward -= 0.01

        return reward

    def _calculate_total_equity(self, current_price: float) -> float:
        """Calculate total equity (balance + position value)"""
        position_value = self.position * self.balance * current_price
        return self.balance + position_value

    def _get_observation(self) -> np.ndarray:
        """Get current observation (state)"""
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1

        obs = self.df.iloc[self.current_step].values.astype(np.float32)

        return obs

    def _get_info(self) -> dict:
        """Get additional info about current state"""
        current_price = self.df.iloc[self.current_step]["close"]
        total_equity = self._calculate_total_equity(current_price)

        return {
            "step": self.current_step,
            "balance": self.balance,
            "position": self.position,
            "total_equity": total_equity,
            "return": (total_equity / self.initial_balance) - 1,
            "num_trades": len(self.trade_history),
        }

    def render(self, mode: str = "human"):
        """Render environment state"""
        info = self._get_info()
        logger.info(
            f"Step: {info['step']}, "
            f"Equity: ${info['total_equity']:.2f}, "
            f"Return: {info['return']:.2%}, "
            f"Position: {info['position']:.2f}"
        )


class MultiAssetTradingEnvironment(gym.Env):
    """
    Multi-asset trading environment
    Allows trading multiple stocks simultaneously
    """

    def __init__(
        self,
        data_dict: Dict[str, pd.DataFrame],
        initial_balance: float = 100000.0,
        commission: float = 0.001,
        max_position_per_asset: float = 0.2,
    ):
        """
        Args:
            data_dict: Dictionary of symbol -> DataFrame
            initial_balance: Initial balance
            commission: Commission rate
            max_position_per_asset: Max position size per asset
        """
        super().__init__()

        self.data_dict = data_dict
        self.symbols = list(data_dict.keys())
        self.num_assets = len(self.symbols)
        self.initial_balance = initial_balance
        self.commission = commission
        self.max_position_per_asset = max_position_per_asset

        # Align all dataframes to common index
        self._align_data()

        # Observation space: features for all assets
        num_features_per_asset = len(
            next(iter(data_dict.values())).columns
        )
        total_features = num_features_per_asset * self.num_assets + 1  # +1 for cash

        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(total_features,), dtype=np.float32
        )

        # Action space: position for each asset [-1, 1]
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.num_assets,),
            dtype=np.float32,
        )

        # State
        self.current_step = 0
        self.balance = initial_balance
        self.positions = {symbol: 0.0 for symbol in self.symbols}
        self.equity_curve = []

        logger.info(
            f"Multi-asset environment initialized: "
            f"{self.num_assets} assets, {total_features} features"
        )

    def _align_data(self):
        """Align all dataframes to common index"""
        # Find common index (intersection of all indices)
        common_index = self.data_dict[self.symbols[0]].index
        for symbol in self.symbols[1:]:
            common_index = common_index.intersection(
                self.data_dict[symbol].index
            )

        # Reindex all dataframes
        for symbol in self.symbols:
            self.data_dict[symbol] = self.data_dict[symbol].loc[common_index]

        self.max_steps = len(common_index)

    def reset(
        self, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> Tuple[np.ndarray, dict]:
        """Reset environment"""
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.positions = {symbol: 0.0 for symbol in self.symbols}
        self.equity_curve = [self.initial_balance]

        return self._get_observation(), {}

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """Execute trading step for all assets"""
        # Clip actions
        action = np.clip(action, -1.0, 1.0)

        # Get current prices
        prices = self._get_current_prices()

        # Execute trades for each asset
        total_reward = 0.0
        for i, symbol in enumerate(self.symbols):
            reward = self._execute_trade_for_asset(
                symbol, action[i], prices[symbol]
            )
            total_reward += reward

        # Move to next step
        self.current_step += 1
        terminated = self.current_step >= self.max_steps - 1

        # Track equity
        total_equity = self._calculate_total_equity()
        self.equity_curve.append(total_equity)

        observation = self._get_observation()
        info = self._get_info()

        return observation, total_reward, terminated, False, info

    def _get_current_prices(self) -> Dict[str, float]:
        """Get current prices for all assets"""
        prices = {}
        for symbol in self.symbols:
            prices[symbol] = self.data_dict[symbol].iloc[self.current_step][
                "close"
            ]
        return prices

    def _execute_trade_for_asset(
        self, symbol: str, action: float, price: float
    ) -> float:
        """Execute trade for single asset"""
        target_position = action * self.max_position_per_asset
        position_change = target_position - self.positions[symbol]

        if abs(position_change) > 0.01:
            trade_value = abs(position_change) * price * self.balance
            trade_cost = trade_value * self.commission

            self.balance -= trade_cost
            self.positions[symbol] = target_position

        return 0.0  # Reward calculated at portfolio level

    def _calculate_total_equity(self) -> float:
        """Calculate total portfolio equity"""
        equity = self.balance

        prices = self._get_current_prices()
        for symbol in self.symbols:
            position_value = (
                self.positions[symbol] * self.balance * prices[symbol]
            )
            equity += position_value

        return equity

    def _get_observation(self) -> np.ndarray:
        """Get observation for all assets"""
        obs_list = []

        # Add features for each asset
        for symbol in self.symbols:
            asset_obs = self.data_dict[symbol].iloc[
                self.current_step
            ].values
            obs_list.append(asset_obs)

        # Add normalized balance
        obs_list.append([self.balance / self.initial_balance])

        return np.concatenate(obs_list).astype(np.float32)

    def _get_info(self) -> dict:
        """Get environment info"""
        total_equity = self._calculate_total_equity()

        return {
            "step": self.current_step,
            "total_equity": total_equity,
            "return": (total_equity / self.initial_balance) - 1,
            "positions": self.positions.copy(),
        }
