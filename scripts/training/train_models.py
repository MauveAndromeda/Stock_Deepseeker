"""
Model Training Script
Trains all AI models for the trading system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
import numpy as np
import torch
from datetime import datetime, timedelta
from loguru import logger

from src.utils.config import get_config
from src.data.collectors import MarketDataCollector, SP500Universe
from src.data.processors import DataProcessor, FeatureProcessor
from src.features.technical.indicators import TechnicalIndicators
from src.models.transformer.model import TimeSeriesTransformer
from src.models.sac.agent import SACTradingAgent
from src.models.sac.environment import TradingEnvironment


def setup_logging():
    """Setup logging configuration"""
    logger.add(
        "logs/training_{time}.log",
        rotation="1 day",
        retention="30 days",
        level="INFO"
    )
    logger.info("Training script started")


def load_training_data(symbols: list, start_date: str, end_date: str):
    """Load and process training data"""
    logger.info(f"Loading data for {len(symbols)} symbols")
    
    collector = MarketDataCollector()
    data_dict = collector.get_historical_data_bulk(
        symbols,
        start_date=start_date,
        end_date=end_date,
        interval='1d'
    )
    
    logger.info(f"Loaded data for {len(data_dict)} symbols")
    return data_dict


def preprocess_data(data_dict):
    """Preprocess raw data"""
    logger.info("Preprocessing data...")
    
    processor = DataProcessor()
    tech_indicators = TechnicalIndicators()
    feature_processor = FeatureProcessor()
    
    processed_data = {}
    
    for symbol, df in data_dict.items():
        try:
            # Clean data
            df = processor.process_ohlcv(df, symbol)
            
            # Add technical indicators
            df = tech_indicators.calculate_all_indicators(df)
            
            # Create features
            df = feature_processor.create_lag_features(
                df, ['close', 'volume'], [1, 2, 3, 5, 10]
            )
            df = feature_processor.create_rolling_features(
                df, ['close', 'volume'], [5, 10, 20]
            )
            
            # Drop NaN
            df = df.dropna()
            
            if len(df) > 100:
                processed_data[symbol] = df
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
    
    logger.info(f"Processed {len(processed_data)} symbols")
    return processed_data


def train_transformer_model(data_dict, config):
    """Train Transformer prediction model"""
    logger.info("Training Transformer model...")
    
    # Prepare data
    all_sequences = []
    all_targets = []
    
    for symbol, df in data_dict.items():
        # Select features
        feature_cols = [c for c in df.columns if c not in ['symbol', 'date']]
        features = df[feature_cols].values
        
        # Create sequences
        seq_length = config.model.transformer_seq_length
        
        for i in range(len(df) - seq_length - 1):
            seq = features[i:i+seq_length]
            target = df['close'].values[i+seq_length]
            
            all_sequences.append(seq)
            all_targets.append(target)
    
    # Convert to arrays
    X = np.array(all_sequences)
    y = np.array(all_targets)
    
    logger.info(f"Created {len(X)} training sequences")
    
    # Split train/val
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    # Initialize model
    input_dim = X.shape[2]
    model = TimeSeriesTransformer(
        input_dim=input_dim,
        d_model=config.model.transformer_hidden_size,
        num_heads=config.model.transformer_num_heads,
        num_layers=config.model.transformer_num_layers,
        output_dim=1
    )
    
    # Move to device
    device = torch.device('cuda' if config.model.use_gpu and torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    # Training setup
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = torch.nn.MSELoss()
    
    # Training loop
    epochs = 50
    batch_size = 32
    
    for epoch in range(epochs):
        model.train()
        epoch_loss = 0
        
        # Batch training
        for i in range(0, len(X_train), batch_size):
            batch_X = torch.FloatTensor(X_train[i:i+batch_size]).to(device)
            batch_y = torch.FloatTensor(y_train[i:i+batch_size]).unsqueeze(1).to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for i in range(0, len(X_val), batch_size):
                batch_X = torch.FloatTensor(X_val[i:i+batch_size]).to(device)
                batch_y = torch.FloatTensor(y_val[i:i+batch_size]).unsqueeze(1).to(device)
                
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
        
        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs}, Train Loss: {epoch_loss:.4f}, Val Loss: {val_loss:.4f}")
    
    # Save model
    torch.save(model.state_dict(), 'models/transformer_model.pth')
    logger.info("Transformer model saved")
    
    return model


def train_sac_agent(data_dict, config):
    """Train SAC trading agent"""
    logger.info("Training SAC agent...")
    
    # Combine all data
    combined_data = pd.concat(data_dict.values(), ignore_index=True)
    combined_data = combined_data.dropna()
    
    # Create environment
    env = TradingEnvironment(
        df=combined_data,
        initial_balance=config.trading.initial_capital,
        commission=0.001
    )
    
    # Initialize agent
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.shape[0]
    
    agent = SACTradingAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        lr=config.model.sac_learning_rate,
        gamma=config.model.sac_gamma,
        tau=config.model.sac_tau
    )
    
    # Training parameters
    episodes = 100
    batch_size = config.model.sac_batch_size
    
    for episode in range(episodes):
        state, _ = env.reset()
        episode_reward = 0
        done = False
        
        while not done:
            # Select action
            action = agent.select_action(state, eval_mode=False)
            
            # Take step
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
            # Store experience
            agent.replay_buffer.push(state, action, reward, next_state, done)
            
            # Train if enough samples
            if len(agent.replay_buffer) > batch_size:
                metrics = agent.train(batch_size)
            
            state = next_state
            episode_reward += reward
        
        if (episode + 1) % 10 == 0:
            logger.info(f"Episode {episode+1}/{episodes}, Reward: {episode_reward:.2f}")
    
    # Save agent
    agent.save('models/sac_agent.pth')
    logger.info("SAC agent saved")
    
    return agent


def main():
    """Main training pipeline"""
    setup_logging()
    
    config = get_config()
    
    # Get S&P 500 symbols
    symbols = SP500Universe.get_all_tickers()[:50]  # Limit for training
    
    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1000)
    
    # Load data
    data_dict = load_training_data(
        symbols,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Preprocess
    processed_data = preprocess_data(data_dict)
    
    # Train Transformer
    transformer_model = train_transformer_model(processed_data, config)
    
    # Train SAC agent
    sac_agent = train_sac_agent(processed_data, config)
    
    logger.info("Training complete!")
    
    # Print summary
    logger.info(f"Models saved to models/ directory")
    logger.info(f"Total symbols trained: {len(processed_data)}")


if __name__ == "__main__":
    main()
