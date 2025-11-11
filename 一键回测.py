#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stock_Deepseeker 一键回测入口.

该脚本保持向后兼容, 但内部直接复用便携版实现, 从而共用最新的
依赖管理与数据回退逻辑。"""

from __future__ import annotations

import sys

import importlib


def main() -> int:
    """委托执行便携版一键回测脚本."""
    portable_module = importlib.import_module("一键回测_portable")
    return portable_module.main()


if __name__ == "__main__":
    sys.exit(main())
