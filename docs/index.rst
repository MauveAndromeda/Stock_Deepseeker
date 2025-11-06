Stock Deepseeker Documentation
================================

Stock Deepseeker is a quantitative trading research platform for academic and personal research purposes.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   api/index

Features
--------

* **High-Performance Factor Engine**: 62+ quantitative factors with vectorized computation
* **No-Lookahead Backtest Engine**: Event-driven architecture ensuring realistic results
* **Risk Management System**: Real-time monitoring with VaR, stress testing, and regime detection
* **Portfolio Management**: Multi-strategy framework with 6 optimization methods
* **Data Pipeline**: Multi-source aggregation with survivorship bias handling
* **Corporate Actions**: Automatic split and dividend adjustments

Quick Start
-----------

Installation::

    pip install stock-deepseeker[dev]

Basic Usage::

    from src.backtest.engine import BacktestEngine
    from src.factors import VectorizedFactorEngine

    # Initialize factor engine
    factor_engine = VectorizedFactorEngine()

    # Run backtest
    engine = BacktestEngine(initial_capital=1_000_000)
    results = engine.run()

Documentation Structure
-----------------------

* **Quick Start Guide**: Get started with Stock Deepseeker
* **API Reference**: Complete API documentation
* **User Guide**: In-depth tutorials and examples
* **Developer Guide**: Contributing guidelines

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
