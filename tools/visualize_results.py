"""
回测结果可视化工具
生成专业的图表和报告
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置seaborn样式
sns.set_style("whitegrid")
sns.set_palette("husl")


class BacktestVisualizer:
    """回测结果可视化器"""

    def __init__(self, output_dir: str = "backtest_results"):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def plot_equity_curve(
        self,
        equity_data: pd.DataFrame,
        benchmark_data: Optional[pd.DataFrame] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制权益曲线

        Args:
            equity_data: 权益数据
            benchmark_data: 基准数据（可选）
            save_path: 保存路径
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # 主图：权益曲线
        if 'equity' in equity_data.columns:
            equity_series = equity_data['equity']
        else:
            equity_series = equity_data.iloc[:, 0]

        # 归一化到100开始
        normalized_equity = equity_series / equity_series.iloc[0] * 100

        ax1.plot(normalized_equity.index, normalized_equity.values,
                label='策略', linewidth=2, color='#2E86AB')

        # 如果有基准数据
        if benchmark_data is not None:
            if 'equity' in benchmark_data.columns:
                benchmark_series = benchmark_data['equity']
            else:
                benchmark_series = benchmark_data.iloc[:, 0]

            normalized_benchmark = benchmark_series / benchmark_series.iloc[0] * 100
            ax1.plot(normalized_benchmark.index, normalized_benchmark.values,
                    label='基准 (SPY)', linewidth=2, color='#A23B72', alpha=0.7)

        ax1.set_title('权益曲线对比', fontsize=16, fontweight='bold', pad=20)
        ax1.set_xlabel('日期', fontsize=12)
        ax1.set_ylabel('归一化收益 (起始=100)', fontsize=12)
        ax1.legend(fontsize=11, loc='upper left')
        ax1.grid(True, alpha=0.3)

        # 填充区域
        ax1.fill_between(normalized_equity.index, 100, normalized_equity.values,
                        alpha=0.2, color='#2E86AB')

        # 下图：回撤
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax * 100

        ax2.fill_between(drawdown.index, 0, drawdown.values,
                        color='#F18F01', alpha=0.6, label='回撤')
        ax2.plot(drawdown.index, drawdown.values, color='#C73E1D', linewidth=1.5)

        ax2.set_title('回撤曲线', fontsize=16, fontweight='bold', pad=20)
        ax2.set_xlabel('日期', fontsize=12)
        ax2.set_ylabel('回撤 (%)', fontsize=12)
        ax2.legend(fontsize=11, loc='lower left')
        ax2.grid(True, alpha=0.3)

        # 标注最大回撤
        max_dd_idx = drawdown.idxmin()
        max_dd_val = drawdown.min()
        ax2.annotate(f'最大回撤: {max_dd_val:.2f}%',
                    xy=(max_dd_idx, max_dd_val),
                    xytext=(max_dd_idx, max_dd_val - 5),
                    arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                    fontsize=10, color='red', fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ 权益曲线已保存: {save_path}")

        plt.close()

    def plot_monthly_returns(
        self,
        equity_data: pd.DataFrame,
        save_path: Optional[str] = None
    ):
        """
        绘制月度收益热力图

        Args:
            equity_data: 权益数据
            save_path: 保存路径
        """
        if 'equity' in equity_data.columns:
            equity_series = equity_data['equity']
        else:
            equity_series = equity_data.iloc[:, 0]

        # 计算日收益率
        returns = equity_series.pct_change().dropna()

        # 按月聚合
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1) * 100

        # 创建年-月矩阵
        monthly_returns_df = monthly_returns.to_frame('returns')
        monthly_returns_df['year'] = monthly_returns_df.index.year
        monthly_returns_df['month'] = monthly_returns_df.index.month

        pivot_table = monthly_returns_df.pivot(
            index='year',
            columns='month',
            values='returns'
        )

        # 月份名称
        month_names = ['1月', '2月', '3月', '4月', '5月', '6月',
                      '7月', '8月', '9月', '10月', '11月', '12月']
        pivot_table.columns = [month_names[i-1] for i in pivot_table.columns]

        # 绘制热力图
        fig, ax = plt.subplots(figsize=(14, 8))

        # 自定义colormap
        cmap = sns.diverging_palette(250, 10, as_cmap=True)

        sns.heatmap(pivot_table, annot=True, fmt='.1f', cmap=cmap,
                   center=0, cbar_kws={'label': '收益率 (%)'}, ax=ax,
                   linewidths=0.5, linecolor='gray')

        ax.set_title('月度收益热力图', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('月份', fontsize=12)
        ax.set_ylabel('年份', fontsize=12)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ 月度收益热力图已保存: {save_path}")

        plt.close()

    def plot_trade_analysis(
        self,
        trades_data: pd.DataFrame,
        save_path: Optional[str] = None
    ):
        """
        绘制交易分析图

        Args:
            trades_data: 交易数据
            save_path: 保存路径
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # 1. PnL分布
        ax1 = fig.add_subplot(gs[0, :2])
        if 'pnl' in trades_data.columns:
            pnl_data = trades_data['pnl'].dropna()

            ax1.hist(pnl_data, bins=50, color='#2E86AB', alpha=0.7, edgecolor='black')
            ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
            ax1.axvline(x=pnl_data.mean(), color='green', linestyle='--',
                       linewidth=2, label=f'均值: ${pnl_data.mean():.2f}')

            ax1.set_title('交易盈亏分布', fontsize=14, fontweight='bold')
            ax1.set_xlabel('盈亏 ($)', fontsize=11)
            ax1.set_ylabel('频数', fontsize=11)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

        # 2. 胜率饼图
        ax2 = fig.add_subplot(gs[0, 2])
        if 'pnl' in trades_data.columns:
            wins = (trades_data['pnl'] > 0).sum()
            losses = (trades_data['pnl'] < 0).sum()

            colors = ['#06D6A0', '#EF476F']
            explode = (0.05, 0)

            ax2.pie([wins, losses], labels=['盈利', '亏损'],
                   autopct='%1.1f%%', startangle=90, colors=colors,
                   explode=explode, textprops={'fontsize': 11})
            ax2.set_title('胜率分布', fontsize=14, fontweight='bold')

        # 3. 累计PnL
        ax3 = fig.add_subplot(gs[1, :])
        if 'pnl' in trades_data.columns and 'timestamp' in trades_data.columns:
            trades_sorted = trades_data.sort_values('timestamp')
            cumulative_pnl = trades_sorted['pnl'].cumsum()

            ax3.plot(trades_sorted['timestamp'], cumulative_pnl,
                    linewidth=2, color='#2E86AB')
            ax3.fill_between(trades_sorted['timestamp'], 0, cumulative_pnl,
                           alpha=0.3, color='#2E86AB')

            ax3.set_title('累计盈亏曲线', fontsize=14, fontweight='bold')
            ax3.set_xlabel('日期', fontsize=11)
            ax3.set_ylabel('累计盈亏 ($)', fontsize=11)
            ax3.grid(True, alpha=0.3)

        # 4. 持仓时间分布
        ax4 = fig.add_subplot(gs[2, 0])
        if 'holding_period' in trades_data.columns:
            holding_periods = trades_data['holding_period'].dropna()

            ax4.hist(holding_periods, bins=30, color='#F18F01', alpha=0.7,
                    edgecolor='black')
            ax4.set_title('持仓时间分布', fontsize=14, fontweight='bold')
            ax4.set_xlabel('天数', fontsize=11)
            ax4.set_ylabel('频数', fontsize=11)
            ax4.grid(True, alpha=0.3)

        # 5. 按股票的PnL
        ax5 = fig.add_subplot(gs[2, 1:])
        if 'symbol' in trades_data.columns and 'pnl' in trades_data.columns:
            symbol_pnl = trades_data.groupby('symbol')['pnl'].sum().sort_values()

            colors_bar = ['#EF476F' if x < 0 else '#06D6A0' for x in symbol_pnl.values]

            symbol_pnl.plot(kind='barh', color=colors_bar, ax=ax5, edgecolor='black')
            ax5.set_title('各股票累计盈亏', fontsize=14, fontweight='bold')
            ax5.set_xlabel('累计盈亏 ($)', fontsize=11)
            ax5.set_ylabel('股票代码', fontsize=11)
            ax5.grid(True, alpha=0.3, axis='x')

        plt.suptitle('交易分析报告', fontsize=18, fontweight='bold', y=0.995)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ 交易分析图已保存: {save_path}")

        plt.close()

    def plot_performance_metrics(
        self,
        metrics: Dict,
        save_path: Optional[str] = None
    ):
        """
        绘制性能指标对比图

        Args:
            metrics: 性能指标字典
            save_path: 保存路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 提取指标
        metric_names = []
        metric_values = []

        for key, value in metrics.items():
            if isinstance(value, (int, float)) and key not in ['total_trades', 'final_equity']:
                metric_names.append(key.replace('_', ' ').title())
                metric_values.append(value)

        # 1. 关键指标
        ax1 = axes[0, 0]
        key_metrics = {
            'Annual Return': metrics.get('annualized_return', 0) * 100,
            'Max Drawdown': abs(metrics.get('max_drawdown', 0)) * 100,
            'Sharpe Ratio': metrics.get('sharpe_ratio', 0),
            'Win Rate': metrics.get('win_rate', 0) * 100
        }

        bars = ax1.barh(list(key_metrics.keys()), list(key_metrics.values()),
                       color=['#06D6A0', '#EF476F', '#2E86AB', '#F18F01'])

        for i, (name, value) in enumerate(key_metrics.items()):
            if 'Ratio' in name:
                ax1.text(value + 0.05, i, f'{value:.2f}', va='center', fontsize=10)
            else:
                ax1.text(value + 1, i, f'{value:.1f}%', va='center', fontsize=10)

        ax1.set_title('关键性能指标', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')

        # 2. 风险收益散点图
        ax2 = axes[0, 1]
        returns = metrics.get('annualized_return', 0) * 100
        volatility = metrics.get('volatility', 0) * 100

        ax2.scatter(volatility, returns, s=300, c='#2E86AB', alpha=0.6,
                   edgecolors='black', linewidth=2)
        ax2.annotate('策略', xy=(volatility, returns),
                    xytext=(volatility + 1, returns + 1),
                    fontsize=12, fontweight='bold')

        ax2.set_title('风险-收益分析', fontsize=14, fontweight='bold')
        ax2.set_xlabel('年化波动率 (%)', fontsize=11)
        ax2.set_ylabel('年化收益率 (%)', fontsize=11)
        ax2.grid(True, alpha=0.3)

        # 3. 月度统计
        ax3 = axes[1, 0]
        monthly_stats = {
            'Total Trades': metrics.get('total_trades', 0),
            'Winning': int(metrics.get('total_trades', 0) * metrics.get('win_rate', 0)),
            'Losing': int(metrics.get('total_trades', 0) * (1 - metrics.get('win_rate', 0)))
        }

        ax3.bar(monthly_stats.keys(), monthly_stats.values(),
               color=['#2E86AB', '#06D6A0', '#EF476F'], alpha=0.7,
               edgecolor='black')

        for i, (name, value) in enumerate(monthly_stats.items()):
            ax3.text(i, value + 2, str(int(value)), ha='center', fontsize=10,
                    fontweight='bold')

        ax3.set_title('交易统计', fontsize=14, fontweight='bold')
        ax3.set_ylabel('次数', fontsize=11)
        ax3.grid(True, alpha=0.3, axis='y')

        # 4. 收益组成
        ax4 = axes[1, 1]
        final_equity = metrics.get('final_equity', 100000)
        initial_capital = 100000  # 假设

        profit_loss = {
            '初始资金': initial_capital,
            '净利润': final_equity - initial_capital
        }

        colors_pl = ['#2E86AB', '#06D6A0' if profit_loss['净利润'] > 0 else '#EF476F']

        ax4.bar(profit_loss.keys(), profit_loss.values(),
               color=colors_pl, alpha=0.7, edgecolor='black')

        for i, (name, value) in enumerate(profit_loss.items()):
            ax4.text(i, value / 2, f'${value:,.0f}', ha='center', va='center',
                    fontsize=12, fontweight='bold', color='white')

        ax4.set_title('收益组成', fontsize=14, fontweight='bold')
        ax4.set_ylabel('金额 ($)', fontsize=11)
        ax4.grid(True, alpha=0.3, axis='y')

        plt.suptitle('性能指标仪表盘', fontsize=18, fontweight='bold', y=0.995)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ 性能指标图已保存: {save_path}")

        plt.close()

    def generate_complete_report(
        self,
        equity_file: str,
        trades_file: Optional[str] = None,
        metrics: Optional[Dict] = None,
        benchmark_file: Optional[str] = None
    ):
        """
        生成完整的可视化报告

        Args:
            equity_file: 权益曲线文件
            trades_file: 交易记录文件
            metrics: 性能指标
            benchmark_file: 基准数据文件
        """
        print("\n" + "=" * 60)
        print("📊 生成可视化报告")
        print("=" * 60)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 读取数据
        equity_data = pd.read_csv(equity_file, index_col=0, parse_dates=True)

        benchmark_data = None
        if benchmark_file and Path(benchmark_file).exists():
            benchmark_data = pd.read_csv(benchmark_file, index_col=0, parse_dates=True)

        # 1. 权益曲线
        print("\n1. 生成权益曲线...")
        equity_path = self.output_dir / f"chart_equity_{timestamp}.png"
        self.plot_equity_curve(equity_data, benchmark_data, equity_path)

        # 2. 月度收益
        print("2. 生成月度收益热力图...")
        monthly_path = self.output_dir / f"chart_monthly_{timestamp}.png"
        self.plot_monthly_returns(equity_data, monthly_path)

        # 3. 交易分析
        if trades_file and Path(trades_file).exists():
            print("3. 生成交易分析图...")
            trades_data = pd.read_csv(trades_file, parse_dates=['timestamp'])
            trades_path = self.output_dir / f"chart_trades_{timestamp}.png"
            self.plot_trade_analysis(trades_data, trades_path)

        # 4. 性能指标
        if metrics:
            print("4. 生成性能指标图...")
            metrics_path = self.output_dir / f"chart_metrics_{timestamp}.png"
            self.plot_performance_metrics(metrics, metrics_path)

        print("\n" + "=" * 60)
        print("✅ 可视化报告生成完成！")
        print(f"📁 保存位置: {self.output_dir}/")
        print("=" * 60)


# 使用示例
if __name__ == "__main__":
    visualizer = BacktestVisualizer()

    # 查找最新的回测结果
    import glob

    equity_files = glob.glob("backtest_results/*equity*.csv")
    trades_files = glob.glob("backtest_results/*trades*.csv")

    if equity_files:
        latest_equity = max(equity_files, key=lambda x: Path(x).stat().st_mtime)

        latest_trades = None
        if trades_files:
            latest_trades = max(trades_files, key=lambda x: Path(x).stat().st_mtime)

        # 示例指标
        sample_metrics = {
            'total_return': 0.45,
            'annualized_return': 0.19,
            'max_drawdown': -0.12,
            'sharpe_ratio': 2.85,
            'volatility': 0.15,
            'total_trades': 234,
            'win_rate': 0.68,
            'profit_factor': 3.18,
            'final_equity': 145230
        }

        visualizer.generate_complete_report(
            equity_file=latest_equity,
            trades_file=latest_trades,
            metrics=sample_metrics
        )
    else:
        print("未找到回测结果文件")
        print("请先运行: python3 advanced_backtest.py")
