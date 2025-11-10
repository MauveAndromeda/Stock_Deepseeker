"""
Performance reporting and metrics calculation

Generate JSON reports and calculate standard trading metrics.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd


def calculate_metrics(results: Dict) -> Dict:
    """
    Calculate performance metrics from backtest results

    Args:
        results: Dict from strategy.run_backtest()

    Returns:
        Dict with metrics:
        - total_return: Total return (%)
        - annual_return: Annualized return (%)
        - sharpe_ratio: Sharpe ratio (annualized)
        - sortino_ratio: Sortino ratio (annualized)
        - max_drawdown: Maximum drawdown (%)
        - volatility: Annualized volatility (%)
        - win_rate: Percentage of winning trades
        - num_trades: Total number of trades
        - avg_trade: Average trade return (%)
        - final_value: Final portfolio value
        - start_date: First date
        - end_date: Last date
        - trading_days: Number of trading days
    """
    portfolio_value = results['portfolio_value']
    returns = results['returns']
    trades = results['trades']
    config = results['config']

    initial_capital = config['initial_capital']
    final_value = portfolio_value.iloc[-1]

    # Basic metrics
    total_return = (final_value / initial_capital - 1.0) * 100

    # Time period
    start_date = portfolio_value.index[0]
    end_date = portfolio_value.index[-1]
    trading_days = len(portfolio_value)
    years = trading_days / 252.0  # Assume 252 trading days per year

    # Annualized return
    annual_return = ((final_value / initial_capital) ** (1.0 / years) - 1.0) * 100 if years > 0 else 0.0

    # Volatility (annualized)
    volatility = returns.std() * np.sqrt(252) * 100

    # Sharpe ratio (assume 0% risk-free rate for simplicity)
    sharpe_ratio = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0

    # Sortino ratio (downside deviation)
    downside_returns = returns[returns < 0]
    downside_dev = downside_returns.std() * np.sqrt(252)
    sortino_ratio = (returns.mean() * 252) / downside_dev if downside_dev > 0 else 0.0

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100

    # Trade statistics
    num_trades = len(trades)

    # Calculate trade-level returns
    trade_returns = []
    buy_prices = {}

    for trade in trades:
        symbol = trade['symbol']
        action = trade['action']
        price = trade['price']

        if action == 'BUY':
            buy_prices[symbol] = price
        elif action == 'SELL' and symbol in buy_prices:
            trade_return = (price - buy_prices[symbol]) / buy_prices[symbol]
            trade_returns.append(trade_return)
            del buy_prices[symbol]

    if trade_returns:
        avg_trade = np.mean(trade_returns) * 100
        win_rate = (np.array(trade_returns) > 0).sum() / len(trade_returns) * 100
    else:
        avg_trade = 0.0
        win_rate = 0.0

    return {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'sortino_ratio': round(sortino_ratio, 2),
        'max_drawdown': round(max_drawdown, 2),
        'volatility': round(volatility, 2),
        'win_rate': round(win_rate, 2),
        'num_trades': num_trades,
        'avg_trade': round(avg_trade, 2),
        'final_value': round(final_value, 2),
        'initial_capital': round(initial_capital, 2),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'trading_days': trading_days
    }


def generate_report(
    results: Dict,
    metrics: Optional[Dict] = None,
    output_dir: Optional[Path] = None,
    report_name: Optional[str] = None
) -> Path:
    """
    Generate JSON report from backtest results

    Args:
        results: Dict from strategy.run_backtest()
        metrics: Optional pre-calculated metrics (will calculate if not provided)
        output_dir: Output directory (default: backtest_reports/)
        report_name: Report filename (default: report_YYYYMMDD_HHMMSS.json)

    Returns:
        Path to generated report file
    """
    if output_dir is None:
        output_dir = Path("backtest_reports")
    output_dir.mkdir(exist_ok=True)

    if metrics is None:
        metrics = calculate_metrics(results)

    if report_name is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"report_{timestamp}.json"

    # Build report structure
    report = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'strategy': results['config'].get('strategy', 'unknown'),
            'symbols': results['symbols'],
            'initial_capital': results['config']['initial_capital']
        },
        'config': results['config'],
        'metrics': metrics,
        'trades_summary': {
            'total_trades': len(results['trades']),
            'first_10_trades': results['trades'][:10] if results['trades'] else []
        }
    }

    # Convert any numpy types to Python types for JSON serialization
    report = _convert_numpy_types(report)

    # Write report
    report_path = output_dir / report_name
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return report_path


def print_summary(metrics: Dict, symbols: list) -> None:
    """
    Print formatted metrics summary to console

    Args:
        metrics: Dict from calculate_metrics()
        symbols: List of symbols traded
    """
    print("=" * 70)
    print("BACKTEST RESULTS SUMMARY".center(70))
    print("=" * 70)
    print()

    print(f"Symbols:          {', '.join(symbols)}")
    print(f"Period:           {metrics['start_date']} to {metrics['end_date']}")
    print(f"Trading days:     {metrics['trading_days']}")
    print()

    print("PERFORMANCE METRICS")
    print("-" * 70)
    print(f"Initial capital:  ${metrics['initial_capital']:,.2f}")
    print(f"Final value:      ${metrics['final_value']:,.2f}")
    print(f"Total return:     {metrics['total_return']:+.2f}%")
    print(f"Annual return:    {metrics['annual_return']:+.2f}%")
    print()

    print("RISK METRICS")
    print("-" * 70)
    print(f"Max drawdown:     {metrics['max_drawdown']:.2f}%")
    print(f"Volatility:       {metrics['volatility']:.2f}%")
    print(f"Sharpe ratio:     {metrics['sharpe_ratio']:.2f}")
    print(f"Sortino ratio:    {metrics['sortino_ratio']:.2f}")
    print()

    print("TRADE STATISTICS")
    print("-" * 70)
    print(f"Total trades:     {metrics['num_trades']}")
    print(f"Win rate:         {metrics['win_rate']:.1f}%")
    print(f"Avg trade return: {metrics['avg_trade']:+.2f}%")
    print()
    print("=" * 70)


def _convert_numpy_types(obj):
    """Recursively convert numpy types to Python types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    else:
        return obj
