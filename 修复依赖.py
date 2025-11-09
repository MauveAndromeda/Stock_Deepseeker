#!/usr/bin/env python3
"""
快速修复脚本 - 解决yfinance和charset-normalizer问题
运行此脚本修复当前虚拟环境中的依赖问题
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("🔧 Stock_Deepseeker 依赖修复工具\n")
    print("=" * 60)

    # 确定Python路径
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        python_exe = sys.executable
        print(f"✓ 检测到虚拟环境: {python_exe}\n")
    else:
        venv_path = Path(__file__).parent / ".venv"
        if sys.platform == "win32":
            python_exe = str(venv_path / "Scripts" / "python.exe")
        else:
            python_exe = str(venv_path / "bin" / "python")

        if not Path(python_exe).exists():
            print("✗ 未找到虚拟环境，请先运行: python 一键回测.py")
            return 1

        print(f"✓ 使用虚拟环境: {python_exe}\n")

    print("步骤 1/3: 升级pip")
    print("-" * 60)
    try:
        subprocess.check_call(
            [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL
        )
        print("✓ pip已升级\n")
    except:
        print("⚠ pip升级失败，继续...\n")

    print("步骤 2/3: 安装/修复关键依赖")
    print("-" * 60)

    critical_packages = [
        "charset-normalizer>=3.0.0",
        "lxml>=4.9.0",
        "requests>=2.31.0",
        "yfinance>=0.2.40",
    ]

    for pkg in critical_packages:
        pkg_name = pkg.split(">=")[0]
        print(f"  • {pkg_name}...", end=" ", flush=True)
        try:
            # 强制重新安装
            subprocess.check_call(
                [python_exe, "-m", "pip", "install", "--force-reinstall", "--no-deps", pkg, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")

    print("\n步骤 3/3: 验证安装")
    print("-" * 60)

    # 验证导入
    test_imports = [
        ("charset_normalizer", "charset-normalizer"),
        ("lxml", "lxml"),
        ("requests", "requests"),
        ("yfinance", "yfinance"),
    ]

    all_ok = True
    for module_name, package_name in test_imports:
        try:
            subprocess.check_call(
                [python_exe, "-c", f"import {module_name}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"  ✓ {package_name} 可用")
        except:
            print(f"  ✗ {package_name} 导入失败")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✓ 所有依赖已修复！")
        print("\n现在可以运行回测：")
        print("  python 一键回测.py")
        print("  或")
        print("  python scripts/一键回测_超级增强版.py --mode fast --skip-install")
        return 0
    else:
        print("⚠ 部分依赖仍有问题，请手动安装：")
        print(f"  {python_exe} -m pip install " + " ".join(critical_packages))
        return 1

if __name__ == "__main__":
    sys.exit(main())
