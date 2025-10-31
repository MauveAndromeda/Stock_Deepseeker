"""
Performance metrics for trading strategies
"""

import numpy as np
import pandas as pd
from typing import Union, Optional
from loguru import logger


def calculate_returns(
    equity_curve: Union[pd.Series, np.ndarray]
) -> Union[pd.Series, np.ndarray]:
    """Calculate returns from equity curve"""
    if isinstance(equity_curve, pd.Series):
        return equity_curve.pct_change().fillna(0)
    else:
        returns = np.diff(equity_curve) / equity_curve[:-1]
        return np.concatenate([[0], returns])


def calculate_sharpe_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe ratio

    Args:
        returns: Series or array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year (252 for daily)

    Returns:
        Sharpe ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    # Remove NaN values
    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    # Convert annual risk-free rate to period rate
    period_risk_free = risk_free_rate / periods_per_year

    # Calculate excess returns
    excess_returns = returns - period_risk_free

    # Calculate Sharpe ratio
    if np.std(excess_returns) == 0:
        return 0.0

    sharpe = np.mean(excess_returns) / np.std(excess_returns)

    # Annualize
    sharpe_annualized = sharpe * np.sqrt(periods_per_year)

    return sharpe_annualized


def calculate_sortino_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sortino ratio (similar to Sharpe but uses downside deviation)

    Args:
        returns: Series or array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Sortino ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    period_risk_free = risk_free_rate / periods_per_year
    excess_returns = returns - period_risk_free

    # Calculate downside deviation (only negative returns)
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0

    downside_std = np.std(downside_returns)
    sortino = np.mean(excess_returns) / downside_std
    sortino_annualized = sortino * np.sqrt(periods_per_year)

    return sortino_annualized


def calculate_max_drawdown(
    equity_curve: Union[pd.Series, np.ndarray]
) -> float:
    """
    Calculate maximum drawdown

    Args:
        equity_curve: Equity curve

    Returns:
        Maximum drawdown (positive value)
    """
    if isinstance(equity_curve, pd.Series):
        equity_curve = equity_curve.values

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity_curve)

    # Calculate drawdown at each point
    drawdown = (equity_curve - running_max) / running_max

    # Return maximum drawdown (as positive value)
    return abs(np.min(drawdown))


