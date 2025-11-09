"""
Comprehensive risk reporting system.

Generates detailed risk reports integrating all risk components.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
import pandas as pd


@dataclass
class RiskReport:
    """Comprehensive risk report."""
    timestamp: datetime
    summary: dict
    portfolio_metrics: dict
    exposure_analysis: dict
    var_analysis: dict
    stress_test_results: list[dict]
    concentration_analysis: dict
    correlation_analysis: dict
    regime_analysis: dict
    risk_budget_status: dict
    limit_violations: list[dict]
    recommendations: list[str]


class RiskReporter:
    """
    Comprehensive risk reporting system.
    
    Aggregates risk metrics from all components and generates
    unified risk reports.
    """

    def __init__(self):
        """Initialize risk reporter."""
        self.report_history: list[RiskReport] = []
        logger.info("Initialized RiskReporter")

    def generate_report(
        self,
        portfolio_metrics: dict,
        risk_monitor: any | None = None,
        var_calculator: any | None = None,
        stress_tester: any | None = None,
        concentration_manager: any | None = None,
        correlation_manager: any | None = None,
        regime_detector: any | None = None,
        risk_budget_manager: any | None = None,
        limit_system: any | None = None
    ) -> RiskReport:
        """
        Generate comprehensive risk report.
        
        Args:
            portfolio_metrics: Current portfolio metrics
            risk_monitor: RiskMonitor instance
            var_calculator: VaRCalculator instance
            stress_tester: StressTester instance
            concentration_manager: ConcentrationManager instance
            correlation_manager: CorrelationManager instance
            regime_detector: RegimeDetector instance
            risk_budget_manager: RiskBudgetManager instance
            limit_system: RiskLimitSystem instance
            
        Returns:
            RiskReport
        """
        timestamp = datetime.now()

        # Summary
        summary = self._generate_summary(portfolio_metrics, risk_monitor)

        # Exposure analysis
        exposure_analysis = self._analyze_exposure(portfolio_metrics)

        # VaR analysis
        var_analysis = self._analyze_var(var_calculator) if var_calculator else {}

        # Stress tests
        stress_results = self._collect_stress_tests(stress_tester) if stress_tester else []

        # Concentration
        concentration_analysis = self._analyze_concentration(
            concentration_manager
        ) if concentration_manager else {}

        # Correlation
        correlation_analysis = self._analyze_correlation(
            correlation_manager
        ) if correlation_manager else {}

        # Regime
        regime_analysis = self._analyze_regime(regime_detector) if regime_detector else {}

        # Risk budget
        budget_status = self._analyze_budget(risk_budget_manager) if risk_budget_manager else {}

        # Limit violations
        violations = self._collect_violations(limit_system) if limit_system else []

        # Generate recommendations
        recommendations = self._generate_recommendations(
            summary, violations, stress_results, regime_analysis
        )

        report = RiskReport(
            timestamp=timestamp,
            summary=summary,
            portfolio_metrics=portfolio_metrics,
            exposure_analysis=exposure_analysis,
            var_analysis=var_analysis,
            stress_test_results=stress_results,
            concentration_analysis=concentration_analysis,
            correlation_analysis=correlation_analysis,
            regime_analysis=regime_analysis,
            risk_budget_status=budget_status,
            limit_violations=violations,
            recommendations=recommendations
        )

        self.report_history.append(report)

        logger.info(f"Risk report generated: {len(violations)} violations, {len(recommendations)} recommendations")

        return report

    def _generate_summary(
        self,
        portfolio_metrics: dict,
        risk_monitor: any | None
    ) -> dict:
        """Generate executive summary."""
        summary = {
            "timestamp": datetime.now(),
            "portfolio_value": portfolio_metrics.get("value", 0),
            "daily_pnl": portfolio_metrics.get("daily_pnl", 0),
            "daily_return": portfolio_metrics.get("daily_return", 0),
        }

        if risk_monitor and risk_monitor.current_metrics:
            metrics = risk_monitor.current_metrics
            summary.update({
                "risk_level": metrics.get_risk_level().value,
                "volatility": metrics.volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "var_99": metrics.var_99,
                "leverage": metrics.leverage,
            })

        return summary

    def _analyze_exposure(
        self,
        portfolio_metrics: dict
    ) -> dict:
        """Analyze portfolio exposures."""
        return {
            "long_exposure": portfolio_metrics.get("long_exposure", 0),
            "short_exposure": portfolio_metrics.get("short_exposure", 0),
            "net_exposure": portfolio_metrics.get("net_exposure", 0),
            "gross_exposure": portfolio_metrics.get("gross_exposure", 0),
            "num_positions": portfolio_metrics.get("num_positions", 0),
        }

    def _analyze_var(
        self,
        var_calculator: any
    ) -> dict:
        """Analyze VaR metrics."""
        # Placeholder - would call var_calculator methods
        return {
            "var_95": 0,
            "var_99": 0,
            "expected_shortfall": 0,
            "method": "historical"
        }

    def _collect_stress_tests(
        self,
        stress_tester: any
    ) -> list[dict]:
        """Collect stress test results."""
        # Placeholder - would call stress_tester methods
        return []

    def _analyze_concentration(
        self,
        concentration_manager: any
    ) -> dict:
        """Analyze concentration risks."""
        # Placeholder
        return {
            "max_single_position": 0,
            "top_5_concentration": 0,
            "herfindahl_index": 0,
        }

    def _analyze_correlation(
        self,
        correlation_manager: any
    ) -> dict:
        """Analyze correlation metrics."""
        if correlation_manager and len(correlation_manager.metrics_history) > 0:
            metrics = correlation_manager.metrics_history[-1]
            return {
                "average_correlation": metrics.average_correlation,
                "max_correlation": metrics.max_correlation,
                "eigenvalue_ratio": metrics.eigenvalue_ratio,
                "effective_dimension": metrics.effective_dimension,
            }
        return {}

    def _analyze_regime(
        self,
        regime_detector: any
    ) -> dict:
        """Analyze market regime."""
        if regime_detector and regime_detector.current_regime:
            state = regime_detector.current_regime
            return {
                "current_regime": state.regime.value,
                "confidence": state.confidence,
                "duration_days": state.duration_days,
                "risk_adjustment": regime_detector.get_risk_adjustment(),
            }
        return {}

    def _analyze_budget(
        self,
        risk_budget_manager: any
    ) -> dict:
        """Analyze risk budget status."""
        if risk_budget_manager:
            return risk_budget_manager.get_utilization_report()
        return {}

    def _collect_violations(
        self,
        limit_system: any
    ) -> list[dict]:
        """Collect limit violations."""
        if limit_system and len(limit_system.violation_history) > 0:
            # Get recent violations (last 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            recent = [
                v for v in limit_system.violation_history
                if v.timestamp > cutoff
            ]

            return [
                {
                    "limit_name": v.limit.name,
                    "severity": v.severity.value,
                    "value": v.current_value,
                    "threshold": v.limit.hard_limit,
                    "timestamp": v.timestamp,
                }
                for v in recent
            ]
        return []

    def _generate_recommendations(
        self,
        summary: dict,
        violations: list[dict],
        stress_results: list[dict],
        regime_analysis: dict
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Check risk level
        risk_level = summary.get("risk_level", "low")
        if risk_level in ["high", "critical"]:
            recommendations.append(
                f"URGENT: Risk level is {risk_level.upper()}. Consider reducing exposure."
            )

        # Check violations
        critical_violations = [v for v in violations if v["severity"] == "critical"]
        if critical_violations:
            recommendations.append(
                f"CRITICAL: {len(critical_violations)} critical limit violations detected. "
                "Immediate action required."
            )

        # Check drawdown
        max_dd = summary.get("max_drawdown", 0)
        if max_dd < -0.15:
            recommendations.append(
                f"High drawdown ({max_dd:.1%}). Consider implementing stop-losses."
            )

        # Check volatility
        vol = summary.get("volatility", 0)
        if vol > 0.35:
            recommendations.append(
                f"Elevated volatility ({vol:.1%}). Reduce position sizes or increase hedging."
            )

        # Check leverage
        leverage = summary.get("leverage", 0)
        if abs(leverage) > 1.5:
            recommendations.append(
                f"High leverage ({leverage:.2f}x). Consider deleveraging to reduce risk."
            )

        # Regime-based recommendations
        regime = regime_analysis.get("current_regime")
        if regime == "crisis":
            recommendations.append(
                "Market in CRISIS regime. Maintain defensive positioning and reduce risk."
            )
        elif regime == "bear":
            recommendations.append(
                "Market in BEAR regime. Consider increasing hedges or reducing net exposure."
            )

        # Default recommendation if all clear
        if len(recommendations) == 0:
            recommendations.append(
                "Risk metrics within acceptable ranges. Continue monitoring."
            )

        return recommendations

    def export_report(
        self,
        report: RiskReport,
        format: str = "text"
    ) -> str:
        """
        Export report in specified format.
        
        Args:
            report: Risk report to export
            format: Output format ('text', 'json', 'html')
            
        Returns:
            Formatted report string
        """
        if format == "text":
            return self._format_text_report(report)
        if format == "json":
            import json
            # Would need to make report JSON-serializable
            return json.dumps({"summary": report.summary}, indent=2)
        if format == "html":
            return self._format_html_report(report)
        raise ValueError(f"Unknown format: {format}")

    def _format_text_report(
        self,
        report: RiskReport
    ) -> str:
        """Format report as text."""
        lines = []
        lines.append("=" * 80)
        lines.append("RISK REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.timestamp}")
        lines.append("")

        # Summary
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 80)
        for key, value in report.summary.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("")

        # Violations
        if report.limit_violations:
            lines.append("LIMIT VIOLATIONS")
            lines.append("-" * 80)
            for v in report.limit_violations:
                lines.append(
                    f"  [{v['severity'].upper()}] {v['limit_name']}: "
                    f"{v['value']:.4f} (threshold: {v['threshold']:.4f})"
                )
            lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 80)
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def _format_html_report(
        self,
        report: RiskReport
    ) -> str:
        """Format report as HTML."""
        html = f"""
        <html>
        <head><title>Risk Report - {report.timestamp}</title></head>
        <body>
        <h1>Risk Report</h1>
        <p><strong>Generated:</strong> {report.timestamp}</p>
        
        <h2>Executive Summary</h2>
        <table border="1">
        """

        for key, value in report.summary.items():
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"

        html += """
        </table>
        
        <h2>Recommendations</h2>
        <ul>
        """

        for rec in report.recommendations:
            html += f"<li>{rec}</li>"

        html += """
        </ul>
        </body>
        </html>
        """

        return html

    def get_report_history(
        self,
        days: int = 30
    ) -> pd.DataFrame:
        """Get historical report summary."""
        if len(self.report_history) == 0:
            return pd.DataFrame()

        cutoff = datetime.now() - timedelta(days=days)
        recent_reports = [r for r in self.report_history if r.timestamp > cutoff]

        data = []
        for report in recent_reports:
            data.append({
                "timestamp": report.timestamp,
                "risk_level": report.summary.get("risk_level", "unknown"),
                "volatility": report.summary.get("volatility", 0),
                "max_drawdown": report.summary.get("max_drawdown", 0),
                "num_violations": len(report.limit_violations),
                "num_recommendations": len(report.recommendations),
            })

        return pd.DataFrame(data)
