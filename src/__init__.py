"""
Stock DeepSeeker - Enterprise-Grade Automated Trading System
Main package initialization
"""

__version__ = "1.0.0"
__author__ = "MauveAndromeda"
__license__ = "MIT"

from src.utils.config import Config
from src.utils.helpers import setup_logging

# Initialize logging
logger = setup_logging()

__all__ = [
    "__version__",
    "Config",
    "logger",
]
