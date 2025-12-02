#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock_Deepseeker - 增强版一键回测脚本
═══════════════════════════════════════════════════════════════

🎯 设计理念: 下载ZIP → 解压 → 直接运行

✨ 核心特性:
  ✅ 零配置启动 - 自动环境设置
  ✅ 智能依赖管理 - 自动安装所需包
  ✅ 多重数据源 - Yahoo → Stooq → 合成数据
  ✅ 灵活策略选择 - 简单SMA或AI增强
  ✅ 完整性能报告 - JSON格式导出
  ✅ 跨平台支持 - Windows/Linux/Mac
  ✅ 详细进度显示 - 实时反馈

📊 回测模式:
  • turbo    - 极速模式 (1年数据, 3-5分钟)
  • fast     - 快速模式 (3年数据, 10-15分钟) [推荐]
  • balanced - 平衡模式 (5年数据, 30-60分钟)
  • full     - 完整模式 (10年数据, 2-4小时)

💡 使用示例:
  python 一键回测_增强版.py                                # 默认配置
  python 一键回测_增强版.py --mode turbo --years 1        # 快速测试
  python 一键回测_增强版.py --symbols AAPL MSFT GOOGL    # 自定义股票
  python 一键回测_增强版.py --ai                          # 启用AI功能
  python 一键回测_增强版.py --list-symbols                # 查看推荐股票

📁 输出目录:
  • backtest_reports/  - 回测报告
  • data_cache/        - 数据缓存
  • .venv/            - Python虚拟环境

═══════════════════════════════════════════════════════════════
"""

import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

# ═══════════════════════════════════════════════════════════════
# 配置和常量
# ═══════════════════════════════════════════════════════════════

VERSION = "3.0.0"
MIN_PYTHON_VERSION = (3, 10)
RECOMMENDED_PYTHON_VERSION = (3, 11)

# 推荐的股票池
STOCK_POOLS = {
    "tech": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMZN", "NFLX"],
    "finance": ["JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "AXP"],
    "healthcare": ["UNH", "JNJ", "PFE", "ABBV", "TMO", "LLY", "MRK", "ABT"],
    "consumer": ["WMT", "HD", "NKE", "SBUX", "MCD", "TGT", "COST", "LOW"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO", "MPC"],
    "diverse": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "JPM", "V", "UNH", "JNJ"],
}

# 回测模式配置
BACKTEST_MODES = {
    "turbo": {
        "years": 1,
        "description": "极速模式 - 1年数据，快速验证",
        "time_estimate": "3-5分钟",
    },
    "fast": {
        "years": 3,
        "description": "快速模式 - 3年数据，日常开发",
        "time_estimate": "10-15分钟",
    },
    "balanced": {
        "years": 5,
        "description": "平衡模式 - 5年数据，正式评估",
        "time_estimate": "30-60分钟",
    },
    "full": {
        "years": 10,
        "description": "完整模式 - 10年数据，学术研究",
        "time_estimate": "2-4小时",
    },
}

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def print_header():
    """打印脚本头部"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + f"Stock_Deepseeker v{VERSION} - 增强版一键回测".center(68) + "║")
    print("║" + "下载ZIP → 解压 → 运行 | 跨平台支持".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "─" * 70)
    print(f"▶ {title}")
    print("─" * 70)


def print_info(message: str, indent: int = 0):
    """打印信息"""
    prefix = "  " * indent
    print(f"{prefix}ℹ {message}")


def print_success(message: str, indent: int = 0):
    """打印成功消息"""
    prefix = "  " * indent
    print(f"{prefix}✓ {message}")


def print_warning(message: str, indent: int = 0):
    """打印警告"""
    prefix = "  " * indent
    print(f"{prefix}⚠ {message}")


def print_error(message: str, indent: int = 0):
    """打印错误"""
    prefix = "  " * indent
    print(f"{prefix}✗ {message}")


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "architecture": platform.machine(),
    }


# ═══════════════════════════════════════════════════════════════
# 环境设置
# ═══════════════════════════════════════════════════════════════

# 确保 Windows 下的 UTF-8 编码
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()


def check_python_version() -> bool:
    """检查Python版本"""
    current_version = sys.version_info[:2]

    if current_version < MIN_PYTHON_VERSION:
        print_error(f"Python版本过低: {sys.version.split()[0]}")
        print_error(f"最低要求: Python {'.'.join(map(str, MIN_PYTHON_VERSION))}")
        return False

    if current_version < RECOMMENDED_PYTHON_VERSION:
        print_warning(f"当前Python版本: {sys.version.split()[0]}")
        print_warning(f"推荐版本: Python {'.'.join(map(str, RECOMMENDED_PYTHON_VERSION))}+")
    else:
        print_success(f"Python版本: {sys.version.split()[0]}")

    return True


