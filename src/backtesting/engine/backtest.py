"""
Backtesting Engine
Historical simulation of trading strategies
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

@dataclass
class BacktestResult:
    """Backtest results"""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: List[float]
    trades: List[Dict]
    metrics: Dict

class BacktestEngine:
    """Backtesting engine for strategies"""

    def __init__(
        self,
        initial_capital: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.0005
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        logger.info("Backtest engine initialized")

    def run(
        self,
        strategy,
        data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Run backtest"""
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        # Initialize state
        capital = self.initial_capital
        positions = {}
        equity_curve = [capital]
        trades = []
        
        # Get all dates
        all_dates = self._get_trading_dates(data, start_date, end_date)
        
        # Main backtest loop
        for date in all_dates:
            # Update positions with current prices
            current_prices = self._get_prices_for_date(data, date)
            
            # Calculate current equity
            equity = capital
            for symbol, pos in positions.items():
                if symbol in current_prices:
                    equity += pos['quantity'] * current_prices[symbol]
            
            equity_curve.append(equity)
            
            # Check exits
            exits = []
            for symbol, pos in positions.items():
                if symbol in current_prices:
                    # Update position price
                    pos['current_price'] = current_prices[symbol]
                    
                    # Create position object for strategy
                    from src.trading.strategy.base import Position
                    position = Position(
                        symbol=symbol,
                        quantity=pos['quantity'],
                        entry_price=pos['entry_price'],
                        entry_time=pos['entry_time'],
                        current_price=current_prices[symbol],
                        stop_loss=pos.get('stop_loss'),
                        take_profit=pos.get('take_profit'),
                        position_type=pos['type']
                    )
                    
                    # Check if should exit
                    should_exit, reason = strategy.should_exit(
                        position,
                        data[symbol].loc[:date]
                    )
                    
                    if should_exit:
                        exits.append((symbol, reason))
            
            # Execute exits
            for symbol, reason in exits:
                trade = self._close_position(
                    symbol, positions, current_prices[symbol],
                    date, reason
                )
                capital += trade['pnl']
                trades.append(trade)
            
            # Check entries
            if len(positions) < 10:  # Max positions
                for symbol in data.keys():
                    if symbol not in positions and symbol in current_prices:
                        should_enter, pos_type = strategy.should_enter(
                            data[symbol].loc[:date],
                            symbol
                        )
                        
                        if should_enter and capital > 0:
                            # Calculate position size
                            price = current_prices[symbol]
                            quantity = int((capital * 0.1) / price)  # 10% per position
                            
                            if quantity > 0:
                                # Open position
                                cost = quantity * price * (1 + self.commission + self.slippage)
                                capital -= cost
                                
                                positions[symbol] = {
                                    'symbol': symbol,
                                    'quantity': quantity,
                                    'entry_price': price,
                                    'entry_time': date,
                                    'current_price': price,
                                    'type': pos_type,
                                    'stop_loss': price * 0.98,
                                    'take_profit': price * 1.05
                                }
                                
                                logger.debug(f"Opened {pos_type} position: {symbol} @ ${price}")
        
        # Close all remaining positions
        final_date = all_dates[-1]
        final_prices = self._get_prices_for_date(data, final_date)
        
        for symbol in list(positions.keys()):
            if symbol in final_prices:
                trade = self._close_position(
                    symbol, positions, final_prices[symbol],
                    final_date, "backtest_end"
                )
                capital += trade['pnl']
                trades.append(trade)
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_curve, trades)
        
        result = BacktestResult(
            total_return=metrics['total_return'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown=metrics['max_drawdown'],
            win_rate=metrics['win_rate'],
            total_trades=len(trades),
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics
        )
        
        logger.info(f"Backtest complete. Return: {result.total_return:.2%}, Sharpe: {result.sharpe_ratio:.2f}")
        
        return result

    def _get_trading_dates(
        self,
        data: Dict[str, pd.DataFrame],
        start: datetime,
        end: datetime
    ) -> List[datetime]:
        """Get all trading dates in range"""
        # Get dates from first symbol
        first_symbol = list(data.keys())[0]
        df = data[first_symbol]
        
        # Filter by date range
        mask = (df.index >= start) & (df.index <= end)
        dates = df.index[mask].tolist()
        
        return dates

    def _get_prices_for_date(
        self,
        data: Dict[str, pd.DataFrame],
        date: datetime
    ) -> Dict[str, float]:
        """Get closing prices for all symbols on date"""
        prices = {}
        
        for symbol, df in data.items():
            if date in df.index:
                prices[symbol] = df.loc[date, 'close']
        
        return prices

    def _close_position(
        self,
        symbol: str,
        positions: Dict,
        price: float,
        date: datetime,
        reason: str
    ) -> Dict:
        """Close a position and return trade data"""
        pos = positions[symbol]
        
        # Calculate P&L
        if pos['type'] == 'long':
            proceeds = pos['quantity'] * price * (1 - self.commission - self.slippage)
            cost = pos['quantity'] * pos['entry_price']
            pnl = proceeds - cost
        else:
            proceeds = pos['quantity'] * pos['entry_price']
            cost = pos['quantity'] * price * (1 + self.commission + self.slippage)
            pnl = proceeds - cost
        
        pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
        
        trade = {
            'symbol': symbol,
            'type': pos['type'],
            'entry_date': pos['entry_time'],
            'exit_date': date,
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'quantity': pos['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
        
        del positions[symbol]
        
        return trade

    def _calculate_metrics(self, equity_curve: List[float], trades: List[Dict]) -> Dict:
        """Calculate backtest metrics"""
        equity = np.array(equity_curve)
        
        # Total return
        total_return = (equity[-1] / equity[0] - 1) * 100
        
        # Returns
        returns = np.diff(equity) / equity[:-1]
        
        # Sharpe ratio
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Max drawdown
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        max_dd = abs(np.min(drawdown)) * 100
        
        # Win rate
        if trades:
            winners = sum(1 for t in trades if t['pnl'] > 0)
            win_rate = winners / len(trades) * 100
        else:
            win_rate = 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'num_trades': len(trades),
            'avg_trade': np.mean([t['pnl'] for t in trades]) if trades else 0
        }
