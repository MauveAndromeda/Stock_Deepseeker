"""
策略比较工具
对比多个回测策略的性能，生成详细的对比报告
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json


class StrategyComparator:
    """策略比较器"""

    def __init__(self, output_dir: str = "comparison_results"):
        """
        初始化比较器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 设置绘图样式
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")

    def load_backtest_results(
        self,
        equity_file: str,
        trades_file: str,
        metrics: Optional[Dict] = None,
        name: str = "Strategy"
    ) -> Dict:
        """
        加载回测结果

        Args:
            equity_file: 权益曲线文件
            trades_file: 交易记录文件
            metrics: 性能指标字典
            name: 策略名称

        Returns:
            结果字典
        """
        print(f"📥 加载 {name} 的回测结果...")

        # 加载权益曲线
        equity_data = pd.read_csv(equity_file, parse_dates=['date'])
        equity_data.set_index('date', inplace=True)

        # 加载交易记录
        trades_data = pd.read_csv(trades_file, parse_dates=['timestamp'])

        # 如果没有提供metrics，从equity计算基本指标
        if metrics is None:
            metrics = self._calculate_basic_metrics(equity_data, trades_data)

        result = {
            'name': name,
            'equity_data': equity_data,
            'trades_data': trades_data,
            'metrics': metrics
        }

        print(f"  ✓ 加载完成: {len(equity_data)} 条权益数据, {len(trades_data)} 笔交易")
        return result

    def _calculate_basic_metrics(
        self,
        equity_data: pd.DataFrame,
        trades_data: pd.DataFrame
    ) -> Dict:
        """计算基本性能指标"""
        # 计算收益率
        initial_capital = equity_data['equity'].iloc[0]
        final_capital = equity_data['equity'].iloc[-1]
        total_return = (final_capital - initial_capital) / initial_capital

        # 计算年化收益率
        days = (equity_data.index[-1] - equity_data.index[0]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1

        # 计算最大回撤
        equity_curve = equity_data['equity'].values
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()

        # 计算夏普比率
        returns = equity_data['equity'].pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if len(returns) > 0 else 0

        # 交易统计
        winning_trades = len(trades_data[trades_data['pnl'] > 0])
        total_trades = len(trades_data)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': total_trades,
            'win_rate': win_rate
        }

    def compare_strategies(
        self,
        strategies: List[Dict],
        benchmark: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        对比多个策略

        Args:
            strategies: 策略列表，每个元素是load_backtest_results返回的字典
            benchmark: 基准数据 (可选)

        Returns:
            对比结果
        """
        print("\n" + "=" * 60)
        print("📊 策略对比分析")
        print("=" * 60)

        comparison = {
            'strategies': strategies,
            'benchmark': benchmark,
            'summary': self._create_summary_table(strategies),
            'rankings': self._rank_strategies(strategies)
        }

        # 显示汇总表
        self._display_summary(comparison['summary'])

        return comparison

    def _create_summary_table(self, strategies: List[Dict]) -> pd.DataFrame:
        """创建汇总表"""
        summary_data = []

        for strategy in strategies:
            metrics = strategy['metrics']
            row = {
                '策略名称': strategy['name'],
                '总收益率': f"{metrics['total_return']:.2%}",
                '年化收益率': f"{metrics['annualized_return']:.2%}",
                '最大回撤': f"{metrics['max_drawdown']:.2%}",
                '夏普比率': f"{metrics['sharpe_ratio']:.2f}",
                '交易次数': metrics['total_trades'],
                '胜率': f"{metrics['win_rate']:.2%}"
            }
            summary_data.append(row)

        return pd.DataFrame(summary_data)

    def _rank_strategies(self, strategies: List[Dict]) -> Dict:
        """策略排名"""
        rankings = {}

        # 按不同指标排名
        metrics_to_rank = [
            ('total_return', '总收益率', False),
            ('annualized_return', '年化收益率', False),
            ('max_drawdown', '最大回撤', True),  # 回撤越小越好
            ('sharpe_ratio', '夏普比率', False),
            ('win_rate', '胜率', False)
        ]

        for metric_key, metric_name, ascending in metrics_to_rank:
            sorted_strategies = sorted(
                strategies,
                key=lambda x: x['metrics'][metric_key],
                reverse=not ascending
            )
            rankings[metric_name] = [(s['name'], s['metrics'][metric_key]) for s in sorted_strategies]

        return rankings

    def _display_summary(self, summary_df: pd.DataFrame):
        """显示汇总表"""
        print("\n📈 性能汇总:")
        print(summary_df.to_string(index=False))
        print()

    def plot_equity_comparison(
        self,
        strategies: List[Dict],
        benchmark: Optional[pd.DataFrame] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制权益曲线对比图

        Args:
            strategies: 策略列表
            benchmark: 基准数据
            save_path: 保存路径
        """
        print("📊 绘制权益曲线对比图...")

        fig, axes = plt.subplots(2, 1, figsize=(14, 10))

        # 子图1: 归一化权益曲线
        ax1 = axes[0]
        for strategy in strategies:
            equity = strategy['equity_data']['equity']
            normalized = equity / equity.iloc[0] * 100  # 归一化为100基准
            ax1.plot(equity.index, normalized, label=strategy['name'], linewidth=2)

        if benchmark is not None:
            benchmark_normalized = benchmark / benchmark.iloc[0] * 100
            ax1.plot(benchmark.index, benchmark_normalized, label='Benchmark',
                    linestyle='--', linewidth=2, color='gray')

        ax1.set_title('归一化权益曲线对比 (基准=100)', fontsize=14, fontweight='bold')
        ax1.set_xlabel('日期')
        ax1.set_ylabel('归一化权益 (初始=100)')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)

        # 子图2: 回撤对比
        ax2 = axes[1]
        for strategy in strategies:
            equity = strategy['equity_data']['equity'].values
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max * 100
            ax2.plot(strategy['equity_data'].index, drawdown,
                    label=strategy['name'], linewidth=2)

        ax2.set_title('回撤对比', fontsize=14, fontweight='bold')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('回撤 (%)')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.fill_between(range(len(drawdown)), drawdown, 0, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"  ✓ 保存至: {save_path}")

        plt.close()

    def plot_metrics_comparison(
        self,
        strategies: List[Dict],
        save_path: Optional[str] = None
    ):
        """
        绘制指标对比图

        Args:
            strategies: 策略列表
            save_path: 保存路径
        """
        print("📊 绘制性能指标对比图...")

        fig, axes = plt.subplots(2, 3, figsize=(18, 10))

        strategy_names = [s['name'] for s in strategies]

        # 1. 总收益率
        returns = [s['metrics']['total_return'] * 100 for s in strategies]
        axes[0, 0].bar(strategy_names, returns, color=sns.color_palette("husl", len(strategies)))
        axes[0, 0].set_title('总收益率 (%)', fontweight='bold')
        axes[0, 0].set_ylabel('收益率 (%)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        for i, v in enumerate(returns):
            axes[0, 0].text(i, v, f'{v:.1f}%', ha='center', va='bottom')

        # 2. 年化收益率
        annual_returns = [s['metrics']['annualized_return'] * 100 for s in strategies]
        axes[0, 1].bar(strategy_names, annual_returns, color=sns.color_palette("husl", len(strategies)))
        axes[0, 1].set_title('年化收益率 (%)', fontweight='bold')
        axes[0, 1].set_ylabel('年化收益率 (%)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        for i, v in enumerate(annual_returns):
            axes[0, 1].text(i, v, f'{v:.1f}%', ha='center', va='bottom')

        # 3. 最大回撤
        drawdowns = [abs(s['metrics']['max_drawdown']) * 100 for s in strategies]
        axes[0, 2].bar(strategy_names, drawdowns, color=sns.color_palette("Reds_r", len(strategies)))
        axes[0, 2].set_title('最大回撤 (%)', fontweight='bold')
        axes[0, 2].set_ylabel('回撤 (%)')
        axes[0, 2].tick_params(axis='x', rotation=45)
        for i, v in enumerate(drawdowns):
            axes[0, 2].text(i, v, f'{v:.1f}%', ha='center', va='bottom')

        # 4. 夏普比率
        sharpe_ratios = [s['metrics']['sharpe_ratio'] for s in strategies]
        axes[1, 0].bar(strategy_names, sharpe_ratios, color=sns.color_palette("husl", len(strategies)))
        axes[1, 0].set_title('夏普比率', fontweight='bold')
        axes[1, 0].set_ylabel('夏普比率')
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].axhline(y=1.0, color='r', linestyle='--', label='优秀阈值')
        axes[1, 0].legend()
        for i, v in enumerate(sharpe_ratios):
            axes[1, 0].text(i, v, f'{v:.2f}', ha='center', va='bottom')

        # 5. 交易次数
        trade_counts = [s['metrics']['total_trades'] for s in strategies]
        axes[1, 1].bar(strategy_names, trade_counts, color=sns.color_palette("husl", len(strategies)))
        axes[1, 1].set_title('交易次数', fontweight='bold')
        axes[1, 1].set_ylabel('交易次数')
        axes[1, 1].tick_params(axis='x', rotation=45)
        for i, v in enumerate(trade_counts):
            axes[1, 1].text(i, v, f'{v}', ha='center', va='bottom')

        # 6. 胜率
        win_rates = [s['metrics']['win_rate'] * 100 for s in strategies]
        axes[1, 2].bar(strategy_names, win_rates, color=sns.color_palette("husl", len(strategies)))
        axes[1, 2].set_title('胜率 (%)', fontweight='bold')
        axes[1, 2].set_ylabel('胜率 (%)')
        axes[1, 2].tick_params(axis='x', rotation=45)
        axes[1, 2].axhline(y=50, color='r', linestyle='--', label='50%基准')
        axes[1, 2].legend()
        for i, v in enumerate(win_rates):
            axes[1, 2].text(i, v, f'{v:.1f}%', ha='center', va='bottom')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"  ✓ 保存至: {save_path}")

        plt.close()

    def plot_risk_return_scatter(
        self,
        strategies: List[Dict],
        save_path: Optional[str] = None
    ):
        """
        绘制风险-收益散点图

        Args:
            strategies: 策略列表
            save_path: 保存路径
        """
        print("📊 绘制风险-收益散点图...")

        plt.figure(figsize=(10, 8))

        for strategy in strategies:
            metrics = strategy['metrics']
            x = abs(metrics['max_drawdown']) * 100  # 风险 (回撤)
            y = metrics['annualized_return'] * 100  # 收益

            plt.scatter(x, y, s=200, alpha=0.6, label=strategy['name'])
            plt.annotate(
                strategy['name'],
                (x, y),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=10
            )

        plt.xlabel('最大回撤 (%)', fontsize=12)
        plt.ylabel('年化收益率 (%)', fontsize=12)
        plt.title('风险-收益分析 (左上角最优)', fontsize=14, fontweight='bold')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)

        # 添加参考线
        plt.axhline(y=0, color='gray', linestyle='--', linewidth=1)
        plt.axvline(x=0, color='gray', linestyle='--', linewidth=1)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"  ✓ 保存至: {save_path}")

        plt.close()

    def generate_comparison_report(
        self,
        strategies: List[Dict],
        benchmark: Optional[pd.DataFrame] = None,
        report_name: str = "strategy_comparison"
    ):
        """
        生成完整的对比报告

        Args:
            strategies: 策略列表
            benchmark: 基准数据
            report_name: 报告名称
        """
        print("\n" + "=" * 60)
        print("📊 生成策略对比报告")
        print("=" * 60)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = self.output_dir / f"{report_name}_{timestamp}"
        report_dir.mkdir(exist_ok=True)

        # 1. 权益曲线对比
        print("\n1️⃣ 生成权益曲线对比图...")
        self.plot_equity_comparison(
            strategies,
            benchmark,
            save_path=str(report_dir / "equity_comparison.png")
        )

        # 2. 指标对比
        print("\n2️⃣ 生成性能指标对比图...")
        self.plot_metrics_comparison(
            strategies,
            save_path=str(report_dir / "metrics_comparison.png")
        )

        # 3. 风险-收益散点图
        print("\n3️⃣ 生成风险-收益散点图...")
        self.plot_risk_return_scatter(
            strategies,
            save_path=str(report_dir / "risk_return_scatter.png")
        )

        # 4. 保存汇总数据
        print("\n4️⃣ 保存对比数据...")
        comparison = self.compare_strategies(strategies, benchmark)

        # 保存汇总表
        summary_df = comparison['summary']
        summary_df.to_csv(report_dir / "summary.csv", index=False)

        # 保存排名
        with open(report_dir / "rankings.json", 'w', encoding='utf-8') as f:
            json.dump(comparison['rankings'], f, indent=2, ensure_ascii=False)

        # 5. 生成Markdown报告
        print("\n5️⃣ 生成Markdown报告...")
        self._generate_markdown_report(comparison, report_dir)

        print("\n" + "=" * 60)
        print("✅ 对比报告生成完成！")
        print("=" * 60)
        print(f"\n📁 报告目录: {report_dir}")
        print("\n包含文件:")
        print("  - equity_comparison.png    (权益曲线对比)")
        print("  - metrics_comparison.png   (性能指标对比)")
        print("  - risk_return_scatter.png  (风险-收益分析)")
        print("  - summary.csv              (汇总表)")
        print("  - rankings.json            (排名数据)")
        print("  - report.md                (Markdown报告)")

    def _generate_markdown_report(self, comparison: Dict, report_dir: Path):
        """生成Markdown格式的报告"""
        report_lines = []

        report_lines.append("# 策略对比报告\n")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        report_lines.append("## 📊 性能汇总\n")
        report_lines.append(comparison['summary'].to_markdown(index=False))
        report_lines.append("\n\n")

        report_lines.append("## 🏆 策略排名\n")
        for metric_name, ranking in comparison['rankings'].items():
            report_lines.append(f"\n### {metric_name}\n")
            for i, (name, value) in enumerate(ranking, 1):
                if isinstance(value, float):
                    if metric_name == '最大回撤':
                        report_lines.append(f"{i}. {name}: {value:.2%}\n")
                    else:
                        report_lines.append(f"{i}. {name}: {value:.2f}\n")
                else:
                    report_lines.append(f"{i}. {name}: {value}\n")

        report_lines.append("\n## 📈 可视化图表\n")
        report_lines.append("\n### 权益曲线对比\n")
        report_lines.append("![权益曲线对比](equity_comparison.png)\n\n")
        report_lines.append("### 性能指标对比\n")
        report_lines.append("![性能指标对比](metrics_comparison.png)\n\n")
        report_lines.append("### 风险-收益分析\n")
        report_lines.append("![风险-收益分析](risk_return_scatter.png)\n\n")

        report_lines.append("## 💡 结论与建议\n")
        report_lines.append(self._generate_conclusions(comparison))

        # 保存报告
        with open(report_dir / "report.md", 'w', encoding='utf-8') as f:
            f.writelines(report_lines)

    def _generate_conclusions(self, comparison: Dict) -> str:
        """生成结论和建议"""
        strategies = comparison['strategies']
        rankings = comparison['rankings']

        conclusions = []

        # 找出最佳策略
        best_return = rankings['年化收益率'][0]
        best_risk = rankings['最大回撤'][0]  # 回撤最小
        best_sharpe = rankings['夏普比率'][0]

        conclusions.append(f"\n### 最佳表现策略\n")
        conclusions.append(f"- **最高年化收益率**: {best_return[0]} ({best_return[1]:.2%})\n")
        conclusions.append(f"- **最低最大回撤**: {best_risk[0]} ({abs(best_risk[1]):.2%})\n")
        conclusions.append(f"- **最高夏普比率**: {best_sharpe[0]} ({best_sharpe[1]:.2f})\n")

        conclusions.append(f"\n### 建议\n")
        conclusions.append("1. 如果追求高收益，选择年化收益率最高的策略\n")
        conclusions.append("2. 如果注重风险控制，选择回撤最小的策略\n")
        conclusions.append("3. 如果追求风险调整后收益，选择夏普比率最高的策略\n")
        conclusions.append("4. 考虑策略组合，分散风险并提升整体表现\n")

        return ''.join(conclusions)


