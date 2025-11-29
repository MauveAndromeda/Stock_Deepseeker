"""
数据存储层
支持时序数据库、缓存

Security Note: pickle is used for local caching only. Data comes from
trusted sources (our own code). For untrusted data, use JSON or parquet.
"""

from datetime import datetime
from pathlib import Path
import pickle
import sqlite3
from typing import Any

import pandas as pd


class DataStorage:
    """数据存储基类"""

    def save(self, key: str, data: Any) -> None:
        """保存数据"""
        raise NotImplementedError

    def load(self, key: str) -> Any:
        """加载数据"""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """删除数据"""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """检查是否存在"""
        raise NotImplementedError


class FileStorage(DataStorage):
    """文件存储

    Uses pickle for general objects and parquet for DataFrames when available.
    Pickle is safe here as we only load files created by this application.
    """

    def __init__(self, base_path: str = "data/storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: Any) -> None:
        """保存到文件

        For DataFrames, attempts parquet first (faster, smaller),
        falls back to pickle for other types or if parquet unavailable.
        """
        # Try parquet for DataFrames (safer and more efficient)
        if isinstance(data, pd.DataFrame):
            parquet_path = self.base_path / f"{key}.parquet"
            try:
                data.to_parquet(parquet_path)
                return
            except (ImportError, ValueError):
                pass  # Fall back to pickle

        file_path = self.base_path / f"{key}.pkl"
        with open(file_path, "wb") as f:
            pickle.dump(data, f)

    def load(self, key: str) -> Any:
        """从文件加载

        Checks for parquet first, then pickle.
        """
        # Try parquet first
        parquet_path = self.base_path / f"{key}.parquet"
        if parquet_path.exists():
            try:
                return pd.read_parquet(parquet_path)
            except (ImportError, ValueError):
                pass

        # Fall back to pickle
        file_path = self.base_path / f"{key}.pkl"
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return pickle.load(f)  # Safe: only loads our own cached files

    def delete(self, key: str) -> bool:
        """删除文件"""
        deleted = False
        for ext in [".pkl", ".parquet"]:
            file_path = self.base_path / f"{key}{ext}"
            if file_path.exists():
                file_path.unlink()
                deleted = True
        return deleted

    def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        pkl_path = self.base_path / f"{key}.pkl"
        parquet_path = self.base_path / f"{key}.parquet"
        return pkl_path.exists() or parquet_path.exists()


class TimeSeriesDB:
    """时序数据库"""

    def __init__(self, db_path: str = "data/timeseries.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        cursor = self.conn.cursor()

        # 创建价格表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                UNIQUE(symbol, timestamp)
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
            ON prices(symbol, timestamp)
        """)

        self.conn.commit()

    def insert_ohlcv(
        self,
        symbol: str,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int
    ):
        """插入OHLCV数据"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO prices 
            (symbol, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, timestamp, open_price, high, low, close, volume))

        self.conn.commit()

    def insert_dataframe(self, df: pd.DataFrame, symbol: str):
        """批量插入DataFrame"""
        for idx, row in df.iterrows():
            self.insert_ohlcv(
                symbol=symbol,
                timestamp=idx,
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"]
            )

    def query(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> pd.DataFrame:
        """查询数据"""
        query = "SELECT timestamp, open, high, low, close, volume FROM prices WHERE symbol = ?"
        params = [symbol]

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"

        df = pd.read_sql_query(query, self.conn, params=params, parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)

        return df

    def get_latest(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """获取最新数据"""
        query = """
            SELECT timestamp, open, high, low, close, volume 
            FROM prices 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """

        df = pd.read_sql_query(query, self.conn, params=[symbol, limit], parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        return df

    def close(self):
        """关闭连接"""
        self.conn.close()


class CacheLayer:
    """缓存层"""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def set(self, key: str, value: Any, ttl: int | None = None):
        """设置缓存"""
        self.cache[key] = {
            "value": value,
            "timestamp": datetime.now(),
            "ttl": ttl or self.ttl_seconds
        }

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        age = (datetime.now() - entry["timestamp"]).total_seconds()

        if age > entry["ttl"]:
            # 过期，删除
            del self.cache[key]
            return None

        return entry["value"]

    def delete(self, key: str):
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []

        for key, entry in self.cache.items():
            age = (now - entry["timestamp"]).total_seconds()
            if age > entry["ttl"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)