def check_disk_space(min_space_mb: int = 500) -> bool:
    """检查磁盘空间"""
    try:
        import shutil
        stat = shutil.disk_usage(PROJECT_ROOT)
        free_mb = stat.free / (1024 * 1024)

        if free_mb < min_space_mb:
            print_warning(f"磁盘剩余空间较少: {free_mb:.0f} MB")
            print_info(f"建议至少有 {min_space_mb} MB 空闲空间")
            return False
        else:
            print_success(f"磁盘空间充足: {free_mb:.0f} MB 可用")
            return True
    except Exception as e:
        print_warning(f"无法检查磁盘空间: {e}")
        return True  # 不阻止运行


def check_path_issues() -> None:
    """检查路径问题"""
    path_str = str(PROJECT_ROOT)

    issues = []

    if len(path_str) > 200:
        issues.append(f"路径过长 ({len(path_str)} 字符)")
        print_warning("路径过长可能在Windows上造成问题，建议移到更短的路径")

    if "(" in path_str or ")" in path_str:
        issues.append("路径包含括号")
        print_warning("路径中的括号可能造成问题，建议重命名文件夹")

    if not issues:
        print_success("路径检查通过")


def check_network() -> bool:
    """简单检查网络连接"""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        print_success("网络连接正常")
        return True
    except OSError:
        print_warning("网络连接失败 - 将使用合成数据")
        return False


# ═══════════════════════════════════════════════════════════════
# 虚拟环境管理
# ═══════════════════════════════════════════════════════════════

def get_venv_path() -> Path:
    """获取虚拟环境路径"""
    return PROJECT_ROOT / ".venv"


def get_venv_python() -> Path:
    """获取虚拟环境中的Python可执行文件"""
    venv_path = get_venv_path()
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"


