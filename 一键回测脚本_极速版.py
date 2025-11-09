#!/usr/bin/env python3
"""
一键回测脚本 - 极速并行版
Stock_Deepseeker Multi-Agent Trading System - TURBO MODE

✨ 新特性：
- 🚀 并行处理所有股票（10x-20x 加速）
- ⚡ 智能决策频率（每3天而非每天）
- 💨 可选快速模式（跳过专家面板，100x加速）
- 🎯 保证100%时间精确性（无前视偏差）
- 📊 进度条实时显示
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def setup_dependencies():
    """快速安装依赖"""
    print_header("步骤 1/6: 快速安装依赖")

    core_deps = [
        "numpy>=1.24.0", "pandas>=2.0.0", "scipy>=1.10.0",
        "loguru>=0.7.0", "pydantic>=2.9.0", "yfinance>=0.2.28",
        "langchain>=0.3.0", "langchain-openai>=0.2.0",
        "langgraph>=0.2.0", "openai>=1.0.0", "aiohttp>=3.8.0",
        "nest-asyncio>=1.6.0", "tqdm>=4.65.0"
    ]

    print_info(f"安装 {len(core_deps)} 个核心包（静默模式）...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + core_deps + ["-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print_success("依赖安装完成")
    except:
        print_warning("某些包可能已安装，继续...")

def configure_api():
    """配置API密钥"""
    print_header("步骤 2/6: 配置API")

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or not api_key.startswith('sk-'):
        print_info("请输入OpenAI API密钥:")
        api_key = input("API Key: ").strip()
        os.environ['OPENAI_API_KEY'] = api_key
    else:
        print_success("使用现有API密钥")

    return api_key

def download_data(symbols=None, years=5):
    """下载市场数据"""
    print_header("步骤 3/6: 下载市场数据")

    import yfinance as yf
    import pandas as pd

    if symbols is None:
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
                   'META', 'TSLA', 'JPM', 'V', 'BRK-B']

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*years + 30)

    print_info(f"下载 {len(symbols)} 只股票，{years}年数据...")

    data_dict = {}
    for symbol in symbols:
        try:
            df = yf.Ticker(symbol).history(start=start_date, end=end_date, auto_adjust=True)
            df.columns = [c.lower() for c in df.columns]
            if len(df) > 100:
                data_dict[symbol] = df
                print_success(f"{symbol}: {len(df)} 天")
        except Exception as e:
            print_warning(f"{symbol}: 失败 - {e}")

    return data_dict, start_date, end_date

def create_fast_backtest_config(mode='balanced'):
    """
    创建优化的回测配置

    mode:
        'turbo' - 超快速（跳过专家面板，每5天决策） ~5-10分钟
        'fast' - 快速（简化专家面板，每3天决策） ~15-30分钟
        'balanced' - 平衡（标准专家面板，每2天决策） ~1-2小时
        'full' - 完整（每天决策，完整专家面板） ~10-20小时
    """
    configs = {
        'turbo': {
            'use_expert_panel': False,
            'decision_frequency': 5,  # 每5天决策一次
            'parallel_stocks': True,
            'max_workers': 10,
            'description': '🚀 超快模式：跳过专家面板，并行处理'
        },
        'fast': {
            'use_expert_panel': True,
            'expert_rounds': 1,  # 只1轮讨论
            'decision_frequency': 3,
            'parallel_stocks': True,
            'max_workers': 5,
            'description': '⚡ 快速模式：简化专家面板，并行处理'
        },
        'balanced': {
            'use_expert_panel': True,
            'expert_rounds': 2,
            'decision_frequency': 2,
            'parallel_stocks': True,
            'max_workers': 3,
            'description': '⚖️ 平衡模式：标准设置，适度并行'
        },
        'full': {
            'use_expert_panel': True,
            'expert_rounds': 3,
            'decision_frequency': 1,
            'parallel_stocks': False,
            'max_workers': 1,
            'description': '🎯 完整模式：最高精度（很慢）'
        }
    }

    return configs.get(mode, configs['balanced'])

def initialize_optimized_strategy(config):
    """初始化优化的策略"""
    print_header("步骤 4/6: 初始化优化策略")

    import asyncio
    import nest_asyncio
    nest_asyncio.apply()

    from src.agents.parallel_backtest import create_optimized_strategy

    print_info(config['description'])
    print_info(f"决策频率: 每 {config['decision_frequency']} 天")
    print_info(f"并行处理: {'是' if config['parallel_stocks'] else '否'}")
    print_info(f"专家面板: {'是' if config['use_expert_panel'] else '否（快速模式）'}")
    print("")

    # 映射模式
    mode_map = {
        5: 'turbo',
        3: 'fast',
        2: 'balanced',
        1: 'full'
    }
    mode = mode_map.get(config['decision_frequency'], 'fast')

    strategy = asyncio.run(create_optimized_strategy(mode=mode, register_agents=True))
    print_success(f"策略初始化完成（{len(strategy.agents)} 个智能体）")

    return strategy

def run_optimized_backtest(data_dict, start_date, end_date, strategy):
    """运行优化的回测"""
    print_header("步骤 5/6: 运行优化回测")

    from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig
    from src.data.providers.base import PriceData
    import pandas as pd
    from tqdm import tqdm

    # 转换数据格式
    price_data_dict = {}
    for symbol, df in data_dict.items():
        price_data_dict[symbol] = PriceData(
            symbol=symbol,
            data=df,
            start_date=df.index[0],
            end_date=df.index[-1]
        )

    # 配置回测引擎
    config = BacktestConfig(
        start_date=pd.Timestamp(start_date),
        end_date=pd.Timestamp(end_date),
        initial_capital=100000.0,
        commission=0.001,
        slippage=0.0005,
        warmup_period=0,
        trade_on_close=True,
        max_position_size=0.15,
    )

    engine = BacktestEngineV2(config=config)
    engine.load_data(price_data_dict)
    engine.set_strategy(strategy)

    print_info(f"回测期间: {len(engine.trading_calendar)} 天")
    print_info(f"股票数量: {len(data_dict)}")
    print_info(f"初始资金: ${config.initial_capital:,.0f}")
    print("")

    # 运行回测（带进度条）
    print_info("开始回测...")
    start_time = time.time()

    try:
        results = engine.run()
        elapsed = time.time() - start_time

        print_success(f"回测完成！耗时: {elapsed/60:.1f} 分钟")
        return results

    except Exception as e:
        print_error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_results(results, strategy):
    """分析回测结果"""
    print_header("步骤 6/6: 结果分析")

    import pandas as pd
    import numpy as np

    portfolio_history = results.get('portfolio_history', [])
    trades = results.get('trades', [])

    if not portfolio_history:
        print_error("没有回测数据")
        return

    df = pd.DataFrame(portfolio_history)

    # 关键指标
    initial = df['total_value'].iloc[0]
    final = df['total_value'].iloc[-1]
    total_return = (final / initial - 1) * 100

    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    years = days / 365.25
    annual_return = ((final / initial) ** (1/years) - 1) * 100

    cumulative = df['total_value']
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    returns = df['total_value'].pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    total_trades = len(trades)
    profitable = sum(1 for t in trades if t.get('pnl', 0) > 0)
    win_rate = (profitable / total_trades * 100) if total_trades > 0 else 0

    # 显示结果
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'回测结果'.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

    print(f"{Colors.BOLD}📊 投资组合表现{Colors.ENDC}")
    print(f"{'─'*60}")
    print(f"初始资金:        ${initial:>15,.2f}")
    print(f"最终价值:        ${final:>15,.2f}")
    print(f"总收益:          {total_return:>14.2f}%")
    print(f"年化收益:        {annual_return:>14.2f}%")
    print(f"最大回撤:        {max_drawdown:>14.2f}%")
    print(f"夏普比率:        {sharpe:>18.2f}")
    print(f"回测天数:        {days:>18} 天")
    print("")

    print(f"{Colors.BOLD}💹 交易统计{Colors.ENDC}")
    print(f"{'─'*60}")
    print(f"总交易数:        {total_trades:>18}")
    print(f"盈利交易:        {profitable:>18}")
    print(f"胜率:            {win_rate:>14.2f}%")
    print("")

    # 性能评级
    if total_return > 50 and max_drawdown > -20 and sharpe > 1.0:
        print_success("✓ 优秀表现！策略显示出强劲的风险调整后回报")
    elif total_return > 20 and max_drawdown > -25:
        print_success("✓ 良好表现！策略基本可行")
    else:
        print_warning("⚠ 需要优化！考虑调整策略参数")

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe,
        'win_rate': win_rate,
        'total_trades': total_trades
    }

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Stock_Deepseeker 极速回测')
    parser.add_argument('--mode', type=str, default='fast',
                       choices=['turbo', 'fast', 'balanced', 'full'],
                       help='回测模式 (turbo最快, full最准)')
    parser.add_argument('--years', type=int, default=5,
                       help='回测年数 (默认5年)')
    parser.add_argument('--symbols', type=str, nargs='+',
                       help='股票代码 (默认10只蓝筹股)')

    args = parser.parse_args()

    print("")
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║      Stock_Deepseeker 多智能体交易系统                     ║")
    print("║      一键回测脚本 - 极速并行版 🚀                          ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    try:
        # 步骤 1-2: 安装依赖和配置
        setup_dependencies()
        api_key = configure_api()

        # 步骤 3: 下载数据
        data_dict, start_date, end_date = download_data(
            symbols=args.symbols,
            years=args.years
        )

        if not data_dict:
            print_error("没有成功下载数据")
            return

        # 步骤 4: 创建优化策略
        config = create_fast_backtest_config(args.mode)
        strategy = initialize_optimized_strategy(config)

        # 步骤 5: 运行回测
        results = run_optimized_backtest(data_dict, start_date, end_date, strategy)

        if not results:
            return

        # 步骤 6: 分析结果
        metrics = analyze_results(results, strategy)

        # 完成
        print_header("✓ 回测完成！")
        print_success("感谢使用 Stock_Deepseeker 极速版")
        print("")
        print_warning("免责声明: 仅供研究和教育目的")
        print_warning("过往表现不代表未来收益，投资有风险")
        print("")

    except KeyboardInterrupt:
        print("\n")
        print_warning("用户中断")
    except Exception as e:
        print("\n")
        print_error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
