#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock_Deepseeker - Portable One-Click Backtest
═══════════════════════════════════════════════════════════════

🎯 Design: ZIP → Extract → Run (Windows-friendly)

Features:
✅ Minimal dependencies by default (no AI required)
✅ Automatic venv setup
✅ Yahoo → Stooq data fallback
✅ Simple SMA strategy (or advanced AI with --ai flag)
✅ JSON reports under backtest_reports/
✅ Works with long paths and parentheses

Usage:
  python 一键回测_portable.py --mode fast --years 3
  python 一键回测_portable.py --mode turbo --years 1 --symbols AAPL MSFT
  python 一键回测_portable.py --mode fast --ai  # Enable AI features

═══════════════════════════════════════════════════════════════
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# Path and Encoding Setup
# ═══════════════════════════════════════════════════════════════

# Ensure UTF-8 encoding for Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Check for problematic path
PROJECT_ROOT = Path(__file__).parent.resolve()
path_str = str(PROJECT_ROOT)

if len(path_str) > 200:
    print("⚠ WARNING: Path is very long ({} chars)".format(len(path_str)))
    print("  This may cause issues on Windows. Consider moving to shorter path.")
    print()

if "(" in path_str or ")" in path_str:
    print("⚠ WARNING: Path contains parentheses")
    print("  Some tools may have issues. Consider renaming folder.")
    print()

# ═══════════════════════════════════════════════════════════════
# Virtual Environment Management
# ═══════════════════════════════════════════════════════════════

def get_venv_path() -> Path:
    """Get virtual environment path"""
    return PROJECT_ROOT / ".venv"

def get_venv_python() -> Path:
    """Get Python executable in venv"""
    venv_path = get_venv_path()
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"

def create_venv() -> bool:
    """Create virtual environment if needed"""
    venv_python = get_venv_python()

    if venv_python.exists():
        print("✓ Virtual environment exists")
        return True

    print("Creating virtual environment...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(get_venv_path())],
            stdout=subprocess.DEVNULL
        )

        # Upgrade pip
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"],
            stdout=subprocess.DEVNULL
        )

        print("✓ Virtual environment created")
        return True

    except Exception as e:
        print(f"✗ Failed to create venv: {e}")
        return False

