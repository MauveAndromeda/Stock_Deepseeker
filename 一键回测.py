#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock_Deepseeker 一键回测脚本 - 便携版
═══════════════════════════════════════════════════════════════════

🎯 设计理念：
   下载 → 解压 → 运行
   无需预配置，自动创建独立环境

✨ 功能特性：
   ✅ 自动创建虚拟环境（.venv/）
   ✅ 自动安装所有依赖
   ✅ 100% 功能覆盖
   ✅ 4种预设模式
   ✅ 完全独立运行

🚀 使用方法：
   python 一键回测.py --mode fast
   python 一键回测.py --mode turbo --years 2
   python 一键回测.py --help

═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import subprocess
import argparse
import time
import platform
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 颜色输出
# ═══════════════════════════════════════════════════════════════

class Colors:
    """跨平台颜色支持"""
    if platform.system() == "Windows":
        # Windows需要启用ANSI
        os.system("color")

    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    """打印成功信息"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_info(text):
    """打印信息"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text):
    """打印警告"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text):
    """打印错误"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

# ═══════════════════════════════════════════════════════════════
# 环境检查
# ═══════════════════════════════════════════════════════════════

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(f"需要Python 3.10+，当前版本: {version.major}.{version.minor}")
        print_info("请访问 https://www.python.org/downloads/ 下载最新版本")
        return False
    print_success(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

# ═══════════════════════════════════════════════════════════════
# 虚拟环境管理
# ═══════════════════════════════════════════════════════════════

def get_venv_path():
    """获取虚拟环境路径"""
    project_root = Path(__file__).parent
    return project_root / ".venv"

def get_venv_python():
    """获取虚拟环境中的Python路径"""
    venv_path = get_venv_path()
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"

def create_venv():
    """创建虚拟环境"""
    print_header("步骤 1/5: 创建虚拟环境")

    venv_path = get_venv_path()
    venv_python = get_venv_python()

    # 检查是否已存在
    if venv_python.exists():
        print_info("虚拟环境已存在，跳过创建")
        return True

    print_info(f"创建虚拟环境: {venv_path}")

    try:
        # 创建虚拟环境
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(venv_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        # 升级pip
        print_info("升级pip...")
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        print_success(f"虚拟环境创建成功: {venv_path}")
        return True

    except subprocess.CalledProcessError as e:
        print_error(f"虚拟环境创建失败: {e}")
        return False
    except Exception as e:
        print_error(f"发生错误: {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# 依赖安装
# ═══════════════════════════════════════════════════════════════

def install_dependencies(force=False):
    """安装所有依赖（分批安装，兼容Python 3.13）"""
    print_header("步骤 2/5: 安装依赖包")

    venv_python = get_venv_python()
    project_root = Path(__file__).parent

    # 检查是否已安装
    marker_file = get_venv_path() / ".deps_installed"
    if marker_file.exists() and not force:
        print_info("依赖已安装，跳过（使用 --force-install 强制重装）")
        return True

    # 检查Python版本，调整依赖
    py_version = sys.version_info
    is_py313_plus = (py_version.major == 3 and py_version.minor >= 13)

    if is_py313_plus:
        print_warning(f"检测到Python 3.13+，使用兼容性版本...")

    # 分批安装依赖，提高成功率
    dep_groups = {
        "基础数据科学": [
            "numpy>=1.26.0,<2.0",
            "pandas>=2.0.0,<2.3",
        ],
        "金融数据": [
            "yfinance>=0.2.28,<0.2.50",
            "pandas-market-calendars>=4.0.0",
        ],
        "AI/LLM核心": [
            "openai>=1.0.0",
            "anthropic>=0.18.0",
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
            "langchain-openai>=0.2.0",
        ],
        "AI/LLM扩展": [
            "langgraph>=0.2.0",
        ],
        "异步网络": [
            "aiohttp>=3.9.0",  # 降低版本，兼容性更好
            "nest-asyncio>=1.6.0",
            "httpx>=0.27.0",
        ],
        "工具库": [
            "loguru>=0.7.2",
            "pydantic>=2.0.0,<3.0",
            "python-dotenv>=1.0.0",
            "tqdm>=4.66.0",
            "rich>=13.0.0",
            "click>=8.0.0",
        ],
    }

    # 可选依赖（如果安装失败不影响核心功能）
    optional_deps = {
        "科学计算": [
            "scipy>=1.11.0" if is_py313_plus else "scipy>=1.14.0",
            "scikit-learn>=1.3.0" if is_py313_plus else "scikit-learn>=1.5.0",
        ],
        "机器学习": [
            "hmmlearn>=0.3.0",
        ],
    }

    print_info(f"准备分批安装依赖（共 {len(dep_groups)} 组必需包 + {len(optional_deps)} 组可选包）...")
    print_warning("首次安装可能需要5-10分钟，请耐心等待...")

    failed_packages = []
    installed_count = 0
    total_count = sum(len(deps) for deps in dep_groups.values())

    # 安装必需依赖
    for group_name, packages in dep_groups.items():
        print(f"\n{Colors.OKCYAN}▶ 安装{group_name}...{Colors.ENDC}")

        for pkg in packages:
            try:
                pkg_name = pkg.split(">=")[0].split("<")[0]
                print(f"  • {pkg_name}...", end=" ", flush=True)

                subprocess.check_call(
                    [str(venv_python), "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=180  # 3分钟超时
                )

                print(f"{Colors.OKGREEN}✓{Colors.ENDC}")
                installed_count += 1

            except subprocess.TimeoutExpired:
                print(f"{Colors.FAIL}✗ (超时){Colors.ENDC}")
                failed_packages.append((pkg, "超时"))
            except subprocess.CalledProcessError as e:
                print(f"{Colors.FAIL}✗{Colors.ENDC}")
                failed_packages.append((pkg, f"错误码{e.returncode}"))
            except Exception as e:
                print(f"{Colors.FAIL}✗ ({str(e)[:20]}){Colors.ENDC}")
                failed_packages.append((pkg, str(e)[:30]))

    # 安装可选依赖（失败不影响）
    print(f"\n{Colors.OKCYAN}▶ 安装可选依赖...{Colors.ENDC}")
    for group_name, packages in optional_deps.items():
        for pkg in packages:
            try:
                pkg_name = pkg.split(">=")[0].split("<")[0]
                print(f"  • {pkg_name}...", end=" ", flush=True)

                subprocess.check_call(
                    [str(venv_python), "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=180
                )

                print(f"{Colors.OKGREEN}✓{Colors.ENDC}")
                installed_count += 1

            except Exception:
                print(f"{Colors.WARNING}⊘ (跳过){Colors.ENDC}")

    # 安装本地项目
    print(f"\n{Colors.OKCYAN}▶ 安装本地项目...{Colors.ENDC}")
    try:
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "-e", str(project_root), "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60
        )
        print_success("✓ 项目安装完成")
    except Exception as e:
        print_warning(f"项目安装失败: {e}")
        print_info("这不影响回测功能，可以继续")

    # 显示安装总结
    print(f"\n{Colors.BOLD}安装总结:{Colors.ENDC}")
    print(f"  成功: {installed_count}/{total_count + len([p for g in optional_deps.values() for p in g])}")

    if failed_packages:
        print(f"  {Colors.WARNING}失败: {len(failed_packages)} 个包{Colors.ENDC}")
        if len(failed_packages) <= 5:
            for pkg, reason in failed_packages:
                print(f"    - {pkg}: {reason}")

        # 检查关键包是否安装
        critical_packages = ["numpy", "pandas", "yfinance", "openai"]
        missing_critical = []

        for critical_pkg in critical_packages:
            try:
                subprocess.check_call(
                    [str(venv_python), "-c", f"import {critical_pkg}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except:
                missing_critical.append(critical_pkg)

        if missing_critical:
            print_error(f"\n关键包缺失: {', '.join(missing_critical)}")
            print_info("\n解决方案:")
            print_info("  1. 升级pip: .venv\\Scripts\\python.exe -m pip install --upgrade pip")
            print_info("  2. 手动安装: .venv\\Scripts\\python.exe -m pip install numpy pandas yfinance openai")
            if is_py313_plus:
                print_info("  3. 或使用Python 3.11/3.12 (更好的兼容性)")
            return False
    else:
        print_success("  全部安装成功！")

    # 创建标记文件
    marker_file.write_text(
        f"Installed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Python {py_version.major}.{py_version.minor}.{py_version.micro}\n"
        f"Success: {installed_count}\n"
        f"Failed: {len(failed_packages)}\n"
    )

    print_success("\n依赖安装完成")
    return True

# ═══════════════════════════════════════════════════════════════
# API配置
# ═══════════════════════════════════════════════════════════════

def setup_api_keys():
    """配置API密钥"""
    print_header("步骤 3/5: 配置API密钥")

    # 加载.env文件
    env_file = Path(__file__).parent / ".env"

    if env_file.exists():
        print_info("加载 .env 文件...")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    # 检查OpenAI API
    api_key = os.getenv('OPENAI_API_KEY', '')

    if not api_key or not api_key.startswith('sk-'):
        print_warning("未找到OpenAI API密钥")
        print_info("\n请选择：")
        print("  1. 现在输入API密钥")
        print("  2. 跳过（后续手动配置）")

        choice = input("\n请选择 (1/2): ").strip()

        if choice == '1':
            api_key = input("\n请输入OpenAI API密钥: ").strip()
            if api_key:
                os.environ['OPENAI_API_KEY'] = api_key

                # 保存到.env
                with open(env_file, 'a') as f:
                    f.write(f"\nOPENAI_API_KEY={api_key}\n")

                print_success("API密钥已保存到 .env 文件")
            else:
                print_warning("未输入API密钥，跳过")
        else:
            print_info("跳过API配置")
            print_info("使用前请手动设置: export OPENAI_API_KEY=sk-xxx")
    else:
        print_success(f"使用API密钥: {api_key[:7]}...{api_key[-4:]}")

    return True

# ═══════════════════════════════════════════════════════════════
# 运行回测
# ═══════════════════════════════════════════════════════════════

def run_backtest(mode='fast', years=3, symbols=None, **kwargs):
    """运行回测"""
    print_header(f"步骤 4/5: 运行回测 ({mode.upper()} 模式)")

    venv_python = get_venv_python()
    script_path = Path(__file__).parent / "scripts" / "一键回测_超级增强版.py"

    # 检查脚本是否存在
    if not script_path.exists():
        print_error(f"回测脚本不存在: {script_path}")
        return False

    # 构建命令
    cmd = [
        str(venv_python),
        str(script_path),
        "--mode", mode,
        "--years", str(years),
        "--skip-install"  # 已经安装过依赖了
    ]

    if symbols:
        cmd.extend(["--symbols"] + symbols)

    print_info(f"执行命令: {' '.join(cmd)}")
    print_warning("回测开始，请勿关闭窗口...\n")

    try:
        # 运行回测（实时输出）
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )

        if result.returncode == 0:
            print_success("\n回测执行成功")
            return True
        else:
            print_error(f"\n回测执行失败，退出码: {result.returncode}")
            return False

    except KeyboardInterrupt:
        print_warning("\n用户中断")
        return False
    except Exception as e:
        print_error(f"\n回测执行失败: {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# 显示结果
# ═══════════════════════════════════════════════════════════════

def show_results():
    """显示结果位置"""
    print_header("步骤 5/5: 查看结果")

    report_dir = Path(__file__).parent / "backtest_reports"

    if report_dir.exists() and list(report_dir.glob("*.json")):
        reports = sorted(report_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        latest = reports[0]

        print_success(f"回测报告已生成: {latest.name}")
        print_info(f"报告目录: {report_dir}")
        print_info(f"共有 {len(reports)} 个历史报告")

        # 显示如何查看
        print(f"\n{Colors.OKCYAN}查看报告：{Colors.ENDC}")
        if platform.system() == "Windows":
            print(f"  type {latest}")
        else:
            print(f"  cat {latest}")
            print(f"  cat {latest} | jq  # 如果安装了jq")
    else:
        print_info("暂无回测报告")

    # 显示数据缓存
    cache_dir = Path(__file__).parent / "data_cache"
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.pkl"))
        if cache_files:
            print_info(f"数据缓存: {len(cache_files)} 个文件")

    return True

# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def main():
    """主函数"""

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='Stock_Deepseeker 一键回测 - 便携版',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python 一键回测.py                                    # 使用默认配置（fast模式，3年）
  python 一键回测.py --mode turbo --years 1            # 快速验证
  python 一键回测.py --mode fast --years 5             # 5年回测
  python 一键回测.py --mode balanced                   # 平衡模式
  python 一键回测.py --symbols AAPL MSFT GOOGL        # 自定义股票池

模式说明:
  turbo    - 极速模式 (3-5分钟，适合快速验证)
  fast     - 快速模式 (10-15分钟，推荐使用) ⭐
  balanced - 平衡模式 (30-60分钟，高准确性)
  full     - 完整模式 (2-4小时，最高准确性)

首次运行会自动:
  1. 创建虚拟环境 (.venv/)
  2. 安装所有依赖
  3. 配置API密钥
  4. 运行回测

后续运行会直接使用已有环境，速度更快。
        """
    )

    parser.add_argument(
        '--mode',
        choices=['turbo', 'fast', 'balanced', 'full'],
        default='fast',
        help='回测模式 (默认: fast)'
    )
    parser.add_argument(
        '--years',
        type=int,
        default=3,
        help='回测年数 (默认: 3)'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='自定义股票列表'
    )
    parser.add_argument(
        '--force-install',
        action='store_true',
        help='强制重新安装依赖'
    )
    parser.add_argument(
        '--skip-env',
        action='store_true',
        help='跳过环境创建（高级用户）'
    )

    args = parser.parse_args()

    # 显示欢迎信息
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                                                                   ║")
    print("║            Stock_Deepseeker 一键回测 - 便携版                     ║")
    print("║            下载 → 解压 → 运行 | 自动配置环境                      ║")
    print("║                                                                   ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    print_info(f"运行模式: {args.mode.upper()}")
    print_info(f"回测周期: {args.years}年")
    if args.symbols:
        print_info(f"股票池: {len(args.symbols)}只股票")

    start_time = time.time()

    try:
        # 步骤0: 检查Python版本
        if not check_python_version():
            return 1

        # 步骤1: 创建虚拟环境
        if not args.skip_env:
            if not create_venv():
                return 1
        else:
            print_info("跳过虚拟环境创建")

        # 步骤2: 安装依赖
        if not install_dependencies(force=args.force_install):
            return 1

        # 步骤3: 配置API
        if not setup_api_keys():
            return 1

        # 步骤4: 运行回测
        if not run_backtest(
            mode=args.mode,
            years=args.years,
            symbols=args.symbols
        ):
            return 1

        # 步骤5: 显示结果
        show_results()

        # 总结
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print(f"\n{Colors.OKGREEN}{Colors.BOLD}═══════════════════════════════════════════════════════════════════")
        print(f"                      ✓ 回测任务完成！")
        print(f"═══════════════════════════════════════════════════════════════════{Colors.ENDC}\n")
        print(f"总耗时: {minutes}分{seconds}秒")
        print(f"模式: {args.mode.upper()}")
        print(f"\n下次运行会更快（已有环境）！\n")

        return 0

    except KeyboardInterrupt:
        print_error("\n\n用户中断")
        return 130
    except Exception as e:
        print_error(f"\n\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
