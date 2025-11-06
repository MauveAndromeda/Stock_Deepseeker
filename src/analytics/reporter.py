"""
Performance reporting and visualization.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

from src.analytics.metrics import PerformanceMetrics, PerformanceStats
from src.analytics.attribution import AttributionAnalyzer, AttributionResult
from src.analytics.trades import TradeAnalyzer, TradeStats


class PerformanceReporter:
    """
    Generate comprehensive performance reports.

    Supports multiple output formats:
    - Text/console output
    - JSON for programmatic access
    - HTML for web display
    - CSV for spreadsheet analysis
    """

    def __init__(
        self,
        performance_stats: Optional[PerformanceStats] = None,
        trade_stats: Optional[TradeStats] = None,
        attribution: Optional[AttributionResult] = None
    ):
        """
        Initialize performance reporter.

        Args:
            performance_stats: Performance metrics
            trade_stats: Trade statistics
            attribution: Attribution analysis
        """
        self.performance_stats = performance_stats
        self.trade_stats = trade_stats
        self.attribution = attribution

    def generate_text_report(self) -> str:
        """
        Generate text report for console output.

        Returns:
            Formatted text report
        """
        lines = []

        lines.append("=" * 80)
        lines.append("PERFORMANCE REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Performance Metrics
        if self.performance_stats:
            lines.append("-" * 80)
            lines.append("PERFORMANCE METRICS")
            lines.append("-" * 80)

            ps = self.performance_stats

            lines.append(f"Total Return:        {ps.total_return:>12.2%}")
            lines.append(f"Annual Return:       {ps.annual_return:>12.2%}")
            lines.append(f"Monthly Return:      {ps.monthly_return:>12.2%}")
            lines.append("")

            lines.append(f"Volatility:          {ps.volatility:>12.2%}")
            lines.append(f"Downside Vol:        {ps.downside_volatility:>12.2%}")
            lines.append(f"VaR (95%):           {ps.var_95:>12.2%}")
            lines.append(f"CVaR (95%):          {ps.cvar_95:>12.2%}")
            lines.append("")

            lines.append(f"Sharpe Ratio:        {ps.sharpe_ratio:>12.2f}")
            lines.append(f"Sortino Ratio:       {ps.sortino_ratio:>12.2f}")
            lines.append(f"Calmar Ratio:        {ps.calmar_ratio:>12.2f}")
            lines.append(f"Omega Ratio:         {ps.omega_ratio:>12.2f}")
            lines.append("")

            lines.append(f"Max Drawdown:        {ps.max_drawdown:>12.2%}")
            lines.append(f"Avg Drawdown:        {ps.avg_drawdown:>12.2%}")
            lines.append(f"Max DD Duration:     {ps.max_drawdown_duration:>12} days")
            lines.append(f"Recovery Time:       {ps.recovery_time:>12} days")
            lines.append("")

            lines.append(f"Win Rate:            {ps.win_rate:>12.2%}")
            lines.append(f"Profit Factor:       {ps.profit_factor:>12.2f}")
            lines.append(f"Avg Win:             {ps.avg_win:>12.2%}")
            lines.append(f"Avg Loss:            {ps.avg_loss:>12.2%}")
            lines.append(f"Largest Win:         {ps.largest_win:>12.2%}")
            lines.append(f"Largest Loss:        {ps.largest_loss:>12.2%}")
            lines.append("")

        # Trade Statistics
        if self.trade_stats:
            lines.append("-" * 80)
            lines.append("TRADE STATISTICS")
            lines.append("-" * 80)

            ts = self.trade_stats

            lines.append(f"Total Trades:        {ts.total_trades:>12}")
            lines.append(f"Winning Trades:      {ts.winning_trades:>12}")
            lines.append(f"Losing Trades:       {ts.losing_trades:>12}")
            lines.append(f"Win Rate:            {ts.win_rate:>12.2%}")
            lines.append("")

            lines.append(f"Total P&L:           ${ts.total_pnl:>11,.2f}")
            lines.append(f"Avg P&L:             ${ts.avg_pnl:>11,.2f}")
            lines.append(f"Avg Win:             ${ts.avg_win:>11,.2f}")
            lines.append(f"Avg Loss:            ${ts.avg_loss:>11,.2f}")
            lines.append(f"Largest Win:         ${ts.largest_win:>11,.2f}")
            lines.append(f"Largest Loss:        ${ts.largest_loss:>11,.2f}")
            lines.append("")

            lines.append(f"Profit Factor:       {ts.profit_factor:>12.2f}")
            lines.append(f"Expectancy:          ${ts.expectancy:>11,.2f}")
            lines.append("")

            lines.append(f"Avg Holding:         {ts.avg_holding_period:>12.1f} days")
            lines.append(f"Avg Win Holding:     {ts.avg_win_holding:>12.1f} days")
            lines.append(f"Avg Loss Holding:    {ts.avg_loss_holding:>12.1f} days")
            lines.append("")

            lines.append(f"Max Consec Wins:     {ts.max_consecutive_wins:>12}")
            lines.append(f"Max Consec Losses:   {ts.max_consecutive_losses:>12}")
            lines.append("")

            lines.append(f"Total Commission:    ${ts.total_commission:>11,.2f}")
            lines.append(f"Total Slippage:      ${ts.total_slippage:>11,.2f}")
            lines.append("")

        # Attribution Analysis
        if self.attribution:
            lines.append("-" * 80)
            lines.append("ATTRIBUTION ANALYSIS")
            lines.append("-" * 80)

            attr = self.attribution

            lines.append(f"Total Return:        {attr.total_return:>12.2%}")
            lines.append("")

            lines.append("Factor Contributions:")
            for factor, contribution in attr.factor_contributions.items():
                lines.append(f"  {factor:<20} {contribution:>12.2%}")
            lines.append("")

            lines.append(f"Residual Return:     {attr.residual_return:>12.2%}")
            lines.append(f"Explained Variance:  {attr.explained_variance:>12.2%}")
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_json_report(self) -> str:
        """
        Generate JSON report.

        Returns:
            JSON string
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'performance': None,
            'trades': None,
            'attribution': None
        }

        if self.performance_stats:
            ps = self.performance_stats
            report['performance'] = {
                'returns': {
                    'total': ps.total_return,
                    'annual': ps.annual_return,
                    'monthly': ps.monthly_return,
                    'daily': ps.daily_return
                },
                'risk': {
                    'volatility': ps.volatility,
                    'downside_volatility': ps.downside_volatility,
                    'var_95': ps.var_95,
                    'cvar_95': ps.cvar_95
                },
                'risk_adjusted': {
                    'sharpe_ratio': ps.sharpe_ratio,
                    'sortino_ratio': ps.sortino_ratio,
                    'calmar_ratio': ps.calmar_ratio,
                    'omega_ratio': ps.omega_ratio
                },
                'drawdown': {
                    'max_drawdown': ps.max_drawdown,
                    'avg_drawdown': ps.avg_drawdown,
                    'max_duration': ps.max_drawdown_duration,
                    'recovery_time': ps.recovery_time
                },
                'win_loss': {
                    'win_rate': ps.win_rate,
                    'profit_factor': ps.profit_factor,
                    'avg_win': ps.avg_win,
                    'avg_loss': ps.avg_loss
                }
            }

        if self.trade_stats:
            ts = self.trade_stats
            report['trades'] = {
                'counts': {
                    'total': ts.total_trades,
                    'winning': ts.winning_trades,
                    'losing': ts.losing_trades,
                    'win_rate': ts.win_rate
                },
                'pnl': {
                    'total': ts.total_pnl,
                    'avg': ts.avg_pnl,
                    'avg_win': ts.avg_win,
                    'avg_loss': ts.avg_loss,
                    'largest_win': ts.largest_win,
                    'largest_loss': ts.largest_loss
                },
                'metrics': {
                    'profit_factor': ts.profit_factor,
                    'expectancy': ts.expectancy
                },
                'holding': {
                    'avg': ts.avg_holding_period,
                    'avg_win': ts.avg_win_holding,
                    'avg_loss': ts.avg_loss_holding
                },
                'streaks': {
                    'max_wins': ts.max_consecutive_wins,
                    'max_losses': ts.max_consecutive_losses
                },
                'costs': {
                    'commission': ts.total_commission,
                    'slippage': ts.total_slippage
                }
            }

        if self.attribution:
            attr = self.attribution
            report['attribution'] = {
                'total_return': attr.total_return,
                'factor_contributions': attr.factor_contributions,
                'residual_return': attr.residual_return,
                'explained_variance': attr.explained_variance
            }

        return json.dumps(report, indent=2)

    def generate_html_report(self) -> str:
        """
        Generate HTML report.

        Returns:
            HTML string
        """
        html = []

        html.append("<!DOCTYPE html>")
        html.append("<html>")
        html.append("<head>")
        html.append("<title>Performance Report</title>")
        html.append("<style>")
        html.append(self._get_css_styles())
        html.append("</style>")
        html.append("</head>")
        html.append("<body>")

        html.append("<div class='container'>")
        html.append("<h1>Performance Report</h1>")
        html.append(f"<p class='timestamp'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")

        # Performance Metrics
        if self.performance_stats:
            html.append("<h2>Performance Metrics</h2>")
            html.append(self._generate_performance_table())

        # Trade Statistics
        if self.trade_stats:
            html.append("<h2>Trade Statistics</h2>")
            html.append(self._generate_trade_table())

        # Attribution
        if self.attribution:
            html.append("<h2>Attribution Analysis</h2>")
            html.append(self._generate_attribution_table())

        html.append("</div>")
        html.append("</body>")
        html.append("</html>")

        return "\n".join(html)

    def save_report(
        self,
        filepath: str,
        format: str = "text"
    ) -> None:
        """
        Save report to file.

        Args:
            filepath: Output file path
            format: Report format ('text', 'json', 'html')
        """
        if format == "text":
            content = self.generate_text_report()
        elif format == "json":
            content = self.generate_json_report()
        elif format == "html":
            content = self.generate_html_report()
        else:
            raise ValueError(f"Unknown format: {format}")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            f.write(content)

    def _generate_performance_table(self) -> str:
        """Generate HTML table for performance metrics."""
        ps = self.performance_stats

        rows = [
            ("Total Return", f"{ps.total_return:.2%}"),
            ("Annual Return", f"{ps.annual_return:.2%}"),
            ("Volatility", f"{ps.volatility:.2%}"),
            ("Sharpe Ratio", f"{ps.sharpe_ratio:.2f}"),
            ("Sortino Ratio", f"{ps.sortino_ratio:.2f}"),
            ("Calmar Ratio", f"{ps.calmar_ratio:.2f}"),
            ("Max Drawdown", f"{ps.max_drawdown:.2%}"),
            ("Win Rate", f"{ps.win_rate:.2%}"),
            ("Profit Factor", f"{ps.profit_factor:.2f}")
        ]

        html = ["<table class='metrics-table'>"]
        for label, value in rows:
            html.append("<tr>")
            html.append(f"<td class='label'>{label}</td>")
            html.append(f"<td class='value'>{value}</td>")
            html.append("</tr>")
        html.append("</table>")

        return "\n".join(html)

    def _generate_trade_table(self) -> str:
        """Generate HTML table for trade statistics."""
        ts = self.trade_stats

        rows = [
            ("Total Trades", f"{ts.total_trades}"),
            ("Win Rate", f"{ts.win_rate:.2%}"),
            ("Total P&L", f"${ts.total_pnl:,.2f}"),
            ("Avg P&L", f"${ts.avg_pnl:,.2f}"),
            ("Profit Factor", f"{ts.profit_factor:.2f}"),
            ("Avg Holding Period", f"{ts.avg_holding_period:.1f} days"),
            ("Max Consecutive Wins", f"{ts.max_consecutive_wins}"),
            ("Max Consecutive Losses", f"{ts.max_consecutive_losses}")
        ]

        html = ["<table class='metrics-table'>"]
        for label, value in rows:
            html.append("<tr>")
            html.append(f"<td class='label'>{label}</td>")
            html.append(f"<td class='value'>{value}</td>")
            html.append("</tr>")
        html.append("</table>")

        return "\n".join(html)

    def _generate_attribution_table(self) -> str:
        """Generate HTML table for attribution analysis."""
        attr = self.attribution

        html = ["<table class='metrics-table'>"]

        html.append("<tr>")
        html.append("<td class='label'>Total Return</td>")
        html.append(f"<td class='value'>{attr.total_return:.2%}</td>")
        html.append("</tr>")

        html.append("<tr>")
        html.append("<td class='label' colspan='2'><strong>Factor Contributions</strong></td>")
        html.append("</tr>")

        for factor, contribution in attr.factor_contributions.items():
            html.append("<tr>")
            html.append(f"<td class='label' style='padding-left: 20px;'>{factor}</td>")
            html.append(f"<td class='value'>{contribution:.2%}</td>")
            html.append("</tr>")

        html.append("<tr>")
        html.append("<td class='label'>Residual Return</td>")
        html.append(f"<td class='value'>{attr.residual_return:.2%}</td>")
        html.append("</tr>")

        html.append("<tr>")
        html.append("<td class='label'>Explained Variance</td>")
        html.append(f"<td class='value'>{attr.explained_variance:.2%}</td>")
        html.append("</tr>")

        html.append("</table>")

        return "\n".join(html)

    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
        }
        .timestamp {
            color: #888;
            font-size: 14px;
        }
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .metrics-table td {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .metrics-table .label {
            font-weight: bold;
            color: #555;
            width: 60%;
        }
        .metrics-table .value {
            text-align: right;
            color: #333;
            font-family: 'Courier New', monospace;
        }
        .metrics-table tr:hover {
            background-color: #f9f9f9;
        }
        """
