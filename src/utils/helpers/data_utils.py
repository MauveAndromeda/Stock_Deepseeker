"""
Data processing utilities
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Union, List
from scipy import stats
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from loguru import logger


def normalize_data(
    data: Union[pd.DataFrame, pd.Series, np.ndarray],
    method: str = "minmax",
    feature_range: Tuple[float, float] = (0, 1),
) -> Union[pd.DataFrame, pd.Series, np.ndarray]:
    """
    Normalize data using various methods

    Args:
        data: Input data
        method: Normalization method ('minmax', 'zscore', 'robust')
        feature_range: Target range for minmax scaling

    Returns:
        Normalized data
    """
    if isinstance(data, (pd.DataFrame, pd.Series)):
        is_dataframe = isinstance(data, pd.DataFrame)
        is_series = isinstance(data, pd.Series)
        index = data.index
        columns = data.columns if is_dataframe else None
        values = data.values
    else:
        is_dataframe = False
        is_series = False
        values = data
        index = None
        columns = None

    if values.ndim == 1:
        values = values.reshape(-1, 1)

    if method == "minmax":
        scaler = MinMaxScaler(feature_range=feature_range)
    elif method == "zscore":
        scaler = StandardScaler()
    elif method == "robust":
        scaler = RobustScaler()
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    normalized = scaler.fit_transform(values)

    if is_dataframe:
        return pd.DataFrame(normalized, index=index, columns=columns)
    elif is_series:
        return pd.Series(normalized.flatten(), index=index)
    else:
        return normalized.flatten() if data.ndim == 1 else normalized


def standardize_data(
    data: Union[pd.DataFrame, pd.Series, np.ndarray]
) -> Union[pd.DataFrame, pd.Series, np.ndarray]:
    """Standardize data (z-score normalization)"""
    return normalize_data(data, method="zscore")


def handle_missing_values(
    df: pd.DataFrame,
    method: str = "forward_fill",
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Handle missing values in DataFrame

    Args:
        df: Input DataFrame
        method: Method to handle missing values
            - 'forward_fill': Forward fill
            - 'backward_fill': Backward fill
            - 'interpolate': Linear interpolation
            - 'mean': Fill with column mean
            - 'median': Fill with column median
            - 'drop': Drop rows with missing values
        limit: Maximum number of consecutive NaN values to fill

    Returns:
        DataFrame with missing values handled
    """
    df = df.copy()

    if method == "forward_fill":
        df = df.fillna(method="ffill", limit=limit)
    elif method == "backward_fill":
        df = df.fillna(method="bfill", limit=limit)
    elif method == "interpolate":
        df = df.interpolate(method="linear", limit=limit)
    elif method == "mean":
        df = df.fillna(df.mean())
    elif method == "median":
        df = df.fillna(df.median())
    elif method == "drop":
        df = df.dropna()
    else:
        raise ValueError(f"Unknown method: {method}")

    return df


def detect_outliers(
    data: Union[pd.Series, np.ndarray],
    method: str = "iqr",
    threshold: float = 1.5,
) -> np.ndarray:
    """
    Detect outliers in data

    Args:
        data: Input data
        method: Detection method
            - 'iqr': Interquartile range
            - 'zscore': Z-score method
            - 'modified_zscore': Modified z-score
        threshold: Threshold for outlier detection

    Returns:
        Boolean array indicating outliers
    """
    if isinstance(data, pd.Series):
        values = data.values
    else:
        values = data

    if method == "iqr":
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr
        outliers = (values < lower_bound) | (values > upper_bound)

    elif method == "zscore":
        z_scores = np.abs(stats.zscore(values, nan_policy="omit"))
        outliers = z_scores > threshold

    elif method == "modified_zscore":
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        modified_z_scores = 0.6745 * (values - median) / mad
        outliers = np.abs(modified_z_scores) > threshold

    else:
        raise ValueError(f"Unknown method: {method}")

    return outliers


def remove_outliers(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    method: str = "iqr",
    threshold: float = 1.5,
) -> pd.DataFrame:
    """
    Remove outliers from DataFrame

    Args:
        df: Input DataFrame
        columns: Columns to check for outliers (None = all numeric columns)
        method: Detection method
        threshold: Threshold for outlier detection

    Returns:
        DataFrame with outliers removed
    """
    df = df.copy()

    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    mask = pd.Series([False] * len(df), index=df.index)

    for col in columns:
        outliers = detect_outliers(df[col], method=method, threshold=threshold)
        mask = mask | outliers
        logger.debug(f"Detected {outliers.sum()} outliers in column {col}")

    logger.info(f"Removing {mask.sum()} outlier rows")
    return df[~mask]