def install_dependencies(enable_ai: bool = False, force: bool = False) -> bool:
    """Install runtime dependencies inside the managed virtual environment."""

    venv_python = get_venv_python()

    base_marker = get_venv_path() / ".deps_installed"
    data_marker = get_venv_path() / ".deps_data_installed"
    ai_marker = get_venv_path() / ".deps_ai_installed"

    # Short-circuit if everything is already installed and no force flag is set
    if not force:
        base_ok = base_marker.exists()
        data_ok = data_marker.exists() or not (PROJECT_ROOT / "requirements-data.txt").exists()
        ai_ok = (not enable_ai) or ai_marker.exists()
        if base_ok and data_ok and ai_ok:
            print("✓ Dependencies already installed (use --force-install to reinstall)")
            return True

    def _install_requirements(req_file: str, marker: Path, optional: bool = False, timeout: int | None = None) -> bool:
        if not (PROJECT_ROOT / req_file).exists():
            return True

        args = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            req_file,
            "-q",
        ]

        try:
            subprocess.check_call(
                args,
                cwd=PROJECT_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
            )
            marker.write_text(f"Installed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"✓ Installed requirements from {req_file}")
            return True
        except subprocess.TimeoutExpired:
            if optional:
                print(f"⚠ Installing {req_file} timed out – continuing without these optional packages")
                return False
            print(f"✗ Installing {req_file} timed out")
            return False
        except subprocess.CalledProcessError as exc:
            if optional:
                print(f"⚠ Optional requirements ({req_file}) failed with exit code {exc.returncode}")
                print("  Synthetic data fallback will be used if live downloads are unavailable.")
                return False
            print(f"✗ Failed to install requirements from {req_file}: exit code {exc.returncode}")
            print(f"  Try manually: {venv_python} -m pip install -r {req_file}")
            return False
        except Exception as err:  # pragma: no cover - defensive
            if optional:
                print(f"⚠ Optional requirements ({req_file}) could not be installed: {err}")
                return False
            print(f"✗ Failed to install requirements from {req_file}: {err}")
            print(f"  Try manually: {venv_python} -m pip install -r {req_file}")
            return False

    print("\nInstalling minimal dependencies...")
    if not _install_requirements("requirements-min.txt", base_marker):
        return False

    print("\nInstalling optional market data helpers...")
    _install_requirements("requirements-data.txt", data_marker, optional=True)

    if enable_ai:
        print("\nInstalling AI dependencies...")
        success = _install_requirements("requirements-ai.txt", ai_marker, optional=True, timeout=600)
        if not success:
            print("  Continuing without AI enhancements – core backtest is unaffected.")

    return True

# ═══════════════════════════════════════════════════════════════
# Backtest Runner
# ═══════════════════════════════════════════════════════════════

def run_backtest(mode: str, years: int, symbols: Optional[list], enable_ai: bool) -> bool:
    """
    Run the backtest

    Args:
        mode: Backtest mode (turbo/fast/balanced/full)
        years: Number of years
        symbols: List of symbols (None = default)
        enable_ai: Use AI strategy

    Returns:
        True if successful
    """
    venv_python = get_venv_python()

    print("\n" + "=" * 70)
    print(f"RUNNING BACKTEST - {mode.upper()} MODE".center(70))
    print("=" * 70)
    print()

    # Set environment variable for AI enable
    env = os.environ.copy()
    if enable_ai:
        env["ENABLE_AI"] = "1"
        print("✓ AI mode enabled")
    else:
        env["ENABLE_AI"] = "0"
        print("ℹ Using minimal SMA strategy (use --ai for advanced features)")

    print(f"Mode: {mode}")
    print(f"Years: {years}")
    if symbols:
        print(f"Symbols: {', '.join(symbols)}")
    print()

    # Import and run backtest (inside venv)
    try:
        # Run the backtest via subprocess to ensure correct Python environment
        import_code = """
import sys
sys.path.insert(0, '{root}')

from portable_runner import download_market_data, SimpleMovingAverageStrategy, generate_report, calculate_metrics, print_summary

# Download data
symbols = {symbols}
data = download_market_data(symbols, years={years}, verbose=True)

# Run strategy
strategy = SimpleMovingAverageStrategy(initial_capital=100000.0)
results = strategy.run_backtest(data, verbose=True)

# Calculate metrics
metrics = calculate_metrics(results)

# Generate report
report_path = generate_report(results, metrics)
print(f"\\n✓ Report saved: {{report_path}}")

# Print summary
print()
print_summary(metrics, symbols)
""".format(
            root=PROJECT_ROOT,
            symbols=symbols or ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'UNH', 'JNJ'],
            years=years
        )

        result = subprocess.run(
            [str(venv_python), "-c", import_code],
            cwd=PROJECT_ROOT,
            env=env
        )

        if result.returncode == 0:
            print("\n✓ Backtest completed successfully")
            return True
        else:
            print(f"\n✗ Backtest failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n✗ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ═══════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description="Stock_Deepseeker Portable Backtest - ZIP → Extract → Run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 一键回测_portable.py
  python 一键回测_portable.py --mode turbo --years 1
  python 一键回测_portable.py --symbols AAPL MSFT GOOGL
  python 一键回测_portable.py --mode fast --ai  # Enable AI features

Modes:
  turbo    - Fast test (1 year recommended)
  fast     - Recommended (2-3 years)
  balanced - Thorough (3-5 years)
  full     - Complete (5+ years)

Notes:
  - First run will create .venv and install dependencies (2-3 mins)
  - Data is cached in data_cache/ for faster subsequent runs
  - Reports are saved in backtest_reports/
  - Use --ai flag to enable advanced AI features (requires additional setup)
        """
    )

    parser.add_argument(
        "--mode",
        choices=["turbo", "fast", "balanced", "full"],
        default="fast",
        help="Backtest mode (default: fast)"
    )

    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Years of historical data (default: 3)"
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Stock symbols to backtest (default: 10 US stocks)"
    )

    parser.add_argument(
        "--ai",
        action="store_true",
        help="Enable AI features (requires additional dependencies)"
    )

    parser.add_argument(
        "--force-install",
        action="store_true",
        help="Force reinstall dependencies"
    )

    args = parser.parse_args()

    # Print header
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                                                                   ║")
    print("║         Stock_Deepseeker - Portable Backtest Runner               ║")
    print("║         ZIP → Extract → Run | Windows-Friendly                    ║")
    print("║                                                                   ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()

    start_time = time.time()

    try:
        # Step 1: Create venv
        print("[Step 1/4] Virtual Environment")
        print("-" * 70)
        if not create_venv():
            return 1
        print()

        # Step 2: Install dependencies
        print("[Step 2/4] Dependencies")
        print("-" * 70)
        if not install_dependencies(enable_ai=args.ai, force=args.force_install):
            return 1
        print()

        # Step 3: Run backtest
        print("[Step 3/4] Backtest")
        print("-" * 70)
        if not run_backtest(args.mode, args.years, args.symbols, args.ai):
            return 1
        print()

        # Step 4: Summary
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print("[Step 4/4] Summary")
        print("-" * 70)
        print(f"✓ Total time: {minutes}m {seconds}s")
        print(f"✓ Reports: backtest_reports/")
        print(f"✓ Cache: data_cache/")
        print()
        print("Next steps:")
        print("  - View reports: cat backtest_reports/report_*.json")
        print("  - Try different mode: --mode turbo")
        print("  - Try AI features: --ai (requires OpenAI API key)")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return 130

    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
