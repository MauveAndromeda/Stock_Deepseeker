"""
Mathematical utility functions.
"""


import numpy as np
import pandas as pd


def sharpe_ratio(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: Return series
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
    
    Returns:
        Sharpe ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    excess_returns = returns - risk_free_rate / periods_per_year

    if len(excess_returns) == 0 or np.std(excess_returns) == 0:
        return 0.0

    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)


def sortino_ratio(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Sortino ratio (uses downside deviation).
    
    Args:
        returns: Return series
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
    
    Returns:
        Sortino ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or len(excess_returns) == 0:
        return 0.0

    downside_std = np.std(downside_returns)
    if downside_std == 0:
        return 0.0

    return np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year)


def max_drawdown(returns: pd.Series | np.ndarray) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        returns: Return series
    
    Returns:
        Maximum drawdown (negative value)
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    cumulative = (1 + returns).cumprod()
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max

    return np.min(drawdown)


def calmar_ratio(
    returns: pd.Series | np.ndarray,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Calmar ratio (return / max drawdown).
    
    Args:
        returns: Return series
        periods_per_year: Number of periods per year
    
    Returns:
        Calmar ratio
    """
    annual_return = annualize_returns(returns, periods_per_year)
    max_dd = max_drawdown(returns)

    if max_dd == 0:
        return 0.0

    return -annual_return / max_dd  # Negative because max_dd is negative


def annualize_returns(
    returns: pd.Series | np.ndarray,
    periods_per_year: int = 252
) -> float:
    """
    Annualize returns.
    
    Args:
        returns: Return series
        periods_per_year: Number of periods per year
    
    Returns:
        Annualized return
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    if len(returns) == 0:
        return 0.0

    total_return = (1 + returns).prod() - 1
    n_periods = len(returns)

    return (1 + total_return) ** (periods_per_year / n_periods) - 1


def annualize_volatility(
    returns: pd.Series | np.ndarray,
    periods_per_year: int = 252
) -> float:
    """
    Annualize volatility.
    
    Args:
        returns: Return series
        periods_per_year: Number of periods per year
    
    Returns:
        Annualized volatility
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    return np.std(returns) * np.sqrt(periods_per_year)


def rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> pd.Series:
    """
    Calculate rolling Sharpe ratio.
    
    Args:
        returns: Return series
        window: Rolling window size
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
    
    Returns:
        Rolling Sharpe ratio series
    """
    excess_returns = returns - risk_free_rate / periods_per_year

    rolling_mean = excess_returns.rolling(window).mean()
    rolling_std = excess_returns.rolling(window).std()

    return rolling_mean / rolling_std * np.sqrt(periods_per_year)


def information_ratio(
    returns: pd.Series | np.ndarray,
    benchmark_returns: pd.Series | np.ndarray
) -> float:
    """
    Calculate information ratio.
    
    Args:
        returns: Strategy returns
        benchmark_returns: Benchmark returns
    
    Returns:
        Information ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    if isinstance(benchmark_returns, pd.Series):
        benchmark_returns = benchmark_returns.values

    active_returns = returns - benchmark_returns

    if len(active_returns) == 0 or np.std(active_returns) == 0:
        return 0.0

    return np.mean(active_returns) / np.std(active_returns)
