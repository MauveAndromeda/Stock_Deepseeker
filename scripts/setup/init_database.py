"""
Database Initialization Script
Sets up PostgreSQL, TimescaleDB, and Redis
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from loguru import logger

from src.utils.config import get_config


def create_postgresql_database():
    """Create PostgreSQL database"""
    config = get_config()
    
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=config.database.postgres_host,
            port=config.database.postgres_port,
            user=config.database.postgres_user,
            password=config.database.postgres_password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database
        cursor.execute(f"DROP DATABASE IF EXISTS {config.database.postgres_db}")
        cursor.execute(f"CREATE DATABASE {config.database.postgres_db}")
        
        logger.info(f"Created database: {config.database.postgres_db}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False


def create_tables():
    """Create database tables"""
    config = get_config()
    
    try:
        conn = psycopg2.connect(
            host=config.database.postgres_host,
            port=config.database.postgres_port,
            user=config.database.postgres_user,
            password=config.database.postgres_password,
            database=config.database.postgres_db
        )
        cursor = conn.cursor()
        
        # Enable TimescaleDB extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        
        # Price data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                time TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume BIGINT,
                PRIMARY KEY (time, symbol)
            )
        """)
        
        # Convert to hypertable
        cursor.execute("""
            SELECT create_hypertable('price_data', 'time',
                if_not_exists => TRUE,
                chunk_time_interval => INTERVAL '1 day'
            )
        """)
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                action VARCHAR(10),
                quantity INTEGER,
                price DOUBLE PRECISION,
                commission DOUBLE PRECISION,
                pnl DOUBLE PRECISION,
                strategy VARCHAR(50)
            )
        """)
        
        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                quantity INTEGER,
                entry_price DOUBLE PRECISION,
                current_price DOUBLE PRECISION,
                unrealized_pnl DOUBLE PRECISION,
                UNIQUE(symbol)
            )
        """)
        
        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                time TIMESTAMPTZ NOT NULL,
                portfolio_value DOUBLE PRECISION,
                cash_balance DOUBLE PRECISION,
                total_return DOUBLE PRECISION,
                sharpe_ratio DOUBLE PRECISION,
                max_drawdown DOUBLE PRECISION,
                num_positions INTEGER,
                PRIMARY KEY (time)
            )
        """)
        
        cursor.execute("""
            SELECT create_hypertable('performance_metrics', 'time',
                if_not_exists => TRUE
            )
        """)
        
        conn.commit()
        logger.info("Created all database tables")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def setup_redis():
    """Setup Redis"""
    import redis
    config = get_config()
    
    try:
        r = redis.Redis(
            host=config.database.redis_host,
            port=config.database.redis_port,
            db=config.database.redis_db,
            password=config.database.redis_password,
            decode_responses=True
        )
        
        # Test connection
        r.ping()
        
        # Set some initial keys
        r.set('system:status', 'initialized')
        r.set('system:start_time', str(datetime.now()))
        
        logger.info("Redis setup complete")
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting up Redis: {e}")
        return False


def main():
    """Main setup function"""
    logger.info("Starting database initialization...")
    
    # Create database
    if not create_postgresql_database():
        logger.error("Failed to create database")
        return
    
    # Create tables
    if not create_tables():
        logger.error("Failed to create tables")
        return
    
    # Setup Redis
    if not setup_redis():
        logger.error("Failed to setup Redis")
        return
    
    logger.info("Database initialization complete!")


if __name__ == "__main__":
    from datetime import datetime
    main()
