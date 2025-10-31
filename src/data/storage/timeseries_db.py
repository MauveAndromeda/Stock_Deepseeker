"""
TimescaleDB Interface
Handles time-series data storage in PostgreSQL + TimescaleDB
"""

import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
from loguru import logger
import psycopg2
from psycopg2.extras import execute_values


class TimeSeriesDB:
    """Interface to TimescaleDB"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
        """
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        
        self.conn = None
        self._connect()
        
        logger.info(f"TimescaleDB connected: {database}@{host}")

    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _ensure_connected(self):
        """Ensure connection is active"""
        if self.conn is None or self.conn.closed:
            self._connect()

    def insert_price_data(self, symbol: str, df: pd.DataFrame):
        """
        Insert price data
        
        Args:
            symbol: Stock symbol
            df: DataFrame with columns: timestamp, open, high, low, close, volume
        """
        self._ensure_connected()
        
        cursor = self.conn.cursor()
        
        # Prepare data
        data = [
            (row.name, symbol, row['open'], row['high'], row['low'], row['close'], int(row['volume']))
            for _, row in df.iterrows()
        ]
        
        # Insert
        query = """
            INSERT INTO price_data (time, symbol, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (time, symbol) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        
        execute_values(cursor, query, data)
        self.conn.commit()
        
        logger.debug(f"Inserted {len(data)} price bars for {symbol}")

    def query_price_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """
        Query price data
        
        Args:
            symbol: Stock symbol
            start_time: Start time
            end_time: End time
            
        Returns:
            DataFrame with price data
        """
        self._ensure_connected()
        
        query = """
            SELECT time, open, high, low, close, volume
            FROM price_data
            WHERE symbol = %s
                AND time >= %s
                AND time <= %s
            ORDER BY time
        """
        
        df = pd.read_sql_query(
            query,
            self.conn,
            params=(symbol, start_time, end_time),
            index_col='time',
            parse_dates=['time']
        )
        
        return df

    def insert_trade(self, trade: Dict):
        """Insert trade record"""
        self._ensure_connected()
        
        cursor = self.conn.cursor()
        
        query = """
            INSERT INTO trades (time, symbol, action, quantity, price, commission, pnl, strategy)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(
            query,
            (
                trade['time'],
                trade['symbol'],
                trade['action'],
                trade['quantity'],
                trade['price'],
                trade['commission'],
                trade.get('pnl', 0),
                trade.get('strategy', 'unknown')
            )
        )
        
        self.conn.commit()

    def insert_performance_metrics(self, metrics: Dict):
        """Insert performance metrics"""
        self._ensure_connected()
        
        cursor = self.conn.cursor()
        
        query = """
            INSERT INTO performance_metrics (
                time, portfolio_value, cash_balance, total_return,
                sharpe_ratio, max_drawdown, num_positions
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time) DO UPDATE SET
                portfolio_value = EXCLUDED.portfolio_value,
                cash_balance = EXCLUDED.cash_balance,
                total_return = EXCLUDED.total_return,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                max_drawdown = EXCLUDED.max_drawdown,
                num_positions = EXCLUDED.num_positions
        """
        
        cursor.execute(
            query,
            (
                metrics['time'],
                metrics['portfolio_value'],
                metrics['cash_balance'],
                metrics.get('total_return', 0),
                metrics.get('sharpe_ratio', 0),
                metrics.get('max_drawdown', 0),
                metrics.get('num_positions', 0)
            )
        )
        
        self.conn.commit()

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for symbol"""
        self._ensure_connected()
        
        query = """
            SELECT close
            FROM price_data
            WHERE symbol = %s
            ORDER BY time DESC
            LIMIT 1
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, (symbol,))
        
        result = cursor.fetchone()
        
        if result:
            return result[0]
        
        return None

    def get_trade_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Get trade history"""
        self._ensure_connected()
        
        query = "SELECT * FROM trades"
        conditions = []
        params = []
        
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        
        if start_time:
            conditions.append("time >= %s")
            params.append(start_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY time DESC LIMIT %s"
        params.append(limit)
        
        df = pd.read_sql_query(query, self.conn, params=params)
        
        return df

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
