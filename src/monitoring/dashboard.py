"""
监控Dashboard
"""

from typing import Any

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go


class Dashboard:
    """监控Dashboard"""

    def __init__(self, trading_system: Any):
        self.trading_system = trading_system
        self.app = dash.Dash(__name__, suppress_callback_exceptions=True)
        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self):
        """设置布局"""
        self.app.layout = html.Div([
            html.H1("Stock Deepseeker - Real-time Dashboard"),

            # 刷新间隔
            dcc.Interval(
                id="interval-component",
                interval=5*1000,  # 5秒
                n_intervals=0
            ),

            # 概览指标
            html.Div([
                html.Div([
                    html.H3("Portfolio Value"),
                    html.H2(id="portfolio-value", children="$0")
                ], className="metric-card"),

                html.Div([
                    html.H3("Daily P&L"),
                    html.H2(id="daily-pnl", children="$0")
                ], className="metric-card"),

                html.Div([
                    html.H3("Total Return"),
                    html.H2(id="total-return", children="0%")
                ], className="metric-card"),

                html.Div([
                    html.H3("Sharpe Ratio"),
                    html.H2(id="sharpe-ratio", children="0.00")
                ], className="metric-card"),
            ], className="metrics-container"),

            # 权益曲线
            html.Div([
                html.H2("Equity Curve"),
                dcc.Graph(id="equity-curve")
            ]),

            # 持仓分布
            html.Div([
                html.Div([
                    html.H2("Positions"),
                    dcc.Graph(id="positions-chart")
                ], style={"width": "50%", "display": "inline-block"}),

                html.Div([
                    html.H2("Sector Allocation"),
                    dcc.Graph(id="sector-chart")
                ], style={"width": "50%", "display": "inline-block"}),
            ]),

            # 最近订单
            html.Div([
                html.H2("Recent Orders"),
                html.Div(id="recent-orders")
            ]),

            # 风险指标
            html.Div([
                html.H2("Risk Metrics"),
                html.Div(id="risk-metrics")
            ]),
        ])

    def _setup_callbacks(self):
        """设置回调"""

        @self.app.callback(
            [Output("portfolio-value", "children"),
             Output("daily-pnl", "children"),
             Output("total-return", "children"),
             Output("sharpe-ratio", "children")],
            [Input("interval-component", "n_intervals")]
        )
        def update_metrics(n):
            """更新指标"""
            # TODO: 从trading_system获取实际数据
            return (
                "$1,000,000",
                "+$5,000",
                "+5.0%",
                "2.1"
            )

        @self.app.callback(
            Output("equity-curve", "figure"),
            [Input("interval-component", "n_intervals")]
        )
        def update_equity_curve(n):
            """更新权益曲线"""
            # 示例数据
            dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
            values = [1000000 + i * 1000 for i in range(100)]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode="lines",
                name="Equity",
                line=dict(color="#2E86AB", width=2)
            ))

            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Portfolio Value ($)",
                hovermode="x unified",
                template="plotly_white"
            )

            return fig

        @self.app.callback(
            Output("positions-chart", "figure"),
            [Input("interval-component", "n_intervals")]
        )
        def update_positions(n):
            """更新持仓图表"""
            # 示例数据
            symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
            values = [100000, 80000, 75000, 60000, 50000]

            fig = go.Figure(data=[
                go.Bar(x=symbols, y=values, marker_color="#2E86AB")
            ])

            fig.update_layout(
                xaxis_title="Symbol",
                yaxis_title="Value ($)",
                template="plotly_white"
            )

            return fig


class DashboardServer:
    """Dashboard服务器"""

    def __init__(self, dashboard: Dashboard, host: str = "0.0.0.0", port: int = 8050):
        self.dashboard = dashboard
        self.host = host
        self.port = port

    def run(self, debug: bool = False):
        """运行服务器"""
        self.dashboard.app.run_server(
            host=self.host,
            port=self.port,
            debug=debug
        )
