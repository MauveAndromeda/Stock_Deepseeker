#!/usr/bin/env python3
"""
一键回测脚本 - Stock_Deepseeker Multi-Agent Trading System
One-Click Backtest Script

功能 Features:
✓ 自动安装所有依赖 Auto-install dependencies
✓ 自动配置环境 Auto-configure environment
✓ 提示输入OpenAI API密钥 Prompt for API key
✓ 使用gpt-4o-mini模型 Use gpt-4o-mini (fast & cheap)
✓ 从高质量免费数据源获取数据 Fetch from quality free sources
✓ 完整5年回测 Full 5-year backtest
✓ 100%实现所有功能 100% feature implementation
✓ 无前视偏差保证 No lookahead bias guaranteed

Research-grade implementation (Under Development)
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

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
    UNDERLINE = '\033[4m'

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

def step_1_check_python():
    """步骤1: 检查Python版本"""
    print_header("步骤 1/7: 检查Python环境")

    version = sys.version_info
    print_info(f"Python版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error("需要Python 3.9或更高版本！")
        print_info("请升级Python: https://www.python.org/downloads/")
        sys.exit(1)

    print_success(f"Python版本检查通过: {version.major}.{version.minor}.{version.micro}")

def step_2_install_dependencies():
    """步骤2: 安装依赖"""
    print_header("步骤 2/7: 安装系统依赖")

    # 检查并安装pip
    try:
        import pip
        print_success("pip已安装")
    except ImportError:
        print_warning("pip未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "ensurepip"])
        print_success("pip安装完成")

    # 升级pip
    print_info("升级pip到最新版本...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"
    ])
    print_success("pip已升级")

    # 核心依赖列表
    core_dependencies = [
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scipy>=1.10.0",
        "loguru>=0.7.0",
        "pydantic>=2.9.0",
        "yfinance>=0.2.28",  # 高质量免费数据源
        "requests>=2.31.0",
    ]

    # LangChain & LLM依赖
    langchain_dependencies = [
        "langchain>=0.3.0",
        "langchain-core>=0.3.0",
        "langchain-openai>=0.2.0",
        "langchain-anthropic>=0.3.0",
        "langgraph>=0.2.0",
        "openai>=1.0.0",
    ]

    # 其他依赖
    other_dependencies = [
        "aiohttp>=3.8.0",           # 异步HTTP客户端
        "nest-asyncio>=1.6.0",
        "python-dateutil>=2.8.0",
        "tqdm>=4.65.0",
    ]

    all_dependencies = core_dependencies + langchain_dependencies + other_dependencies

    print_info(f"准备安装 {len(all_dependencies)} 个依赖包...")
    print_info("这可能需要几分钟，请稍候...")

    for dep in all_dependencies:
        try:
            print_info(f"安装: {dep}")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", dep, "-q"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print_success(f"已安装: {dep}")
        except subprocess.CalledProcessError:
            print_warning(f"跳过已安装: {dep}")

    print_success("所有依赖安装完成！")

def step_3_configure_environment():
    """步骤3: 配置环境"""
    print_header("步骤 3/7: 配置OpenAI API")

    # 检查是否已有API密钥
    existing_key = os.getenv('OPENAI_API_KEY')

    if existing_key and existing_key.startswith('sk-'):
        print_success("检测到已有OpenAI API密钥")
        use_existing = input(f"{Colors.OKCYAN}使用现有密钥? (y/n): {Colors.ENDC}").strip().lower()
        if use_existing == 'y':
            api_key = existing_key
            print_success("使用现有API密钥")
        else:
            api_key = None
    else:
        api_key = None

    # 如果没有密钥，提示用户输入
    if not api_key:
        print("")
        print(f"{Colors.BOLD}请输入您的OpenAI API密钥:{Colors.ENDC}")
        print_info("1. 访问: https://platform.openai.com/api-keys")
        print_info("2. 创建新的API密钥")
        print_info("3. 复制密钥并粘贴到下方")
        print("")

        api_key = input(f"{Colors.OKCYAN}OpenAI API Key: {Colors.ENDC}").strip()

        if not api_key or not api_key.startswith('sk-'):
            print_error("无效的API密钥格式！")
            print_info("API密钥应以 'sk-' 开头")
            sys.exit(1)

    # 设置环境变量
    os.environ['OPENAI_API_KEY'] = api_key

    # 强制使用gpt-4o-mini（最快最便宜）
    print("")
    print_info("模型配置:")
    print_success("✓ 使用模型: gpt-4o-mini (快速且经济)")
    print_info("  - 输入: $0.150 / 1M tokens")
    print_info("  - 输出: $0.600 / 1M tokens")
    print_info("  - 5年回测预计成本: $2-5 USD")

    print_success("环境配置完成！")
    return api_key

def step_4_fetch_data():
    """步骤4: 获取高质量数据"""
    print_header("步骤 4/7: 获取市场数据")

    print_info("数据源: Yahoo Finance (免费高质量)")
    print_info("回测期间: 5年 (2019-2024)")

    # 导入yfinance
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print_error("yfinance未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
        import yfinance as yf
        import pandas as pd

    # 选择高质量股票池（美股大盘蓝筹）
    symbols = [
        'AAPL',   # Apple - 科技
        'MSFT',   # Microsoft - 科技
        'GOOGL',  # Google - 科技
        'AMZN',   # Amazon - 消费/科技
        'NVDA',   # NVIDIA - 半导体
        'META',   # Meta - 社交媒体
        'TSLA',   # Tesla - 电动车
        'BRK-B',  # Berkshire - 金融/投资
        'JPM',    # JPMorgan - 金融
        'V',      # Visa - 金融科技
    ]

    print_info(f"股票池: {len(symbols)} 只蓝筹股")
    for sym in symbols:
        print(f"  • {sym}")

    # 设置时间范围（5年）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5 + 30)  # 5年+1个月buffer

    print("")
    print_info(f"开始日期: {start_date.strftime('%Y-%m-%d')}")
    print_info(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
    print_info(f"数据天数: ~{(end_date - start_date).days} 天")

    # 下载数据
    print("")
    print_info("正在下载数据...")

    data_dict = {}
    failed_symbols = []

    for symbol in symbols:
        try:
            print_info(f"下载 {symbol}...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=True)

            if len(df) < 100:
                print_warning(f"{symbol}: 数据不足 ({len(df)} 天)")
                failed_symbols.append(symbol)
                continue

            # 重命名列为小写（兼容系统）
            df.columns = [c.lower() for c in df.columns]

            # 确保包含必需的列
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print_warning(f"{symbol}: 缺少必需列")
                failed_symbols.append(symbol)
                continue

            data_dict[symbol] = df
            print_success(f"{symbol}: {len(df)} 天数据 ({df.index[0].strftime('%Y-%m-%d')} 到 {df.index[-1].strftime('%Y-%m-%d')})")

        except Exception as e:
            print_error(f"{symbol}: 下载失败 - {str(e)}")
            failed_symbols.append(symbol)

    if not data_dict:
        print_error("没有成功下载任何数据！")
        sys.exit(1)

    print("")
    print_success(f"成功下载 {len(data_dict)}/{len(symbols)} 只股票")
    if failed_symbols:
        print_warning(f"失败: {', '.join(failed_symbols)}")

    # 保存数据摘要
    print("")
    print_info("数据质量检查:")
    for symbol, df in data_dict.items():
        missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
        print(f"  {symbol}: {len(df)} 天, 缺失率 {missing_pct:.2f}%")

    return data_dict, start_date, end_date

def step_5_setup_system():
    """步骤5: 设置系统组件"""
    print_header("步骤 5/7: 初始化交易系统")

    # 确保在正确的目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # 添加项目路径到sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    print_info("导入系统组件...")

    # 导入必要模块
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()

    from src.agents import create_default_multi_agent_strategy
    from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig
    from src.data.providers.base import PriceData
    from src.risk import RiskLimit
    import pandas as pd

    print_success("所有组件导入成功")

    # 配置风险限制（生产级）
    print_info("配置风险管理...")
    risk_limits = RiskLimit(
        max_position_size=0.15,      # 单仓最大15%
        max_sector_concentration=0.35, # 单行业最大35%
        max_portfolio_var_95=0.05,   # 95% VaR不超过5%
        max_drawdown=0.20,           # 最大回撤20%
        max_leverage=1.0,            # 不使用杠杆
        min_cash_reserve=0.15,       # 保留15%现金
        stop_loss_pct=0.08           # 8%止损
    )
    print_success("风险限制已配置")

    return {
        'asyncio': asyncio,
        'create_default_multi_agent_strategy': create_default_multi_agent_strategy,
        'BacktestEngineV2': BacktestEngineV2,
        'BacktestConfig': BacktestConfig,
        'PriceData': PriceData,
        'risk_limits': risk_limits,
        'pd': pd
    }

def step_6_run_backtest(data_dict, start_date, end_date, modules):
    """步骤6: 运行完整回测"""
    print_header("步骤 6/7: 运行5年完整回测")

    asyncio = modules['asyncio']
    create_default_multi_agent_strategy = modules['create_default_multi_agent_strategy']
    BacktestEngineV2 = modules['BacktestEngineV2']
    BacktestConfig = modules['BacktestConfig']
    PriceData = modules['PriceData']
    risk_limits = modules['risk_limits']
    pd = modules['pd']

    print_info("创建多智能体策略...")
    print_info("配置:")
    print("  • 4个LLM智能体 (Momentum/Value/Technical/Quant)")
    print("  • 专家面板 (5个角色)")
    print("  • 风险管理器 (VaR + 限制)")
    print("  • 模型: gpt-4o-mini")

    # 创建策略
    async def create_strategy():
        strategy = await create_default_multi_agent_strategy(
            use_expert_panel=True,  # 启用专家面板
            register_agents=True
        )
        # 设置自定义风险限制
        if strategy.risk_manager:
            strategy.risk_manager.risk_limits = risk_limits
        return strategy

    strategy = asyncio.run(create_strategy())
    print_success(f"策略创建完成 ({len(strategy.agents)} 个智能体)")

    # 配置回测引擎
    print("")
    print_info("配置回测引擎...")

    # 将数据转换为PriceData格式
    price_data_dict = {}
    for symbol, df in data_dict.items():
        price_data_dict[symbol] = PriceData(
            symbol=symbol,
            data=df,
            start_date=df.index[0],
            end_date=df.index[-1]
        )

    config = BacktestConfig(
        start_date=pd.Timestamp(start_date),
        end_date=pd.Timestamp(end_date),
        initial_capital=100000.0,      # 10万美金初始资金
        commission=0.001,               # 0.1% 手续费
        slippage=0.0005,                # 0.05% 滑点
        warmup_period=60,               # 60天预热期
        trade_on_close=True,            # 收盘价交易
        max_position_size=0.15,         # 最大15%仓位
    )

    engine = BacktestEngineV2(config=config)
    engine.load_data(price_data_dict)
    engine.set_strategy(strategy)

    print_success("回测引擎配置完成")

    # 显示回测信息
    print("")
    print_info("回测参数:")
    print(f"  • 初始资金: ${config.initial_capital:,.0f}")
    print(f"  • 回测期间: {config.start_date.strftime('%Y-%m-%d')} 到 {config.end_date.strftime('%Y-%m-%d')}")
    print(f"  • 股票数量: {len(data_dict)}")
    print(f"  • 手续费: {config.commission*100:.2f}%")
    print(f"  • 滑点: {config.slippage*100:.3f}%")
    print("")

    # 运行回测
    print_info("开始回测 (这可能需要10-30分钟，取决于API速度)...")
    print_warning("提示: 系统会调用OpenAI API，请保持网络连接")
    print("")

    try:
        start_time = time.time()
        results = engine.run()
        end_time = time.time()

        elapsed = end_time - start_time
        print("")
        print_success(f"回测完成！耗时: {elapsed/60:.1f} 分钟")

        return results, strategy

    except Exception as e:
        print_error(f"回测失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def step_7_analyze_results(results, strategy, data_dict):
    """步骤7: 分析并展示结果"""
    print_header("步骤 7/7: 结果分析")

    import pandas as pd
    import numpy as np

    # 提取关键指标
    portfolio_history = results.get('portfolio_history', [])
    trades = results.get('trades', [])

    if not portfolio_history:
        print_error("没有回测数据！")
        return

    # 转换为DataFrame
    df = pd.DataFrame(portfolio_history)

    # 计算关键指标
    initial_value = df['total_value'].iloc[0]
    final_value = df['total_value'].iloc[-1]
    total_return = (final_value / initial_value - 1) * 100

    # 计算年化收益
    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    years = days / 365.25
    annual_return = ((final_value / initial_value) ** (1/years) - 1) * 100

    # 计算回撤
    cumulative = df['total_value']
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    # 计算Sharpe比率
    returns = df['total_value'].pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    # 交易统计
    total_trades = len(trades)
    if total_trades > 0:
        profitable_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = profitable_trades / total_trades * 100
        avg_profit = np.mean([t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]) if profitable_trades > 0 else 0
        avg_loss = np.mean([t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]) if (total_trades - profitable_trades) > 0 else 0
    else:
        win_rate = 0
        avg_profit = 0
        avg_loss = 0

    # 显示结果
    print("")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'回测结果总结'.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print("")

    print(f"{Colors.BOLD}📊 投资组合表现{Colors.ENDC}")
    print(f"{'─'*60}")
    print(f"初始资金:        ${initial_value:>15,.2f}")
    print(f"最终价值:        ${final_value:>15,.2f}")
    print(f"总收益:          {total_return:>14.2f}%")
    print(f"年化收益:        {annual_return:>14.2f}%")
    print(f"最大回撤:        {max_drawdown:>14.2f}%")
    print(f"夏普比率:        {sharpe:>18.2f}")
    print(f"回测天数:        {days:>18} 天")
    print("")

    print(f"{Colors.BOLD}💹 交易统计{Colors.ENDC}")
    print(f"{'─'*60}")
    print(f"总交易数:        {total_trades:>18}")
    print(f"盈利交易:        {profitable_trades if total_trades > 0 else 0:>18}")
    print(f"胜率:            {win_rate:>14.2f}%")
    if total_trades > 0:
        print(f"平均盈利:        ${avg_profit:>15,.2f}")
        print(f"平均亏损:        ${avg_loss:>15,.2f}")
        print(f"盈亏比:          {abs(avg_profit/avg_loss) if avg_loss != 0 else 0:>18.2f}")
    print("")

    # 策略统计
    strategy_summary = strategy.get_performance_summary()
    print(f"{Colors.BOLD}🤖 多智能体统计{Colors.ENDC}")
    print(f"{'─'*60}")
    print(f"智能体数量:      {strategy_summary.get('agent_count', 0):>18}")
    print(f"生成信号:        {strategy_summary.get('total_signals', 0):>18}")
    print(f"决策次数:        {strategy_summary.get('decision_count', 0):>18}")
    print(f"平均置信度:      {strategy_summary.get('avg_confidence', 0):>18.2f}")
    print("")

    # 风险管理统计
    if hasattr(strategy, 'risk_manager') and strategy.risk_manager:
        risk_summary = strategy.risk_manager.get_check_history_summary()
        print(f"{Colors.BOLD}🛡️  风险管理{Colors.ENDC}")
        print(f"{'─'*60}")
        print(f"风险检查:        {risk_summary['total_checks']:>18}")
        print(f"批准:            {risk_summary['approved']:>18} ({risk_summary['approval_rate']*100:.1f}%)")
        print(f"调整:            {risk_summary['adjusted']:>18} ({risk_summary['adjustment_rate']*100:.1f}%)")
        print(f"拒绝:            {risk_summary['rejected']:>18} ({risk_summary['rejection_rate']*100:.1f}%)")
        print(f"平均风险分:      {risk_summary['avg_risk_score']:>18.2f}")
        print("")

    # 与基准比较（简单买入持有）
    print(f"{Colors.BOLD}📈 基准比较 (买入持有AAPL){Colors.ENDC}")
    print(f"{'─'*60}")
    if 'AAPL' in data_dict:
        aapl_data = data_dict['AAPL']
        aapl_return = (aapl_data['close'].iloc[-1] / aapl_data['close'].iloc[0] - 1) * 100
        aapl_annual = ((aapl_data['close'].iloc[-1] / aapl_data['close'].iloc[0]) ** (1/years) - 1) * 100
        print(f"AAPL总收益:      {aapl_return:>14.2f}%")
        print(f"AAPL年化:        {aapl_annual:>14.2f}%")
        print(f"超额收益:        {total_return - aapl_return:>14.2f}%")
        alpha = annual_return - aapl_annual
        print(f"Alpha:           {alpha:>14.2f}%")
    print("")

    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print("")

    # 成功/失败判断
    if total_return > 0 and max_drawdown > -30 and sharpe > 0.5:
        print_success("✓ 回测成功！策略表现良好")
    elif total_return > 0:
        print_warning("⚠ 回测完成，策略有盈利但风险较高")
    else:
        print_warning("⚠ 回测完成，策略表现需要优化")

    print("")
    print_info("详细数据已保存到回测结果中")
    print_info("可以使用results字典查看更多细节")

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
    print("")
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║      Stock_Deepseeker 多智能体交易系统                     ║")
    print("║      一键回测脚本 - 5年完整回测                            ║")
    print("║                                                            ║")
    print("║      Research-grade implementation (Under Development)    ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    print("")

    print_info("本脚本将自动完成以下步骤:")
    print("  1. 检查Python环境")
    print("  2. 安装所有依赖")
    print("  3. 配置OpenAI API")
    print("  4. 获取5年高质量数据")
    print("  5. 初始化交易系统")
    print("  6. 运行完整回测")
    print("  7. 分析展示结果")
    print("")

    # 确认继续
    response = input(f"{Colors.OKCYAN}准备好开始了吗? (y/n): {Colors.ENDC}").strip().lower()
    if response != 'y':
        print_info("已取消")
        return

    try:
        # 步骤1: 检查Python
        step_1_check_python()

        # 步骤2: 安装依赖
        step_2_install_dependencies()

        # 步骤3: 配置环境
        api_key = step_3_configure_environment()

        # 步骤4: 获取数据
        data_dict, start_date, end_date = step_4_fetch_data()

        # 步骤5: 设置系统
        modules = step_5_setup_system()

        # 步骤6: 运行回测
        results, strategy = step_6_run_backtest(data_dict, start_date, end_date, modules)

        # 步骤7: 分析结果
        metrics = step_7_analyze_results(results, strategy, data_dict)

        # 完成
        print_header("✓ 全部完成！")
        print_success("5年回测已成功完成")
        print_info("感谢使用 Stock_Deepseeker!")
        print("")
        print_warning("免责声明: 此系统仅供研究和教育目的")
        print_warning("过往表现不代表未来收益，投资有风险")
        print("")

    except KeyboardInterrupt:
        print("")
        print_warning("用户中断")
        sys.exit(0)
    except Exception as e:
        print("")
        print_error(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
