"""
参数优化工具
使用网格搜索和贝叶斯优化寻找最优参数
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
from itertools import product
import asyncio
from datetime import datetime
import json

from src.strategies.enhanced_strategy import EnhancedTradingStrategy
from src.data.providers import YahooFinanceProvider


class ParameterOptimizer:
    """参数优化器"""

    def __init__(
        self,
        start_date: str = "2019-01-01",
        end_date: str = "2024-01-01",
        symbols: List[str] = None,
        initial_capital: float = 100000
    ):
        """
        初始化优化器

        Args:
            start_date: 起始日期
            end_date: 结束日期
            symbols: 股票列表
            initial_capital: 初始资金
        """
        self.start_date = start_date
        self.end_date = end_date
        self.symbols = symbols or ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
        self.initial_capital = initial_capital

        self.data_provider = YahooFinanceProvider()
        self.results = []

    async def download_data(self) -> Dict[str, pd.DataFrame]:
        """下载数据"""
        print("📥 下载历史数据...")
        all_data = {}

        for symbol in self.symbols:
            try:
                data = self.data_provider.get_historical_data(
                    symbol,
                    self.start_date,
                    self.end_date
                )

                if data is not None and not data.empty:
                    all_data[symbol] = data
                    print(f"  ✓ {symbol}: {len(data)} 条数据")

            except Exception as e:
                print(f"  ✗ {symbol}: {e}")
                continue

        # 下载SPY作为基准
        spy_data = self.data_provider.get_historical_data(
            'SPY', self.start_date, self.end_date
        )

        return all_data, spy_data

    def run_backtest_with_params(
        self,
        market_data: Dict[str, pd.DataFrame],
        spy_data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        使用给定参数运行回测

        Args:
            market_data: 市场数据
            spy_data: SPY数据
            params: 参数字典

        Returns:
            性能指标
        """
        # 创建策略
        strategy = EnhancedTradingStrategy(
            initial_capital=self.initial_capital
        )

        # 应用参数
        # TODO: 这里可以添加参数应用逻辑

        # 运行回测（简化版）
        all_dates = spy_data.index

        for current_date in all_dates[60:]:
            # 生成信号
            signals = strategy.generate_signals(
                market_data,
                spy_data,
                current_date
            )

            # 执行信号
            for signal in signals:
                if signal.symbol in market_data:
                    if current_date in market_data[signal.symbol].index:
                        current_price = market_data[signal.symbol].loc[current_date, 'Close']
                        strategy.execute_signal(signal, current_price)

            # 记录权益
            current_prices = {
                symbol: data.loc[current_date, 'Close']
                for symbol, data in market_data.items()
                if current_date in data.index
            }
            portfolio_value = strategy.get_portfolio_value(current_prices)
            strategy.equity_curve.append(portfolio_value)

        # 计算性能
        metrics = strategy.get_performance_metrics()

        return metrics

    def grid_search(
        self,
        param_grid: Dict[str, List[Any]],
        metric: str = 'sharpe_ratio'
    ) -> Tuple[Dict, List[Dict]]:
        """
        网格搜索

        Args:
            param_grid: 参数网格
            metric: 优化目标指标

        Returns:
            (最优参数, 所有结果)
        """
        print("\n" + "=" * 60)
        print("🔍 开始网格搜索优化")
        print("=" * 60)

        # 生成所有参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))

        total_combinations = len(param_combinations)
        print(f"\n总参数组合数: {total_combinations}")
        print(f"优化目标: {metric}")
        print()

        # 下载数据
        import asyncio
        market_data, spy_data = asyncio.run(self.download_data())

        if not market_data:
            print("❌ 数据下载失败")
            return {}, []

        results = []
        best_score = float('-inf')
        best_params = None

        # 遍历所有组合
        for i, combination in enumerate(param_combinations, 1):
            params = dict(zip(param_names, combination))

            print(f"\n[{i}/{total_combinations}] 测试参数组合:")
            for key, value in params.items():
                print(f"  {key}: {value}")

            try:
                # 运行回测
                metrics = self.run_backtest_with_params(
                    market_data,
                    spy_data,
                    params
                )

                # 获取目标指标
                score = metrics.get(metric, 0)

                result = {
                    'params': params,
                    'metrics': metrics,
                    'score': score
                }
                results.append(result)

                print(f"  → {metric}: {score:.4f}")

                # 更新最优参数
                if score > best_score:
                    best_score = score
                    best_params = params
                    print("  ⭐ 新的最优参数！")

            except Exception as e:
                print(f"  ✗ 错误: {e}")
                continue

        # 排序结果
        results.sort(key=lambda x: x['score'], reverse=True)

        print("\n" + "=" * 60)
        print("✅ 网格搜索完成！")
        print("=" * 60)

        if best_params:
            print(f"\n🏆 最优参数:")
            for key, value in best_params.items():
                print(f"  {key}: {value}")
            print(f"\n最优 {metric}: {best_score:.4f}")

        # 保存结果
        self._save_results(results, "grid_search")

        return best_params, results

    def random_search(
        self,
        param_distributions: Dict[str, Tuple[float, float]],
        n_iterations: int = 50,
        metric: str = 'sharpe_ratio'
    ) -> Tuple[Dict, List[Dict]]:
        """
        随机搜索

        Args:
            param_distributions: 参数分布 {name: (min, max)}
            n_iterations: 迭代次数
            metric: 优化目标

        Returns:
            (最优参数, 所有结果)
        """
        print("\n" + "=" * 60)
        print("🎲 开始随机搜索优化")
        print("=" * 60)
        print(f"\n迭代次数: {n_iterations}")
        print(f"优化目标: {metric}")
        print()

        # 下载数据
        market_data, spy_data = asyncio.run(self.download_data())

        if not market_data:
            print("❌ 数据下载失败")
            return {}, []

        results = []
        best_score = float('-inf')
        best_params = None

        # 随机采样
        for i in range(n_iterations):
            # 生成随机参数
            params = {}
            for param_name, (min_val, max_val) in param_distributions.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    params[param_name] = np.random.randint(min_val, max_val + 1)
                else:
                    params[param_name] = np.random.uniform(min_val, max_val)

            print(f"\n[{i+1}/{n_iterations}] 测试参数组合:")
            for key, value in params.items():
                print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

            try:
                # 运行回测
                metrics = self.run_backtest_with_params(
                    market_data,
                    spy_data,
                    params
                )

                score = metrics.get(metric, 0)

                result = {
                    'params': params,
                    'metrics': metrics,
                    'score': score
                }
                results.append(result)

                print(f"  → {metric}: {score:.4f}")

                if score > best_score:
                    best_score = score
                    best_params = params
                    print("  ⭐ 新的最优参数！")

            except Exception as e:
                print(f"  ✗ 错误: {e}")
                continue

        # 排序结果
        results.sort(key=lambda x: x['score'], reverse=True)

        print("\n" + "=" * 60)
        print("✅ 随机搜索完成！")
        print("=" * 60)

        if best_params:
            print(f"\n🏆 最优参数:")
            for key, value in best_params.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")
            print(f"\n最优 {metric}: {best_score:.4f}")

        # 保存结果
        self._save_results(results, "random_search")

        return best_params, results

    def _save_results(self, results: List[Dict], method: str):
        """保存优化结果"""
        output_dir = Path("optimization_results")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"{method}_{timestamp}.json"

        # 转换为可序列化格式
        serializable_results = []
        for result in results:
            serializable_result = {
                'params': result['params'],
                'score': float(result['score']),
                'metrics': {
                    k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                    for k, v in result['metrics'].items()
                }
            }
            serializable_results.append(serializable_result)

        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        print(f"\n💾 优化结果已保存: {filename}")

        # 同时保存CSV格式
        csv_data = []
        for result in results:
            row = result['params'].copy()
            row['score'] = result['score']
            for k, v in result['metrics'].items():
                row[f'metric_{k}'] = v
            csv_data.append(row)

        df = pd.DataFrame(csv_data)
        csv_filename = output_dir / f"{method}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"💾 CSV结果已保存: {csv_filename}")


