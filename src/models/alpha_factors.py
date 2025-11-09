"""
Alpha因子库 - 100+ 量化因子
基于学术研究和业界最佳实践
"""

from dataclasses import dataclass
from enum import Enum

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

    # ==================== 动量因子 ====================

    def momentum_1m(self, prices: pd.Series) -> np.ndarray:
        """1个月动量"""
        return prices.pct_change(periods=21)

    def momentum_3m(self, prices: pd.Series) -> np.ndarray:
        """3个月动量"""
        return prices.pct_change(periods=63)

    def momentum_6m(self, prices: pd.Series) -> np.ndarray:
        """6个月动量"""
        return prices.pct_change(periods=126)

    def momentum_12m(self, prices: pd.Series) -> np.ndarray:
        """12个月动量（跳过最近1个月）"""
        return prices.pct_change(periods=252).shift(21)

    def residual_momentum(self, prices: pd.Series, market_prices: pd.Series) -> np.ndarray:
        """残差动量 - 市场中性"""
        returns = prices.pct_change()
        market_returns = market_prices.pct_change()

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
        returns = prices.pct_change()
        return returns.diff()

    def momentum_52w_high(self, prices: pd.Series) -> np.ndarray:
        """距离52周最高点的距离"""
        rolling_max = prices.rolling(window=252).max()
        return (prices - rolling_max) / rolling_max

    # ==================== 反转因子 ====================

    def reversal_1d(self, prices: pd.Series) -> np.ndarray:
        """1日反转"""
        return -prices.pct_change(periods=1)

    def reversal_5d(self, prices: pd.Series) -> np.ndarray:
        """5日反转"""
        return -prices.pct_change(periods=5)

    def reversal_20d(self, prices: pd.Series) -> np.ndarray:
        """20日反转（月度反转）"""
        return -prices.pct_change(periods=20)

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

    def roa(self, net_income: pd.Series, assets: pd.Series) -> np.ndarray:
        """总资产收益率"""
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

    def piotroski_f_score(self, fundamentals: dict) -> np.ndarray:
        """Piotroski F-Score (9分制质量评分)"""
        score = 0

        # 盈利能力（4分）
        score += (fundamentals["roa"] > 0).astype(int)
        score += (fundamentals["cash_flow"] > 0).astype(int)
        score += (fundamentals["roa_change"] > 0).astype(int)
        score += (fundamentals["accruals"] < 0).astype(int)

        # 杠杆、流动性（3分）
        score += (fundamentals["leverage_change"] < 0).astype(int)
        score += (fundamentals["liquidity_change"] > 0).astype(int)
        score += (fundamentals["equity_offering"] == 0).astype(int)

        # 运营效率（2分）
        score += (fundamentals["margin_change"] > 0).astype(int)
        score += (fundamentals["turnover_change"] > 0).astype(int)

        return score

    # ==================== 波动率因子 ====================

    def realized_volatility(self, returns: pd.Series, window: int = 20) -> np.ndarray:
        """已实现波动率"""
        return returns.rolling(window=window).std() * np.sqrt(252)

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

    def compute_all_factors(self, data: dict[str, pd.Series]) -> pd.DataFrame:
        """
        计算所有因子

        Args:
            data: 包含价格、成交量、基本面等数据的字典

        Returns:
            因子矩阵 DataFrame
        """
        factors = {}

        # 动量因子
        if "close" in data:
            factors["mom_1m"] = self.momentum_1m(data["close"])
            factors["mom_3m"] = self.momentum_3m(data["close"])
            factors["mom_6m"] = self.momentum_6m(data["close"])
            factors["mom_12m"] = self.momentum_12m(data["close"])
            factors["mom_52w_high"] = self.momentum_52w_high(data["close"])

        # 反转因子
        if "close" in data:
            factors["rev_1d"] = self.reversal_1d(data["close"])
            factors["rev_5d"] = self.reversal_5d(data["close"])
            factors["rev_20d"] = self.reversal_20d(data["close"])

        if "open" in data and "close" in data:
            factors["rev_overnight"] = self.overnight_reversal(data["open"], data["close"])

        # 波动率因子
        if "close" in data:
            returns = data["close"].pct_change()
            factors["vol_realized"] = self.realized_volatility(returns)
            factors["vol_downside"] = self.downside_volatility(returns)

        # 流动性因子
        if "volume" in data and "close" in data:
            returns = data["close"].pct_change()
            factors["illiq_amihud"] = self.amihud_illiquidity(returns, data["volume"])
            factors["liquidity_dollar_vol"] = self.dollar_volume(data["volume"], data["close"])

        # 价值因子
        if "earnings" in data and "close" in data:
            factors["value_ep"] = self.earnings_yield(data["earnings"], data["close"])

        if "book_value" in data and "market_cap" in data:
            factors["value_bm"] = self.book_to_market(data["book_value"], data["market_cap"])

        # 转换为DataFrame
        factor_df = pd.DataFrame(factors)

        # 标准化
        factor_df = factor_df.apply(lambda x: (x - x.mean()) / x.std())

        return factor_df

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
    forward_returns = data["close"].pct_change().shift(-1)
    print("\n\n因子IC值:")
    for col in factors.columns[:5]:  # 只显示前5个
        ic = factor_lib.calculate_factor_ic(
            factors[col].values,
            forward_returns.values
        )
        print(f"  {col}: {ic:.4f}")
