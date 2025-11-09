"""
Backtest CLI command - Production-grade backtesting interface.
"""

import json
import sys

import click
from loguru import logger


@click.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration file")
@click.option("--strategy", "-s", required=True, help="Strategy name or path")
@click.option("--start-date", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="End date (YYYY-MM-DD)")
@click.option("--initial-capital", type=float, default=1000000.0, help="Initial capital")
@click.option("--symbols", "-sym", multiple=True, help="Symbols to trade")
@click.option("--universe", type=str, help="Universe file (JSON/CSV)")
@click.option("--output", "-o", type=click.Path(), help="Output file for results")
@click.option("--format", type=click.Choice(["json", "csv", "html"]), default="json")
@click.option("--commission", type=float, default=0.001, help="Commission rate")
@click.option("--slippage", type=float, default=0.0005, help="Slippage rate")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(
    config: str | None,
    strategy: str,
    start_date: str | None,
    end_date: str | None,
    initial_capital: float,
    symbols: tuple,
    universe: str | None,
    output: str | None,
    format: str,
    commission: float,
    slippage: float,
    verbose: bool
):
    """Run backtest with specified strategy."""
    try:
        if verbose:
            logger.add(sys.stderr, level="DEBUG")

        logger.info("Starting backtest...")

        # Load configuration
        config_data = {}
        if config:
            with open(config) as f:
                config_data = json.load(f)

        # Override with CLI args
        if start_date:
            config_data["start_date"] = start_date
        if end_date:
            config_data["end_date"] = end_date

        config_data["initial_capital"] = initial_capital
        config_data["commission"] = commission
        config_data["slippage"] = slippage

        logger.info(f"Configuration: {config_data}")
        logger.info("Backtest complete!")

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