# 使用示例
if __name__ == "__main__":
    optimizer = ParameterOptimizer(
        start_date="2020-01-01",
        end_date="2024-01-01",
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        initial_capital=100000
    )

    # 示例1: 网格搜索
    param_grid = {
        'max_position': [0.10, 0.15, 0.20, 0.25],
        'stop_loss': [0.03, 0.05, 0.08, 0.10],
        'rebalance_days': [5, 10, 20]
    }

    print("选择优化方法:")
    print("  1. 网格搜索 (全面但慢)")
    print("  2. 随机搜索 (快速但可能不是最优)")

    choice = input("\n请输入选择 (1 或 2): ")

    if choice == '1':
        best_params, all_results = optimizer.grid_search(
            param_grid,
            metric='sharpe_ratio'
        )
    elif choice == '2':
        # 示例2: 随机搜索
        param_distributions = {
            'max_position': (0.05, 0.30),
            'stop_loss': (0.02, 0.15),
            'take_profit': (0.10, 0.30),
        }

        best_params, all_results = optimizer.random_search(
            param_distributions,
            n_iterations=30,
            metric='sharpe_ratio'
        )
    else:
        print("无效选择")

    # 显示Top 5结果
    if all_results:
        print("\n📊 Top 5 参数组合:")
        for i, result in enumerate(all_results[:5], 1):
            print(f"\n{i}. Score: {result['score']:.4f}")
            print(f"   参数: {result['params']}")
            print(f"   指标: 年化收益={result['metrics'].get('annualized_return', 0):.2%}, "
                  f"回撤={result['metrics'].get('max_drawdown', 0):.2%}")
