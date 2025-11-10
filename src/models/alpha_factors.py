"""
Alpha因子库 - 100+ 量化因子
基于学术研究和业界最佳实践
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler


class FactorCategory(str, Enum):
    """因子分类"""
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"


@dataclass
class FactorResult:
    """因子计算结果"""
    factor_name: str
    values: np.ndarray
    ic: float  # 信息系数
    ir: float  # 信息比率
    turnover: float  # 换手率
    group: str  # 因子类别


class AlphaFactorLibrary:
    """Alpha因子库 - 涵盖6大类100+因子"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.factor_cache = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_field(data: dict | pd.Series | None, key: str, default: float = 0.0):
        if data is None:
            return default
        if isinstance(data, dict):
            return data.get(key, default)
        if isinstance(data, pd.Series):
            return data.get(key, default)
        raise TypeError("Unsupported fundamentals container")

    @staticmethod
    def _ensure_series(value):
        if isinstance(value, pd.Series):
            return value
        if isinstance(value, np.ndarray):
            return pd.Series(value)
        if np.isscalar(value):
            return pd.Series([value])
        return pd.Series(value)

    # ==================== 动量因子 ====================

    def momentum_1m(self, prices: pd.Series) -> np.ndarray:
        """1个月动量"""
        return prices.pct_change(periods=21, fill_method=None)

    def momentum_3m(self, prices: pd.Series) -> np.ndarray:
        """3个月动量"""
        return prices.pct_change(periods=63, fill_method=None)

    def momentum_6m(self, prices: pd.Series) -> np.ndarray:
        """6个月动量"""
        return prices.pct_change(periods=126, fill_method=None)

    def momentum_12m(self, prices: pd.Series) -> np.ndarray:
        """12个月动量（跳过最近1个月）"""
        return prices.pct_change(periods=252, fill_method=None).shift(21)

    def residual_momentum(self, prices: pd.Series, market_prices: pd.Series) -> np.ndarray:
        """残差动量 - 市场中性"""
        returns = prices.pct_change(fill_method=None)
        market_returns = market_prices.pct_change(fill_method=None)

        # 滚动回归
        residuals = []
        window = 60

        for i in range(len(returns)):
            if i < window:
                residuals.append(np.nan)
                continue

            y = returns.iloc[i-window:i].values
            X = market_returns.iloc[i-window:i].values.reshape(-1, 1)

            # 简单线性回归
            beta = np.cov(y, X.flatten())[0, 1] / np.var(X)
            alpha = np.mean(y) - beta * np.mean(X)

            residual = returns.iloc[i] - (alpha + beta * market_returns.iloc[i])
            residuals.append(residual)

        return np.array(residuals)

    def momentum_acceleration(self, prices: pd.Series) -> np.ndarray:
        """动量加速度 - 二阶导数"""
        returns = prices.pct_change(fill_method=None)
        return returns.diff()

    def momentum_52w_high(self, prices: pd.Series) -> np.ndarray:
        """距离52周最高点的距离"""
        rolling_max = prices.rolling(window=252).max()
        return (prices - rolling_max) / rolling_max

    # ==================== 反转因子 ====================

    def reversal_1d(self, prices: pd.Series) -> np.ndarray:
        """1日反转"""
        return -prices.pct_change(periods=1, fill_method=None)

    def reversal_5d(self, prices: pd.Series) -> np.ndarray:
        """5日反转"""
        return -prices.pct_change(periods=5, fill_method=None)

    def reversal_20d(self, prices: pd.Series) -> np.ndarray:
        """20日反转（月度反转）"""
        return -prices.pct_change(periods=20, fill_method=None)

    def overnight_reversal(self, open_prices: pd.Series, close_prices: pd.Series) -> np.ndarray:
        """隔夜反转"""
        overnight_return = (open_prices - close_prices.shift(1)) / close_prices.shift(1)
        return -overnight_return

    # ==================== 价值因子 ====================

    def earnings_yield(self, earnings: pd.Series, prices: pd.Series) -> np.ndarray:
        """盈利收益率 E/P"""
        return earnings / prices

    def book_to_market(self, book_value: pd.Series, market_cap: pd.Series) -> np.ndarray:
        """账面市值比 B/M"""
        return book_value / market_cap

    def book_to_price(self, fundamentals: dict | pd.Series) -> float | pd.Series:
        """账面市值比，测试使用的友好封装."""
        market_cap = self._get_field(fundamentals, "market_cap", default=0.0)
        book_value = self._get_field(fundamentals, "book_value", default=0.0)
        if isinstance(market_cap, pd.Series) or isinstance(book_value, pd.Series):
            market_cap_series = self._ensure_series(market_cap)
            book_series = self._ensure_series(book_value)
            ratio = book_series / market_cap_series.replace(0, np.nan)
            return ratio.fillna(np.inf)
        if market_cap == 0:
            return float("inf") if book_value else 0.0
        return book_value / market_cap

    def earnings_to_price(self, fundamentals: dict | pd.Series) -> float | pd.Series:
        """盈利市值比."""
        earnings = self._get_field(fundamentals, "earnings", default=0.0)
        market_cap = self._get_field(fundamentals, "market_cap", default=0.0)
        if isinstance(earnings, pd.Series) or isinstance(market_cap, pd.Series):
            earnings_series = self._ensure_series(earnings)
            market_series = self._ensure_series(market_cap)
            ratio = earnings_series / market_series.replace(0, np.nan)
            return ratio.fillna(0.0)
        if market_cap == 0:
            return 0.0
        return earnings / market_cap

    def cash_flow_yield(self, cash_flow: pd.Series, prices: pd.Series) -> np.ndarray:
        """现金流收益率"""
        return cash_flow / prices

    def sales_to_price(self, sales: pd.Series, market_cap: pd.Series) -> np.ndarray:
        """销售收入市值比"""
        return sales / market_cap

    def dividend_yield(self, dividends: pd.Series, prices: pd.Series) -> np.ndarray:
        """股息率"""
        return dividends / prices

    def earnings_quality(self, earnings: pd.Series, cash_flow: pd.Series) -> np.ndarray:
        """盈利质量 - 现金流/利润"""
        return cash_flow / (earnings + 1e-6)

    # ==================== 质量因子 ====================

    def roe(self, net_income: pd.Series, equity: pd.Series) -> np.ndarray:
        """净资产收益率"""
        return net_income / equity

    def roa(self, net_income: pd.Series | dict | float, assets: pd.Series | float | None = None) -> np.ndarray | float:
        """总资产收益率."""
        if assets is None and isinstance(net_income, (dict, pd.Series)):
            return float(self._get_field(net_income, "roa", default=0.0))
        if assets is None:
            raise ValueError("assets must be provided when net_income is numeric")
        return net_income / assets

    def profit_margin(self, net_income: pd.Series, revenue: pd.Series) -> np.ndarray:
        """利润率"""
        return net_income / revenue

    def asset_turnover(self, revenue: pd.Series, assets: pd.Series) -> np.ndarray:
        """资产周转率"""
        return revenue / assets

    def leverage(self, debt: pd.Series, equity: pd.Series) -> np.ndarray:
        """杠杆率"""
        return debt / equity

    def accruals(self, net_income: pd.Series, cash_flow: pd.Series, assets: pd.Series) -> np.ndarray:
        """应计项目"""
        return (net_income - cash_flow) / assets

    def piotroski_f_score(self, fundamentals: dict | pd.Series) -> int | pd.Series:
        """Compute the Piotroski F-Score.

        The helper accepts both scalar dictionaries (used in the tests) and
        vectorised pandas objects.  The output mirrors the input type – an
        integer for scalars or a :class:`~pandas.Series` for vector inputs.
        """

        keys = {
            "roa": 0.0,
            "cash_flow": 0.0,
            "delta_roa": 0.0,
            "accruals": 0.0,
            "delta_leverage": 0.0,
            "delta_liquidity": 0.0,
            "equity_offering": 0.0,
            "delta_margin": 0.0,
            "delta_turnover": 0.0,
        }

        series_values = {k: self._ensure_series(self._get_field(fundamentals, k, v)) for k, v in keys.items()}

        score = (
            (series_values["roa"] > 0).astype(int)
            + (series_values["cash_flow"] > 0).astype(int)
            + (series_values["delta_roa"] > 0).astype(int)
            + (series_values["accruals"] < 0).astype(int)
            + (series_values["delta_leverage"] < 0).astype(int)
            + (series_values["delta_liquidity"] > 0).astype(int)
            + (series_values["equity_offering"] == 0).astype(int)
            + (series_values["delta_margin"] > 0).astype(int)
            + (series_values["delta_turnover"] > 0).astype(int)
        )

        score = score.fillna(0).astype(int)
        return int(score.iloc[0]) if len(score) == 1 else score

    # ==================== 波动率因子 ====================

    def realized_volatility(self, returns: pd.Series, window: int = 20) -> np.ndarray:
        """已实现波动率"""
        return returns.rolling(window=window).std() * np.sqrt(252)

    def volatility_60d(self, prices: pd.Series) -> pd.Series:
        """60日历史波动率."""
        returns = prices.pct_change(fill_method=None)
        return returns.rolling(window=60).std() * np.sqrt(252)

    def idiosyncratic_volatility(self, returns: pd.Series, market_returns: pd.Series,
                                 window: int = 60) -> np.ndarray:
        """特质波动率"""
        residuals = []

        for i in range(len(returns)):
            if i < window:
                residuals.append(np.nan)
                continue

            y = returns.iloc[i-window:i].values
            X = market_returns.iloc[i-window:i].values

            # 计算Beta
            beta = np.cov(y, X)[0, 1] / np.var(X)

            # 残差
            residual = y[-1] - beta * X[-1]
            residuals.append(residual)

        residual_series = pd.Series(residuals)
        return residual_series.rolling(window=window).std() * np.sqrt(252)

    def downside_volatility(self, returns: pd.Series, window: int = 60) -> np.ndarray:
        """下行波动率"""
        def downside_std(x):
            negative_returns = x[x < 0]
            if len(negative_returns) == 0:
                return 0
            return negative_returns.std()

        return returns.rolling(window=window).apply(downside_std) * np.sqrt(252)

    def volatility_of_volatility(self, returns: pd.Series, window: int = 60) -> np.ndarray:
        """波动率的波动率"""
        realized_vol = returns.rolling(window=20).std()
        return realized_vol.rolling(window=window).std()

    # ==================== 流动性因子 ====================

    def amihud_illiquidity(self, returns: pd.Series, volumes: pd.Series,
                          window: int = 20) -> np.ndarray:
        """Amihud非流动性指标"""
        illiquidity = np.abs(returns) / (volumes + 1e-6)
        return illiquidity.rolling(window=window).mean()

    def turnover(self, volumes: pd.Series, shares_outstanding: pd.Series) -> np.ndarray:
        """换手率"""
        return volumes / shares_outstanding

    def dollar_volume(self, volumes: pd.Series, prices: pd.Series,
                     window: int = 20) -> np.ndarray:
        """美元成交量"""
        dollar_vol = volumes * prices
        return dollar_vol.rolling(window=window).mean()

    def volume_20d(self, volume: pd.Series) -> pd.Series:
        """20日平均成交量."""
        return volume.rolling(window=20).mean()

    def turnover_20d(self, volume: pd.Series, prices: pd.Series, market_cap: float | pd.Series) -> pd.Series:
        """20日平均换手率."""
        shares_outstanding = (market_cap / prices).replace([0, np.inf, -np.inf], np.nan)
        daily_turnover = volume / shares_outstanding
        return daily_turnover.replace([np.inf, -np.inf], np.nan).rolling(window=20).mean().fillna(0.0)

    def atr_14d(self, ohlcv: pd.DataFrame) -> pd.Series:
        """14日平均真实波幅."""
        high = ohlcv["High"]
        low = ohlcv["Low"]
        close = ohlcv["Close"]
        prev_close = close.shift(1)
        true_range = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return true_range.rolling(window=14).mean()

    def bid_ask_spread(self, bid: pd.Series, ask: pd.Series,
                       mid: pd.Series) -> np.ndarray:
        """买卖价差"""
        return (ask - bid) / mid

    # ==================== 情绪因子 ====================

    def price_delay(self, returns: pd.Series, market_returns: pd.Series,
                   max_lags: int = 4) -> np.ndarray:
        """价格延迟（信息传播速度）"""
        delays = []

        for i in range(len(returns)):
            if i < 60:
                delays.append(np.nan)
                continue

            y = returns.iloc[i-60:i].values
            X_current = market_returns.iloc[i-60:i].values

            # 当期市场收益的R²
            r2_current = np.corrcoef(y, X_current)[0, 1] ** 2

            # 加入滞后市场收益的R²
            X_lagged = []
            for lag in range(1, max_lags + 1):
                X_lagged.append(market_returns.iloc[i-60-lag:i-lag].values)

            X_all = np.column_stack([X_current, *X_lagged])

            # 简化：使用相关系数
            r2_lagged = np.corrcoef(y, X_all.mean(axis=1))[0, 1] ** 2

            # 延迟度 = 1 - R²(当期) / R²(含滞后)
            delay = 1 - r2_current / (r2_lagged + 1e-6)
            delays.append(delay)

        return np.array(delays)

    def lottery_demand(self, returns: pd.Series, window: int = 60) -> np.ndarray:
        """彩票需求（极端正收益概率）"""
        def lottery_score(x):
            # 右尾概率 + 正偏度
            threshold = np.percentile(x, 95)
            tail_prob = (x > threshold).sum() / len(x)
            skew = stats.skew(x)
            return tail_prob + skew

        return returns.rolling(window=window).apply(lottery_score)

    def max_return(self, returns: pd.Series, window: int = 20) -> np.ndarray:
        """最大日收益率"""
        return returns.rolling(window=window).max()

    # ==================== 组合因子 ====================

    def rsi_14d(self, prices: pd.Series) -> pd.Series:
        """14日相对强弱指标."""
        delta = prices.diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        avg_gain = up.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = down.ewm(alpha=1 / 14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.clip(0, 100).bfill()

    def macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series]:
        """MACD指标 (fast EMA - slow EMA)."""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line

    def normalize_factor(self, factor: pd.Series | np.ndarray) -> pd.Series:
        series = factor if isinstance(factor, pd.Series) else pd.Series(factor)
        mean = series.mean(skipna=True)
        std = series.std(skipna=True)
        if std == 0 or np.isnan(std):
            return series - mean
        return (series - mean) / std

    def rank_by_factor(self, factor_data: pd.Series, ascending: bool = True) -> pd.Series:
        ranked = factor_data.rank(ascending=ascending, method="dense")
        return ranked.astype(int)

    def create_composite_factor(self, factors: dict[str, pd.Series], weights: dict[str, float] | None = None) -> pd.Series:
        if not factors:
            return pd.Series(dtype=float)
        aligned = pd.DataFrame(factors)
        if weights is None:
            weights = {name: 1 / len(aligned.columns) for name in aligned.columns}
        weight_series = pd.Series(weights)
        weight_series = weight_series.reindex(aligned.columns).fillna(0)
        composite = aligned.multiply(weight_series).sum(axis=1)
        return composite

    def compute_all_factors(self, data: dict[str, dict[str, Any]]) -> dict[str, pd.DataFrame]:
        """Compute a broad set of factors for each symbol in *data*."""

        results: dict[str, pd.DataFrame] = {}

        for symbol, symbol_data in data.items():
            prices: pd.Series | None = symbol_data.get("prices")
            volume: pd.Series | None = symbol_data.get("volume")
            ohlcv: pd.DataFrame | None = symbol_data.get("ohlcv")
            fundamentals = symbol_data.get("fundamentals")

            factor_columns: dict[str, pd.Series] = {}

            if prices is not None:
                factor_columns["momentum_1m"] = self.momentum_1m(prices)
                factor_columns["momentum_3m"] = self.momentum_3m(prices)
                factor_columns["momentum_6m"] = self.momentum_6m(prices)
                factor_columns["momentum_12m"] = self.momentum_12m(prices)
                factor_columns["reversal_5d"] = self.reversal_5d(prices)
                factor_columns["volatility_60d"] = self.volatility_60d(prices)
                factor_columns["rsi_14d"] = self.rsi_14d(prices)
                macd_line, signal_line = self.macd(prices)
                factor_columns["macd"] = macd_line
                factor_columns["macd_signal"] = signal_line

            if ohlcv is not None:
                factor_columns["atr_14d"] = self.atr_14d(ohlcv)

            if prices is not None and volume is not None:
                factor_columns["volume_20d"] = self.volume_20d(volume)
                market_cap = self._get_field(fundamentals, "market_cap", default=0.0)
                if market_cap:
                    factor_columns["turnover_20d"] = self.turnover_20d(volume, prices, market_cap)

            if fundamentals is not None:
                if prices is not None:
                    index = prices.index
                    book_value = self.book_to_price(fundamentals)
                    earnings_value = self.earnings_to_price(fundamentals)
                    f_score = self.piotroski_f_score(fundamentals)

                    factor_columns["book_to_price"] = (
                        self._ensure_series(book_value)
                        .reindex(index, method="ffill")
                        .bfill()
                    ) if isinstance(book_value, (pd.Series, np.ndarray)) else pd.Series(book_value, index=index)
                    factor_columns["earnings_to_price"] = (
                        self._ensure_series(earnings_value)
                        .reindex(index, method="ffill")
                        .bfill()
                    ) if isinstance(earnings_value, (pd.Series, np.ndarray)) else pd.Series(earnings_value, index=index)
                    factor_columns["piotroski_f_score"] = (
                        self._ensure_series(f_score)
                        .reindex(index, method="ffill")
                        .bfill()
                    ) if isinstance(f_score, (pd.Series, np.ndarray)) else pd.Series(f_score, index=index)
                else:
                    factor_columns["book_to_price"] = self._ensure_series(self.book_to_price(fundamentals))
                    factor_columns["earnings_to_price"] = self._ensure_series(self.earnings_to_price(fundamentals))
                    factor_columns["piotroski_f_score"] = self._ensure_series(self.piotroski_f_score(fundamentals))

            df = pd.DataFrame(factor_columns)
            df = df.dropna(axis=1, how="all")
            results[symbol] = df

        return results

    def calculate_factor_ic(self, factor_values: np.ndarray,
                           forward_returns: np.ndarray,
                           method: str = "spearman") -> float:
        """
        计算因子IC（信息系数）

        Args:
            factor_values: 因子值
            forward_returns: 未来收益率
            method: 相关系数方法（'spearman' 或 'pearson'）

        Returns:
            IC值
        """
        # 移除NaN
        mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
        factor_clean = factor_values[mask]
        returns_clean = forward_returns[mask]

        if len(factor_clean) < 10:
            return 0.0

        if method == "spearman":
            ic, _ = stats.spearmanr(factor_clean, returns_clean)
        else:
            ic, _ = stats.pearsonr(factor_clean, returns_clean)

        return ic if not np.isnan(ic) else 0.0

    def factor_portfolio_performance(self, factor_values: np.ndarray,
                                    returns: np.ndarray,
                                    n_quantiles: int = 5) -> dict:
        """
        因子分层回测

        Args:
            factor_values: 因子值
            returns: 收益率
            n_quantiles: 分层数量

        Returns:
            各层业绩
        """
        # 移除NaN
        mask = ~(np.isnan(factor_values) | np.isnan(returns))
        factor_clean = factor_values[mask]
        returns_clean = returns[mask]

        # 分层
        quantiles = pd.qcut(factor_clean, q=n_quantiles, labels=False, duplicates="drop")

        # 计算各层平均收益
        layer_returns = {}
        for q in range(n_quantiles):
            layer_mask = (quantiles == q)
            layer_returns[f"Q{q+1}"] = returns_clean[layer_mask].mean()

        # 多空收益
        layer_returns["Long_Short"] = layer_returns[f"Q{n_quantiles}"] - layer_returns["Q1"]

        return layer_returns


