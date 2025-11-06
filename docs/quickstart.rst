Quick Start Guide
=================

Installation
------------

Install Stock Deepseeker with pip::

    pip install stock-deepseeker

For development::

    git clone https://github.com/MauveAndromeda/Stock_Deepseeker.git
    cd Stock_Deepseeker
    pip install -e ".[dev]"

Basic Example
-------------

Here's a simple example of running a factor backtest::

    from src.backtest.engine import BacktestEngine
    from src.factors.momentum import PriceMomentum
    from src.factors import VectorizedFactorEngine

    # Initialize components
    factor_engine = VectorizedFactorEngine()
    momentum = PriceMomentum(lookback=252)

    # Run backtest
    engine = BacktestEngine(
        initial_capital=1_000_000,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31)
    )

    results = engine.run()
    print(f"Total Return: {results.total_return:.2%}")
    print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")

Next Steps
----------

* Read the :doc:`api/index` for detailed API documentation
* Explore example notebooks in the ``examples/`` directory
* Join our community discussions
