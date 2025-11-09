"""
Optimization CLI command - Strategy parameter optimization.
"""

import json

import click
from loguru import logger
import numpy as np


@click.command()
@click.option("--strategy", "-s", required=True, help="Strategy to optimize")
@click.option("--params", "-p", multiple=True, help="Parameters to optimize (name:min:max:step)")
@click.option("--metric", default="sharpe", type=click.Choice(["sharpe", "return", "sortino"]))
@click.option("--method", default="grid", type=click.Choice(["grid", "random", "bayesian"]))
@click.option("--iterations", "-n", type=int, default=100, help="Number of iterations")
@click.option("--output", "-o", type=click.Path(), help="Output results file")
@click.option("--parallel", is_flag=True, help="Run optimizations in parallel")
@click.option("--workers", type=int, default=4, help="Number of parallel workers")
def main(
    strategy: str,
    params: tuple,
    metric: str,
    method: str,
    iterations: int,
    output: str,
    parallel: bool,
    workers: int
):
    """Optimize strategy parameters."""
    try:
        logger.info(f"Optimizing strategy: {strategy}")
        logger.info(f"Method: {method}, Metric: {metric}")
        logger.info(f"Iterations: {iterations}")

        # Parse parameters
        param_ranges = parse_parameters(params)
        logger.info(f"Parameter ranges: {param_ranges}")

        # Run optimization
        if method == "grid":
            results = grid_search(strategy, param_ranges, metric, parallel, workers)
        elif method == "random":
            results = random_search(strategy, param_ranges, metric, iterations, parallel, workers)
        else:  # bayesian
            results = bayesian_optimization(strategy, param_ranges, metric, iterations)

        # Save results
        if output:
            save_results(results, output)
            logger.info(f"Results saved to {output}")

        # Print best parameters
        print_best_results(results, metric)

        logger.info("Optimization complete!")

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise click.ClickException(str(e))


def parse_parameters(params: tuple) -> dict[str, tuple[float, float, float]]:
    """Parse parameter specifications."""
    param_ranges = {}
    for param_spec in params:
        parts = param_spec.split(":")
        if len(parts) != 4:
            raise ValueError(f"Invalid parameter spec: {param_spec}")

        name = parts[0]
        min_val = float(parts[1])
        max_val = float(parts[2])
        step = float(parts[3])

        param_ranges[name] = (min_val, max_val, step)

    return param_ranges


def grid_search(strategy: str, param_ranges: dict, metric: str, parallel: bool, workers: int) -> list[dict]:
    """Perform grid search optimization."""
    logger.info("Running grid search...")
    results = []

    # Generate all parameter combinations
    import itertools

    param_names = list(param_ranges.keys())
    param_values = []

    for name in param_names:
        min_val, max_val, step = param_ranges[name]
        values = np.arange(min_val, max_val + step, step)
        param_values.append(values)

    # Test all combinations
    total_combos = np.prod([len(v) for v in param_values])
    logger.info(f"Testing {total_combos} parameter combinations...")

    for combo in itertools.product(*param_values):
        params = dict(zip(param_names, combo))

        # Run backtest with these parameters
        score = evaluate_parameters(strategy, params, metric)

        results.append({
            "parameters": params,
            "score": score
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def random_search(strategy: str, param_ranges: dict, metric: str, iterations: int, parallel: bool, workers: int) -> list[dict]:
    """Perform random search optimization."""
    logger.info(f"Running random search with {iterations} iterations...")
    results = []

    for i in range(iterations):
        # Sample random parameters
        params = {}
        for name, (min_val, max_val, step) in param_ranges.items():
            params[name] = np.random.uniform(min_val, max_val)

        # Evaluate
        score = evaluate_parameters(strategy, params, metric)

        results.append({
            "parameters": params,
            "score": score
        })

        if (i + 1) % 10 == 0:
            logger.info(f"Completed {i + 1}/{iterations} iterations")

    return sorted(results, key=lambda x: x["score"], reverse=True)


def bayesian_optimization(strategy: str, param_ranges: dict, metric: str, iterations: int) -> list[dict]:
    """Perform Bayesian optimization."""
    logger.info("Running Bayesian optimization...")

    # Simplified implementation - would use scikit-optimize in production
    results = []

    for i in range(iterations):
        # Sample parameters (would use Gaussian Process in production)
        params = {}
        for name, (min_val, max_val, step) in param_ranges.items():
            params[name] = np.random.uniform(min_val, max_val)

        score = evaluate_parameters(strategy, params, metric)

        results.append({
            "parameters": params,
            "score": score
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def evaluate_parameters(strategy: str, params: dict, metric: str) -> float:
    """Evaluate strategy with given parameters."""
    # Simulate evaluation - would run actual backtest in production
    return np.random.normal(1.5, 0.5)  # Mock Sharpe ratio


def save_results(results: list[dict], output_path: str):
    """Save optimization results."""
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)


def print_best_results(results: list[dict], metric: str):
    """Print best optimization results."""
    click.echo("\n" + "="*60)
    click.echo("TOP 5 PARAMETER SETS")
    click.echo("="*60)

    for i, result in enumerate(results[:5], 1):
        click.echo(f"\n#{i} - {metric.upper()}: {result['score']:.4f}")
        click.echo("Parameters:")
        for name, value in result["parameters"].items():
            click.echo(f"  {name}: {value:.4f}")

    click.echo("="*60 + "\n")


if __name__ == "__main__":
    main()
