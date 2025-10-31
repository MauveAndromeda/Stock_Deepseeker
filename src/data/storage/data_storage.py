"""
Data Storage Manager
Manages storage of market data, features, and model outputs
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pickle
import json
from loguru import logger


class DataStorage:
    """Manages data storage and retrieval"""

    def __init__(self, base_dir: str = "data"):
        """
        Args:
            base_dir: Base directory for data storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed"
        self.features_dir = self.base_dir / "features"
        self.models_dir = self.base_dir / "models"
        
        for directory in [self.raw_dir, self.processed_dir, self.features_dir, self.models_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Data storage initialized: {base_dir}")

    def save_raw_data(self, symbol: str, df: pd.DataFrame):
        """Save raw market data"""
        filepath = self.raw_dir / f"{symbol}.parquet"
        df.to_parquet(filepath)
        logger.debug(f"Saved raw data: {symbol}")

    def load_raw_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load raw market data"""
        filepath = self.raw_dir / f"{symbol}.parquet"
        
        if not filepath.exists():
            logger.warning(f"Raw data not found: {symbol}")
            return None
        
        df = pd.read_parquet(filepath)
        return df

    def save_processed_data(self, symbol: str, df: pd.DataFrame):
        """Save processed data"""
        filepath = self.processed_dir / f"{symbol}.parquet"
        df.to_parquet(filepath)
        logger.debug(f"Saved processed data: {symbol}")

    def load_processed_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load processed data"""
        filepath = self.processed_dir / f"{symbol}.parquet"
        
        if not filepath.exists():
            return None
        
        return pd.read_parquet(filepath)

    def save_features(self, symbol: str, features: pd.DataFrame):
        """Save engineered features"""
        filepath = self.features_dir / f"{symbol}_features.parquet"
        features.to_parquet(filepath)
        logger.debug(f"Saved features: {symbol}")

    def load_features(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load engineered features"""
        filepath = self.features_dir / f"{symbol}_features.parquet"
        
        if not filepath.exists():
            return None
        
        return pd.read_parquet(filepath)

    def save_model(self, name: str, model: any):
        """Save model to disk"""
        filepath = self.models_dir / f"{name}.pkl"
        
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
        
        logger.info(f"Saved model: {name}")

    def load_model(self, name: str) -> Optional[any]:
        """Load model from disk"""
        filepath = self.models_dir / f"{name}.pkl"
        
        if not filepath.exists():
            logger.warning(f"Model not found: {name}")
            return None
        
        with open(filepath, 'rb') as f:
            model = pickle.load(f)
        
        return model

    def save_metadata(self, symbol: str, metadata: Dict):
        """Save metadata"""
        filepath = self.base_dir / "metadata" / f"{symbol}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

    def load_metadata(self, symbol: str) -> Optional[Dict]:
        """Load metadata"""
        filepath = self.base_dir / "metadata" / f"{symbol}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            metadata = json.load(f)
        
        return metadata

    def list_symbols(self, data_type: str = "raw") -> List[str]:
        """List all available symbols"""
        if data_type == "raw":
            directory = self.raw_dir
        elif data_type == "processed":
            directory = self.processed_dir
        elif data_type == "features":
            directory = self.features_dir
        else:
            return []
        
        symbols = [f.stem for f in directory.glob("*.parquet")]
        return sorted(symbols)

    def delete_symbol_data(self, symbol: str):
        """Delete all data for a symbol"""
        for directory in [self.raw_dir, self.processed_dir, self.features_dir]:
            filepath = directory / f"{symbol}.parquet"
            if filepath.exists():
                filepath.unlink()
        
        logger.info(f"Deleted all data for {symbol}")

    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        stats = {
            'raw_symbols': len(self.list_symbols("raw")),
            'processed_symbols': len(self.list_symbols("processed")),
            'features_symbols': len(self.list_symbols("features")),
        }
        
        # Calculate total size
        total_size = sum(
            f.stat().st_size
            for directory in [self.raw_dir, self.processed_dir, self.features_dir, self.models_dir]
            for f in directory.rglob("*")
            if f.is_file()
        )
        
        stats['total_size_mb'] = total_size / (1024 * 1024)
        
        return stats