def calculate_calmar_ratio(
    returns: Union[pd.Series, np.ndarray],
    equity_curve: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Calmar ratio (annual return / max drawdown)

    Args:
        returns: Series or array of returns
        equity_curve: Equity curve
        periods_per_year: Number of periods per year

    Returns:
        Calmar ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    # Calculate annualized return
    total_return = np.prod(1 + returns) - 1
    num_years = len(returns) / periods_per_year
    annualized_return = (1 + total_return) ** (1 / num_years) - 1

    # Calculate max drawdown
    max_dd = calculate_max_drawdown(equity_curve)

    if max_dd == 0:
        return 0.0

    return annualized_return / max_dd


def calculate_win_rate(returns: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate win rate (percentage of profitable periods)

    Args:
        returns: Series or array of returns

    Returns:
        Win rate (0 to 1)
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    wins = np.sum(returns > 0)
    total = len(returns)

    return wins / total


def calculate_profit_factor(returns: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate profit factor (gross profit / gross loss)

    Args:
        returns: Series or array of returns

    Returns:
        Profit factor
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    gross_profit = np.sum(returns[returns > 0])
    gross_loss = abs(np.sum(returns[returns < 0]))

    if gross_loss == 0:
        return np.inf if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_expectancy(returns: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate expectancy (average win * win_rate - average loss * loss_rate)

    Args:
        returns: Series or array of returns

    Returns:
        Expectancy
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    wins = returns[returns > 0]
    losses = returns[returns < 0]

    if len(wins) == 0:
        avg_win = 0
        win_rate = 0
    else:
        avg_win = np.mean(wins)
        win_rate = len(wins) / len(returns)

    if len(losses) == 0:
        avg_loss = 0
        loss_rate = 0
    else:
        avg_loss = abs(np.mean(losses))
        loss_rate = len(losses) / len(returns)

    expectancy = (avg_win * win_rate) - (avg_loss * loss_rate)

    return expectancy


def calculate_var(
    returns: Union[pd.Series, np.ndarray], confidence_level: float = 0.95
) -> float:
    """
    Calculate Value at Risk (VaR)

    Args:
        returns: Series or array of returns
        confidence_level: Confidence level (e.g., 0.95 for 95%)

    Returns:
        VaR (positive value representing maximum expected loss)
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    var = abs(np.percentile(returns, (1 - confidence_level) * 100))

    return var


def calculate_cvar(
    returns: Union[pd.Series, np.ndarray], confidence_level: float = 0.95
) -> float:
    """
    Calculate Conditional Value at Risk (CVaR) / Expected Shortfall

    Args:
        returns: Series or array of returns
        confidence_level: Confidence level

    Returns:
        CVaR (average of returns below VaR)
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]

    if len(returns) == 0:
        return 0.0

    var = calculate_var(returns, confidence_level)
    cvar = abs(np.mean(returns[returns <= -var]))

    return cvar


def calculate_all_metrics(
    equity_curve: Union[pd.Series, np.ndarray],
    returns: Optional[Union[pd.Series, np.ndarray]] = None,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> dict:
    """
    Calculate all performance metrics

    Args:
        equity_curve: Equity curve
        returns: Returns (calculated from equity if not provided)
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Dictionary of all metrics
    """
    if returns is None:
        returns = calculate_returns(equity_curve)

    metrics = {
        "total_return": (equity_curve[-1] / equity_curve[0]) - 1
        if len(equity_curve) > 0
        else 0,
        "sharpe_ratio": calculate_sharpe_ratio(
            returns, risk_free_rate, periods_per_year
        ),
        "sortino_ratio": calculate_sortino_ratio(
            returns, risk_free_rate, periods_per_year
        ),
        "max_drawdown": calculate_max_drawdown(equity_curve),
        "calmar_ratio": calculate_calmar_ratio(
            returns, equity_curve, periods_per_year
        ),
        "win_rate": calculate_win_rate(returns),
        "profit_factor": calculate_profit_factor(returns),
        "expectancy": calculate_expectancy(returns),
        "var_95": calculate_var(returns, 0.95),
        "cvar_95": calculate_cvar(returns, 0.95),
    }

    # Calculate annualized metrics
    if isinstance(returns, pd.Series):
        returns_arr = returns.values
    else:
        returns_arr = returns

    returns_arr = returns_arr[~np.isnan(returns_arr)]

    if len(returns_arr) > 0:
        total_return = np.prod(1 + returns_arr) - 1
        num_years = len(returns_arr) / periods_per_year
        if num_years > 0:
            metrics["annualized_return"] = (1 + total_return) ** (
                1 / num_years
            ) - 1
            metrics["annualized_volatility"] = np.std(
                returns_arr
            ) * np.sqrt(periods_per_year)
        else:
            metrics["annualized_return"] = 0
            metrics["annualized_volatility"] = 0
    else:
        metrics["annualized_return"] = 0
        metrics["annualized_volatility"] = 0

    return metrics


def print_performance_summary(metrics: dict):
    """Print formatted performance summary"""
    logger.info("=" * 60)
    logger.info("PERFORMANCE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Return:         {metrics['total_return']:>10.2%}")
    logger.info(
        f"Annualized Return:    {metrics['annualized_return']:>10.2%}"
    )
    logger.info(
        f"Annualized Volatility:{metrics['annualized_volatility']:>10.2%}"
    )
    logger.info(f"Sharpe Ratio:         {metrics['sharpe_ratio']:>10.2f}")
    logger.info(f"Sortino Ratio:        {metrics['sortino_ratio']:>10.2f}")
    logger.info(f"Calmar Ratio:         {metrics['calmar_ratio']:>10.2f}")
    logger.info(f"Max Drawdown:         {metrics['max_drawdown']:>10.2%}")
    logger.info(f"Win Rate:             {metrics['win_rate']:>10.2%}")
    logger.info(f"Profit Factor:        {metrics['profit_factor']:>10.2f}")
    logger.info(f"Expectancy:           {metrics['expectancy']:>10.4f}")
    logger.info(f"VaR (95%):            {metrics['var_95']:>10.2%}")
    logger.info(f"CVaR (95%):           {metrics['cvar_95']:>10.2%}")
    logger.info("=" * 60)
