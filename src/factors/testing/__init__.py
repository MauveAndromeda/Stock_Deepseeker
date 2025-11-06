"""
Factor testing and analysis framework.

Tools for evaluating factor performance, attribution, and validation.
"""

from src.factors.testing.backtester import FactorBacktester, FactorBacktestResult
from src.factors.testing.ic_analysis import ICAnalyzer, ICMetrics
from src.factors.testing.attribution import PerformanceAttributor, AttributionResult
from src.factors.testing.cross_section import CrossSectionalRegression, RegressionResult
from src.factors.testing.decay import FactorDecayAnalyzer, DecayAnalysis
from src.factors.testing.validation import OutOfSampleValidator, ValidationResult

__all__ = [
    'FactorBacktester',
    'FactorBacktestResult',
    'ICAnalyzer',
    'ICMetrics',
    'PerformanceAttributor',
    'AttributionResult',
    'CrossSectionalRegression',
    'RegressionResult',
    'FactorDecayAnalyzer',
    'DecayAnalysis',
    'OutOfSampleValidator',
    'ValidationResult',
]