def winsorize_data(
    data: Union[pd.Series, np.ndarray],
    limits: Tuple[float, float] = (0.05, 0.05),
) -> Union[pd.Series, np.ndarray]:
    """
    Winsorize data (cap extreme values)

    Args:
        data: Input data
        limits: Lower and upper percentile limits

    Returns:
        Winsorized data
    """
    if isinstance(data, pd.Series):
        values = data.values
        return pd.Series(
            stats.mstats.winsorize(values, limits=limits), index=data.index
        )
    else:
        return stats.mstats.winsorize(data, limits=limits)


def calculate_returns(
    prices: pd.Series, method: str = "simple", periods: int = 1
) -> pd.Series:
    """
    Calculate returns from prices

    Args:
        prices: Price series
        method: Return calculation method ('simple' or 'log')
        periods: Number of periods for return calculation

    Returns:
        Returns series
    """
    if method == "simple":
        returns = prices.pct_change(periods=periods)
    elif method == "log":
        returns = np.log(prices / prices.shift(periods))
    else:
        raise ValueError(f"Unknown method: {method}")

    return returns


def calculate_rolling_statistics(
    data: pd.Series, window: int
) -> pd.DataFrame:
    """
    Calculate rolling statistics

    Args:
        data: Input series
        window: Rolling window size

    Returns:
        DataFrame with rolling statistics
    """
    return pd.DataFrame(
        {
            "mean": data.rolling(window).mean(),
            "std": data.rolling(window).std(),
            "min": data.rolling(window).min(),
            "max": data.rolling(window).max(),
            "median": data.rolling(window).median(),
            "skew": data.rolling(window).skew(),
            "kurt": data.rolling(window).kurt(),
        }
    )


def resample_data(
    df: pd.DataFrame, freq: str, agg_dict: Optional[dict] = None
) -> pd.DataFrame:
    """
    Resample time series data

    Args:
        df: Input DataFrame with DatetimeIndex
        freq: Resampling frequency ('1min', '5min', '1H', '1D', etc.)
        agg_dict: Aggregation dictionary (column -> function)

    Returns:
        Resampled DataFrame
    """
    if agg_dict is None:
        # Default OHLCV aggregation
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }

    # Use only columns that exist in the DataFrame
    agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

    return df.resample(freq).agg(agg_dict)


def align_dataframes(
    dfs: List[pd.DataFrame], method: str = "inner"
) -> List[pd.DataFrame]:
    """
    Align multiple DataFrames by index

    Args:
        dfs: List of DataFrames
        method: Alignment method ('inner' or 'outer')

    Returns:
        List of aligned DataFrames
    """
    if len(dfs) == 0:
        return []

    if method == "inner":
        # Get intersection of all indices
        common_index = dfs[0].index
        for df in dfs[1:]:
            common_index = common_index.intersection(df.index)

        return [df.loc[common_index] for df in dfs]

    elif method == "outer":
        # Get union of all indices
        all_index = dfs[0].index
        for df in dfs[1:]:
            all_index = all_index.union(df.index)

        return [df.reindex(all_index) for df in dfs]

    else:
        raise ValueError(f"Unknown method: {method}")


def create_lagged_features(
    df: pd.DataFrame, columns: List[str], lags: List[int]
) -> pd.DataFrame:
    """
    Create lagged features

    Args:
        df: Input DataFrame
        columns: Columns to create lags for
        lags: List of lag periods

    Returns:
        DataFrame with lagged features
    """
    result = df.copy()

    for col in columns:
        for lag in lags:
            result[f"{col}_lag_{lag}"] = df[col].shift(lag)

    return result


def create_rolling_features(
    df: pd.DataFrame, columns: List[str], windows: List[int]
) -> pd.DataFrame:
    """
    Create rolling window features

    Args:
        df: Input DataFrame
        columns: Columns to create features for
        windows: List of window sizes

    Returns:
        DataFrame with rolling features
    """
    result = df.copy()

    for col in columns:
        for window in windows:
            result[f"{col}_rolling_mean_{window}"] = (
                df[col].rolling(window).mean()
            )
            result[f"{col}_rolling_std_{window}"] = (
                df[col].rolling(window).std()
            )
            result[f"{col}_rolling_min_{window}"] = (
                df[col].rolling(window).min()
            )
            result[f"{col}_rolling_max_{window}"] = (
                df[col].rolling(window).max()
            )

    return result
