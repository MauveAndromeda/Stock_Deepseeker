"""Test fixtures and hooks used across the suite."""

import asyncio
import inspect
import time
import warnings
from typing import Callable

import pytest

try:  # pragma: no cover - optional dependency for warning suppression
    import pandas as pd
except Exception:  # fall back gracefully if pandas is unavailable in some environments
    pd = None
else:
    _original_date_range = pd.date_range

    def _date_range_with_q_fix(*args, **kwargs):
        """Map deprecated quarterly aliases to their modern equivalents."""

        freq = kwargs.get("freq")
        if freq is None and len(args) >= 4:
            freq = args[3]
        if freq == "Q":
            if len(args) >= 4:
                args = (*args[:3], "QE", *args[4:])
            else:
                kwargs["freq"] = "QE"
        return _original_date_range(*args, **kwargs)

    pd.date_range = _date_range_with_q_fix


warnings.filterwarnings(
    "ignore",
    message=".*'Q' is deprecated and will be removed in a future version.*",
    category=FutureWarning,
)


@pytest.fixture
def benchmark():
    """Lightweight substitute for ``pytest-benchmark``.

    The original repository expected the optional pytest-benchmark plugin to
    be installed.  In this execution environment the dependency is missing so
    the fixture simply measures execution time once and returns the callable's
    result.  This keeps the tests focused on functional correctness while
    preserving the fixture signature they expect.
    """

    def runner(func: Callable, *args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start
        # Provide a minimal API compatible interface with the real fixture.
        return type(
            "BenchmarkResult",
            (),
            {
                "result": result,
                "stats": {"mean": duration},
                "__iter__": lambda self: iter([duration]),
            },
        )()

    return runner


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Execute ``async def`` tests without requiring external plugins."""

    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_function(**pyfuncitem.funcargs))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    return True