def create_venv() -> bool:
    """创建虚拟环境"""
    venv_python = get_venv_python()

    if venv_python.exists():
        print_success("虚拟环境已存在")
        return True

    print_info("正在创建虚拟环境...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(get_venv_path())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 升级pip
        print_info("正在升级pip...")
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print_success("虚拟环境创建成功")
        return True

    except Exception as e:
        print_error(f"创建虚拟环境失败: {e}")
        return False


def install_dependencies(enable_ai: bool = False, force: bool = False) -> bool:
    """
    安装运行时依赖

    Args:
        enable_ai: 是否启用AI功能
        force: 是否强制重新安装

    Returns:
        是否成功
    """
    venv_python = get_venv_python()

    base_marker = get_venv_path() / ".deps_installed"
    data_marker = get_venv_path() / ".deps_data_installed"
    ai_marker = get_venv_path() / ".deps_ai_installed"

    # 快速检查是否已安装
    if not force:
        base_ok = base_marker.exists()
        data_ok = data_marker.exists() or not (PROJECT_ROOT / "requirements-data.txt").exists()
        ai_ok = (not enable_ai) or ai_marker.exists()

        if base_ok and data_ok and ai_ok:
            print_success("依赖已安装 (使用 --force-install 强制重装)")
            return True

    def _install_requirements(
        req_file: str,
        marker: Path,
        optional: bool = False,
        timeout: Optional[int] = None,
        max_retries: int = 3
    ) -> bool:
        """安装依赖文件，支持重试"""
        req_path = PROJECT_ROOT / req_file
        if not req_path.exists():
            return True

        print_info(f"正在安装 {req_file}...")

        for attempt in range(max_retries):
            try:
                args = [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    req_file,
                    "-q",
                ]

                subprocess.check_call(
                    args,
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout,
                )

                marker.write_text(f"Installed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print_success(f"成功安装 {req_file}", indent=1)
                return True

            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    print_warning(f"安装超时，正在重试 ({attempt + 1}/{max_retries})...", indent=1)
                    time.sleep(2)
                else:
                    if optional:
                        print_warning(f"安装 {req_file} 超时 - 继续使用基础功能", indent=1)
                        return False
                    print_error(f"安装 {req_file} 超时", indent=1)
                    return False

            except subprocess.CalledProcessError as exc:
                if attempt < max_retries - 1:
                    print_warning(f"安装失败，正在重试 ({attempt + 1}/{max_retries})...", indent=1)
                    time.sleep(2)
                else:
                    if optional:
                        print_warning(f"可选依赖 {req_file} 安装失败 (退出码 {exc.returncode})", indent=1)
                        print_info("将使用合成数据作为后备", indent=2)
                        return False
                    print_error(f"安装 {req_file} 失败: 退出码 {exc.returncode}", indent=1)
                    print_info(f"手动安装: {venv_python} -m pip install -r {req_file}", indent=2)
                    return False

            except Exception as err:
                if attempt < max_retries - 1:
                    print_warning(f"安装出错，正在重试 ({attempt + 1}/{max_retries})...", indent=1)
                    time.sleep(2)
                else:
                    if optional:
                        print_warning(f"可选依赖 {req_file} 无法安装: {err}", indent=1)
                        return False
                    print_error(f"安装 {req_file} 失败: {err}", indent=1)
                    return False

        return False

    # 安装基础依赖
    print_info("安装基础依赖...")
    if not _install_requirements("requirements-min.txt", base_marker):
        return False

    # 安装数据源依赖
    print_info("安装数据源依赖...")
    _install_requirements("requirements-data.txt", data_marker, optional=True)

    # 安装AI依赖
    if enable_ai:
        print_info("安装AI依赖...")
        success = _install_requirements("requirements-ai.txt", ai_marker, optional=True, timeout=600)
        if not success:
            print_info("继续使用基础回测功能", indent=1)

    return True


# ═══════════════════════════════════════════════════════════════
# 回测运行
# ═══════════════════════════════════════════════════════════════

def run_backtest(
    mode: str,
    years: int,
    symbols: Optional[List[str]],
    enable_ai: bool,
    capital: float
) -> bool:
    """
    运行回测

    Args:
        mode: 回测模式
        years: 年数
        symbols: 股票代码列表
        enable_ai: 启用AI
        capital: 初始资金

    Returns:
        是否成功
    """
    venv_python = get_venv_python()

    print_section("运行回测")

    # 设置环境变量
    env = os.environ.copy()
    env["ENABLE_AI"] = "1" if enable_ai else "0"

    # 显示配置
    print_info(f"回测模式: {mode}")
    print_info(f"数据年限: {years}年")
    print_info(f"初始资金: ${capital:,.2f}")
    if symbols:
        print_info(f"股票代码: {', '.join(symbols)}")
    if enable_ai:
        print_success("AI模式已启用")
    else:
        print_info("使用简单SMA策略 (添加 --ai 启用AI功能)")
    print()

    # 默认股票池
    if symbols is None:
        symbols = STOCK_POOLS["diverse"]

    # 生成回测代码
    import_code = """
import sys
sys.path.insert(0, '{root}')

from portable_runner import download_market_data, SimpleMovingAverageStrategy, generate_report, calculate_metrics, print_summary

# 下载数据
symbols = {symbols}
print("\\n正在下载市场数据...")
print("=" * 70)
data = download_market_data(symbols, years={years}, verbose=True)

# 运行策略
print("\\n正在运行回测策略...")
print("=" * 70)
strategy = SimpleMovingAverageStrategy(initial_capital={capital})
results = strategy.run_backtest(data, verbose=True)

# 计算指标
metrics = calculate_metrics(results)

# 生成报告
report_path = generate_report(results, metrics)
print(f"\\n✓ 报告已保存: {{report_path}}")

# 打印摘要
print()
print_summary(metrics, symbols)
""".format(
        root=PROJECT_ROOT,
        symbols=symbols,
        years=years,
        capital=capital,
    )

    try:
        result = subprocess.run(
            [str(venv_python), "-c", import_code],
            cwd=PROJECT_ROOT,
            env=env,
        )

        if result.returncode == 0:
            print_success("回测完成")
            return True
        else:
            print_error(f"回测失败 (退出码 {result.returncode})")
            return False

    except Exception as e:
        print_error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def list_symbols():
    """列出推荐的股票池"""
    print_section("推荐股票池")
    for category, symbols in STOCK_POOLS.items():
        print(f"\n{category.upper()}:")
        print(f"  {', '.join(symbols)}")
    print()


def main():
    """主函数"""
    # 解析参数
    parser = argparse.ArgumentParser(
        description="Stock_Deepseeker 增强版一键回测 - 下载ZIP → 解压 → 运行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
回测模式:
{chr(10).join(f"  {mode:8} - {config['description']} (预计 {config['time_estimate']})" for mode, config in BACKTEST_MODES.items())}

股票池:
{chr(10).join(f"  {category:10} - {', '.join(symbols[:5])}..." for category, symbols in list(STOCK_POOLS.items())[:3])}

使用示例:
  {sys.argv[0]}                                    # 默认配置
  {sys.argv[0]} --mode turbo                      # 极速模式
  {sys.argv[0]} --symbols AAPL MSFT GOOGL         # 自定义股票
  {sys.argv[0]} --pool tech                       # 使用科技股池
  {sys.argv[0]} --ai                              # 启用AI功能
  {sys.argv[0]} --list-symbols                    # 查看所有股票池

输出目录:
  backtest_reports/  - 回测报告 (JSON格式)
  data_cache/        - 数据缓存 (加速后续运行)
  .venv/            - Python虚拟环境

注意事项:
  - 首次运行需要创建虚拟环境和安装依赖 (2-5分钟)
  - 数据将被缓存，后续运行更快
  - 使用 --ai 需要配置 OpenAI API Key
        """
    )

    parser.add_argument(
        "--mode",
        choices=list(BACKTEST_MODES.keys()),
        default="fast",
        help="回测模式 (默认: fast)",
    )

    parser.add_argument(
        "--years",
        type=int,
        default=None,
        help="历史数据年数 (默认: 根据模式自动设置)",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="股票代码列表 (例: AAPL MSFT GOOGL)",
    )

    parser.add_argument(
        "--pool",
        choices=list(STOCK_POOLS.keys()),
        help="使用预定义股票池",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="初始资金 (默认: 100000)",
    )

    parser.add_argument(
        "--ai",
        action="store_true",
        help="启用AI功能 (需要额外配置)",
    )

    parser.add_argument(
        "--force-install",
        action="store_true",
        help="强制重新安装依赖",
    )

    parser.add_argument(
        "--list-symbols",
        action="store_true",
        help="列出所有推荐股票池",
    )

    parser.add_argument(
        "--no-checks",
        action="store_true",
        help="跳过系统检查 (不推荐)",
    )

    args = parser.parse_args()

    # 列出股票池
    if args.list_symbols:
        print_header()
        list_symbols()
        return 0

    # 打印头部
    print_header()

    # 记录开始时间
    start_time = time.time()

    try:
        # ═══════════════════════════════════════════════════════════
        # 步骤1: 系统检查
        # ═══════════════════════════════════════════════════════════
        print_section("步骤 1/4: 系统检查")

        # 显示系统信息
        sys_info = get_system_info()
        print_info(f"操作系统: {sys_info['platform']} {sys_info['architecture']}")
        print_info(f"Python: {sys_info['python_version']} ({sys_info['python_implementation']})")
        print()

        if not args.no_checks:
            # Python版本检查
            if not check_python_version():
                return 1

            # 路径检查
            check_path_issues()

            # 磁盘空间检查
            check_disk_space()

            # 网络检查
            check_network()
        else:
            print_warning("已跳过系统检查")

        # ═══════════════════════════════════════════════════════════
        # 步骤2: 虚拟环境
        # ═══════════════════════════════════════════════════════════
        print_section("步骤 2/4: 虚拟环境")
        if not create_venv():
            return 1

        # ═══════════════════════════════════════════════════════════
        # 步骤3: 安装依赖
        # ═══════════════════════════════════════════════════════════
        print_section("步骤 3/4: 依赖管理")
        if not install_dependencies(enable_ai=args.ai, force=args.force_install):
            return 1

        # ═══════════════════════════════════════════════════════════
        # 步骤4: 运行回测
        # ═══════════════════════════════════════════════════════════

        # 确定参数
        mode = args.mode
        years = args.years if args.years is not None else BACKTEST_MODES[mode]["years"]
        symbols = args.symbols

        # 使用股票池
        if args.pool:
            if symbols:
                print_warning("--pool 和 --symbols 同时指定，将使用 --symbols")
            else:
                symbols = STOCK_POOLS[args.pool]
                print_info(f"使用股票池: {args.pool}")

        # 运行回测
        if not run_backtest(mode, years, symbols, args.ai, args.capital):
            return 1

        # ═══════════════════════════════════════════════════════════
        # 完成总结
        # ═══════════════════════════════════════════════════════════
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print_section("完成")
        print_success(f"总耗时: {minutes}分{seconds}秒")
        print_success(f"报告目录: backtest_reports/")
        print_success(f"缓存目录: data_cache/")
        print()

        print("📊 下一步:")
        print("  • 查看报告: cat backtest_reports/report_*.json")
        print("  • 尝试其他模式: --mode turbo/balanced/full")
        print("  • 自定义股票: --symbols AAPL MSFT GOOGL")
        print("  • 使用股票池: --pool tech/finance/healthcare")
        print("  • 启用AI功能: --ai (需要配置API密钥)")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n")
        print_warning("用户中断")
        return 130

    except Exception as e:
        print("\n")
        print_error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