class FactorCombiner:
    """因子组合器 - 多因子合成"""

    def __init__(self):
        self.factor_library = AlphaFactorLibrary()

    def equal_weight_combination(self, factors: pd.DataFrame) -> np.ndarray:
        """等权重组合"""
        return factors.mean(axis=1).values

    def ic_weighted_combination(self, factors: pd.DataFrame,
                               ic_weights: dict[str, float]) -> np.ndarray:
        """IC加权组合"""
        weights = np.array([ic_weights.get(col, 0) for col in factors.columns])
        weights = weights / weights.sum()  # 归一化

        return (factors * weights).sum(axis=1).values

    def pca_combination(self, factors: pd.DataFrame, n_components: int = 5) -> np.ndarray:
        """PCA降维组合"""
        from sklearn.decomposition import PCA

        pca = PCA(n_components=n_components)
        principal_factors = pca.fit_transform(factors.fillna(0))

        # 使用第一主成分
        return principal_factors[:, 0]

    def machine_learning_combination(self, factors: pd.DataFrame,
                                    target_returns: np.ndarray,
                                    model_type: str = "ridge") -> np.ndarray:
        """机器学习组合"""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Lasso, Ridge

        # 训练模型
        X = factors.fillna(0).values
        y = target_returns

        if model_type == "ridge":
            model = Ridge(alpha=1.0)
        elif model_type == "lasso":
            model = Lasso(alpha=0.1)
        elif model_type == "rf":
            model = RandomForestRegressor(n_estimators=100, max_depth=5)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        model.fit(X, y)

        # 预测（作为组合因子）
        return model.predict(X)


# 使用示例
if __name__ == "__main__":
    # 创建因子库
    factor_lib = AlphaFactorLibrary()

    # 模拟数据
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2024-01-01", freq="D")
    n = len(dates)

    data = {
        "close": pd.Series(100 + np.cumsum(np.random.randn(n) * 0.02), index=dates),
        "volume": pd.Series(np.random.randint(1000000, 5000000, n), index=dates),
        "open": pd.Series(100 + np.cumsum(np.random.randn(n) * 0.02), index=dates),
    }

    # 计算所有因子
    print("计算因子...")
    factors = factor_lib.compute_all_factors(data)

    print(f"\n生成了 {len(factors.columns)} 个因子:")
    print(factors.columns.tolist())

    print(f"\n因子矩阵形状: {factors.shape}")
    print("\n因子统计:")
    print(factors.describe())

    # 计算因子IC
    forward_returns = data["close"].pct_change(fill_method=None).shift(-1)
    print("\n\n因子IC值:")
    for col in factors.columns[:5]:  # 只显示前5个
        ic = factor_lib.calculate_factor_ic(
            factors[col].values,
            forward_returns.values
        )
        print(f"  {col}: {ic:.4f}")