# 使用示例
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="策略对比工具")
    parser.add_argument(
        '--strategies',
        nargs='+',
        required=True,
        help='策略配置列表，格式: name:equity_file:trades_file'
    )
    parser.add_argument(
        '--benchmark',
        type=str,
        help='基准数据文件 (可选)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='comparison_results',
        help='输出目录'
    )
    parser.add_argument(
        '--report-name',
        type=str,
        default='strategy_comparison',
        help='报告名称'
    )

    args = parser.parse_args()

    # 创建比较器
    comparator = StrategyComparator(output_dir=args.output)

    # 加载策略
    strategies = []
    for strategy_config in args.strategies:
        parts = strategy_config.split(':')
        if len(parts) != 3:
            print(f"错误: 策略配置格式错误: {strategy_config}")
            print("正确格式: name:equity_file:trades_file")
            continue

        name, equity_file, trades_file = parts
        strategy = comparator.load_backtest_results(
            equity_file=equity_file,
            trades_file=trades_file,
            name=name
        )
        strategies.append(strategy)

    if not strategies:
        print("错误: 没有成功加载任何策略")
        sys.exit(1)

    # 加载基准 (可选)
    benchmark = None
    if args.benchmark:
        print(f"\n📥 加载基准数据: {args.benchmark}")
        benchmark_df = pd.read_csv(args.benchmark, parse_dates=['date'])
        benchmark_df.set_index('date', inplace=True)
        benchmark = benchmark_df['equity']

    # 生成对比报告
    comparator.generate_comparison_report(
        strategies=strategies,
        benchmark=benchmark,
        report_name=args.report_name
    )

    print("\n✨ 使用示例:")
    print("  # 对比两个策略")
    print("  python tools/compare_strategies.py \\")
    print("    --strategies \\")
    print("      'Basic:backtest_results/equity_basic.csv:backtest_results/trades_basic.csv' \\")
    print("      'Enhanced:backtest_results/equity_enhanced.csv:backtest_results/trades_enhanced.csv' \\")
    print("    --report-name basic_vs_enhanced")
