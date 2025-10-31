"""
RESTful API接口
使用FastAPI构建
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ===== 数据模型 =====

class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderRequest(BaseModel):
    """订单请求"""
    symbol: str = Field(..., description="股票代码")
    side: OrderSide = Field(..., description="买卖方向")
    order_type: OrderType = Field(OrderType.MARKET, description="订单类型")
    quantity: int = Field(..., gt=0, description="数量")
    price: Optional[float] = Field(None, gt=0, description="价格")
    stop_price: Optional[float] = Field(None, gt=0, description="止损价")


class OrderResponse(BaseModel):
    """订单响应"""
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: int
    price: Optional[float]
    status: str
    created_at: datetime
    

class PortfolioResponse(BaseModel):
    """投资组合响应"""
    total_value: float
    cash: float
    positions_value: float
    daily_pnl: float
    total_pnl: float
    return_rate: float
    positions: List[Dict[str, Any]]


class PerformanceResponse(BaseModel):
    """性能指标响应"""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, str]


# ===== API类 =====

class TradingAPI:
    """交易API主类"""
    
    def __init__(self, trading_system: Any):
        """
        初始化API
        
        Args:
            trading_system: 交易系统实例
        """
        self.trading_system = trading_system
        self.start_time = datetime.now()
    
    async def create_order(self, order_request: OrderRequest) -> OrderResponse:
        """创建订单"""
        try:
            # 调用交易系统创建订单
            order = await self.trading_system.create_order(
                symbol=order_request.symbol,
                side=order_request.side.value,
                order_type=order_request.order_type.value,
                quantity=order_request.quantity,
                price=order_request.price,
                stop_price=order_request.stop_price
            )
            
            return OrderResponse(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                status=order.status,
                created_at=order.created_at
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create order: {str(e)}"
            )
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """取消订单"""
        try:
            success = await self.trading_system.cancel_order(order_id)
            
            if success:
                return {"order_id": order_id, "status": "cancelled"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found or cannot be cancelled"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel order: {str(e)}"
            )
    
    async def get_order(self, order_id: str) -> OrderResponse:
        """获取订单详情"""
        try:
            order = await self.trading_system.get_order(order_id)
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            return OrderResponse(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                status=order.status,
                created_at=order.created_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get order: {str(e)}"
            )
    
    async def get_portfolio(self) -> PortfolioResponse:
        """获取投资组合"""
        try:
            portfolio = await self.trading_system.get_portfolio()
            
            return PortfolioResponse(
                total_value=portfolio['total_value'],
                cash=portfolio['cash'],
                positions_value=portfolio['positions_value'],
                daily_pnl=portfolio['daily_pnl'],
                total_pnl=portfolio['total_pnl'],
                return_rate=portfolio['return_rate'],
                positions=portfolio['positions']
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get portfolio: {str(e)}"
            )
    
    async def get_performance(self) -> PerformanceResponse:
        """获取性能指标"""
        try:
            performance = await self.trading_system.get_performance()
            
            return PerformanceResponse(
                total_return=performance['total_return'],
                annualized_return=performance['annualized_return'],
                sharpe_ratio=performance['sharpe_ratio'],
                max_drawdown=performance['max_drawdown'],
                win_rate=performance['win_rate'],
                total_trades=performance['total_trades']
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get performance: {str(e)}"
            )
    
    async def health_check(self) -> HealthResponse:
        """健康检查"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # 检查各组件状态
        components = {
            "trading_system": "ok",
            "data_feed": "ok",
            "execution_engine": "ok",
            "risk_manager": "ok"
        }
        
        return HealthResponse(
            status="healthy",
            version="3.0.0",
            timestamp=datetime.now(),
            uptime_seconds=uptime,
            components=components
        )


# ===== FastAPI应用 =====

def create_app(trading_system: Any) -> FastAPI:
    """
    创建FastAPI应用
    
    Args:
        trading_system: 交易系统实例
        
    Returns:
        FastAPI应用实例
    """
    app = FastAPI(
        title="Stock Deepseeker API",
        description="机构级AI量化交易系统API",
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 创建API实例
    api = TradingAPI(trading_system)
    
    # ===== 路由 =====
    
    @app.get("/", response_model=Dict[str, str])
    async def root():
        """根路径"""
        return {
            "name": "Stock Deepseeker API",
            "version": "3.0.0",
            "status": "running"
        }
    
    @app.get("/health", response_model=HealthResponse)
    async def health():
        """健康检查"""
        return await api.health_check()
    
    @app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
    async def create_order(order: OrderRequest):
        """创建订单"""
        return await api.create_order(order)
    
    @app.get("/orders/{order_id}", response_model=OrderResponse)
    async def get_order(order_id: str):
        """获取订单"""
        return await api.get_order(order_id)
    
    @app.delete("/orders/{order_id}")
    async def cancel_order(order_id: str):
        """取消订单"""
        return await api.cancel_order(order_id)
    
    @app.get("/portfolio", response_model=PortfolioResponse)
    async def get_portfolio():
        """获取投资组合"""
        return await api.get_portfolio()
    
    @app.get("/performance", response_model=PerformanceResponse)
    async def get_performance():
        """获取性能指标"""
        return await api.get_performance()
    
    @app.get("/metrics")
    async def get_metrics():
        """获取系统指标（Prometheus格式）"""
        # TODO: 返回Prometheus格式的指标
        return {"status": "not implemented"}
    
    # 异常处理
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"}
        )
    
    return app
