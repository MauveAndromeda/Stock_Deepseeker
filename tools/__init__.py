"""
Stock Deepseeker 工具包
包含参数优化、结果可视化、策略比较等专业工具
"""

from pathlib import Path

__version__ = "1.0.0"
__author__ = "Stock Deepseeker Team"

# 工具目录
TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent

# 导出主要工具类
__all__ = [
    'ParameterOptimizer',
    'BacktestVisualizer',
    'StrategyComparator',
]

# 延迟导入以避免循环依赖
def get_optimizer():
    """获取参数优化器"""
    from .optimize_parameters import ParameterOptimizer
    return ParameterOptimizer

def get_visualizer():
    """获取可视化工具"""
    from .visualize_results import BacktestVisualizer
    return BacktestVisualizer

def get_comparator():
    """获取策略比较工具"""
    from .compare_strategies import StrategyComparator
    return StrategyComparator
