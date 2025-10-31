"""
Main Trading System Loop
Orchestrates data collection, model inference, trading decisions, and execution
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from loguru import logger

from src.utils.config import get_config
from src.utils.helpers import is_market_open, get_next_market_open
from src.data.collectors import MarketDataCollector, NewsCollector, SentimentCollector, SP500Universe
from src.features.technical.indicators import TechnicalIndicators
from src.models.transformer.model import TimeSeriesTransformer
from src.models.sac.agent import SACTradingAgent
from src.models.sac.environment import MultiAssetTradingEnvironment
from src.trading.strategy import MomentumStrategy, MLStrategy
from src.trading.execution import OrderExecutor
from src.risk.manager import RiskManager
from src.portfolio.manager import PortfolioManager
from src.monitoring.metrics import MetricsCollector
from src.api.llm.gpt_analyzer import GPTMarketAnalyzer


class TradingSystemState:
    """Tracks system state"""
    def __init__(self):
        self.is_running = False
        self.last_update = None
        self.cycle_count = 0
        self.errors_count = 0
        self.positions = {}
        self.cash_balance = 0.0
        self.total_value = 0.0


class StockDeepSeekerSystem:
    """Main automated trading system orchestrator"""

    def __init__(self):
        self.config = get_config()
        self.state = TradingSystemState()
        
        # Initialize components
        logger.info("Initializing Stock DeepSeeker System...")
        
        # Data collectors
        self.market_data = MarketDataCollector()
        self.news_collector = NewsCollector()
        self.sentiment_analyzer = SentimentCollector()
        
        # Feature engineering
        self.tech_indicators = TechnicalIndicators()
        
        # AI Models
        self._init_models()
        
        # Trading components
        self.strategies = self._init_strategies()
        self.executor = OrderExecutor()
        self.risk_manager = RiskManager()
        self.portfolio_manager = PortfolioManager(
            initial_capital=self.config.trading.initial_capital
        )
        
        # LLM Analyzer
        self.gpt_analyzer = GPTMarketAnalyzer()
        
        # Monitoring
        self.metrics = MetricsCollector()
        
        # Stock universe
        self.universe = SP500Universe.get_all_tickers()
        
        logger.info("Stock DeepSeeker System initialized successfully")

    def _init_models(self):
        """Initialize AI models"""
        logger.info("Initializing AI models...")
        
        # TODO: Load pre-trained models or train if needed
        # self.transformer = TimeSeriesTransformer(...)
        # self.sac_agent = SACTradingAgent(...)
        
        logger.info("AI models initialized")

    def _init_strategies(self) -> List:
        """Initialize trading strategies"""
        from src.trading.strategy.base import StrategyConfig
        
        strategies = []
        
        # Momentum strategy
        momentum_config = StrategyConfig(
            name="Momentum",
            max_positions=5,
            max_position_size=0.05,
            stop_loss_pct=0.02,
            take_profit_pct=0.05
        )
        strategies.append(MomentumStrategy(momentum_config))
        
        # Add more strategies as needed
        
        return strategies

    async def run(self):
        """Main system loop"""
        logger.info("Starting Stock DeepSeeker System main loop...")
        self.state.is_running = True
        
        try:
            while self.state.is_running:
                try:
                    # Check if market is open
                    if not is_market_open():
                        next_open = get_next_market_open()
                        wait_time = (next_open - datetime.now()).total_seconds()
                        logger.info(f"Market closed. Waiting {wait_time/3600:.1f} hours until open")
                        await asyncio.sleep(min(wait_time, 3600))
                        continue
                    
                    # Run trading cycle
                    await self._trading_cycle()
                    
                    # Increment cycle counter
                    self.state.cycle_count += 1
                    self.state.last_update = datetime.now()
                    
                    # Sleep between cycles
                    await asyncio.sleep(self.config.data.price_data_interval)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    self.state.errors_count += 1
                    
                    # Emergency shutdown if too many errors
                    if self.state.errors_count > 10:
                        logger.critical("Too many errors! Emergency shutdown")
                        await self.emergency_shutdown()
                        break
                    
                    await asyncio.sleep(60)
                    
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()

    async def _trading_cycle(self):
        """Execute one complete trading cycle"""
        cycle_start = time.time()
        logger.info(f"Starting trading cycle #{self.state.cycle_count}")
        
        # 1. Collect market data
        market_data = await self._collect_market_data()
        
        # 2. Collect news and sentiment
        news_sentiment = await self._collect_news_sentiment()
        
        # 3. Engineer features
        features = await self._engineer_features(market_data)
        
        # 4. Run AI models for predictions
        predictions = await self._run_predictions(features)
        
        # 5. Get LLM market analysis
        llm_analysis = await self._get_llm_analysis(market_data, news_sentiment)
        
        # 6. Generate trading signals from strategies
        signals = await self._generate_signals(features, predictions, llm_analysis)
        
        # 7. Filter signals by stock selection
        selected_stocks = await self._select_stocks(signals, market_data)
        
        # 8. Risk management checks
        approved_trades = await self._risk_checks(selected_stocks)
        
        # 9. Portfolio optimization
        optimal_allocation = await self._optimize_portfolio(approved_trades)
        
        # 10. Execute trades
        await self._execute_trades(optimal_allocation)
        
        # 11. Update portfolio and positions
        await self._update_portfolio()
        
        # 12. Monitor performance
        await self._monitor_performance()
        
        # 13. Update metrics
        cycle_time = time.time() - cycle_start
        self.metrics.record_cycle_time(cycle_time)
        
        logger.info(f"Trading cycle completed in {cycle_time:.2f}s")

    async def _collect_market_data(self) -> Dict:
        """Collect real-time market data for all symbols"""
        logger.debug("Collecting market data...")
        
        data = {}
        for symbol in self.universe[:50]:  # Limit for performance
            try:
                # Get latest bars
                df = self.market_data.get_intraday_data(symbol, interval="1m", days=1)
                if not df.empty:
                    data[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to get data for {symbol}: {e}")
        
        logger.debug(f"Collected data for {len(data)} symbols")
        return data

    async def _collect_news_sentiment(self) -> Dict:
        """Collect news and analyze sentiment"""
        logger.debug("Collecting news and sentiment...")
        
        sentiment_data = {}
        
        # Get general market news
        market_news = self.news_collector.get_market_news(max_articles=50)
        market_sentiment = self.sentiment_analyzer.get_market_sentiment(market_news)
        
        sentiment_data["market"] = market_sentiment
        
        # Get news for top symbols
        for symbol in self.universe[:20]:
            try:
                news = self.news_collector.get_news_for_symbol(symbol, days_back=1, max_articles=10)
                if news:
                    sentiment = self.sentiment_analyzer.get_symbol_sentiment(symbol, news)
                    sentiment_data[symbol] = sentiment
            except Exception as e:
                logger.warning(f"Failed to get news for {symbol}: {e}")
        
        return sentiment_data

    async def _engineer_features(self, market_data: Dict) -> Dict:
        """Engineer features from raw data"""
        logger.debug("Engineering features...")
        
        features = {}
        for symbol, df in market_data.items():
            try:
                # Calculate technical indicators
                df_with_indicators = self.tech_indicators.calculate_all_indicators(df)
                features[symbol] = df_with_indicators
            except Exception as e:
                logger.warning(f"Feature engineering failed for {symbol}: {e}")
        
        return features

    async def _run_predictions(self, features: Dict) -> Dict:
        """Run AI model predictions"""
        logger.debug("Running AI predictions...")
        
        predictions = {}
        
        # TODO: Implement actual model inference
        # For now, return placeholder
        for symbol in features.keys():
            predictions[symbol] = {
                "price_direction": 0.0,  # -1 to 1
                "confidence": 0.5,
                "volatility": 0.02
            }
        
        return predictions

    async def _get_llm_analysis(self, market_data: Dict, news_sentiment: Dict) -> Dict:
        """Get LLM analysis of market conditions"""
        logger.debug("Getting LLM market analysis...")
        
        try:
            analysis = await self.gpt_analyzer.analyze_market(
                market_data, news_sentiment
            )
            return analysis
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {}

    async def _generate_signals(self, features: Dict, predictions: Dict, llm_analysis: Dict) -> Dict:
        """Generate trading signals from all strategies"""
        logger.debug("Generating trading signals...")
        
        all_signals = {}
        
        for strategy in self.strategies:
            for symbol, df in features.items():
                try:
                    signal = strategy.analyze(df, symbol)
                    
                    if symbol not in all_signals:
                        all_signals[symbol] = []
                    all_signals[symbol].append(signal)
                    
                except Exception as e:
                    logger.warning(f"Signal generation failed for {symbol}: {e}")
        
        return all_signals

    async def _select_stocks(self, signals: Dict, market_data: Dict) -> List:
        """Select best stocks to trade based on signals"""
        logger.debug("Selecting stocks...")
        
        scored_stocks = []
        
        for symbol, signal_list in signals.items():
            # Aggregate signals
            buy_strength = sum(s.strength for s in signal_list if s.action == "buy")
            sell_strength = sum(s.strength for s in signal_list if s.action == "sell")
            avg_confidence = np.mean([s.confidence for s in signal_list])
            
            net_strength = buy_strength - sell_strength
            
            if abs(net_strength) > 0.5 and avg_confidence > 0.6:
                scored_stocks.append({
                    "symbol": symbol,
                    "action": "buy" if net_strength > 0 else "sell",
                    "score": abs(net_strength) * avg_confidence,
                    "confidence": avg_confidence
                })
        
        # Sort by score and return top stocks
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        selected = scored_stocks[:self.config.trading.max_positions]
        
        logger.info(f"Selected {len(selected)} stocks for trading")
        return selected

    async def _risk_checks(self, selected_stocks: List) -> List:
        """Apply risk management filters"""
        logger.debug("Performing risk checks...")
        
        approved = []
        
        for stock in selected_stocks:
            symbol = stock["symbol"]
            
            # Check risk limits
            if self.risk_manager.can_trade(symbol, stock["action"]):
                approved.append(stock)
            else:
                logger.warning(f"Risk check failed for {symbol}")
        
        logger.info(f"Approved {len(approved)}/{len(selected_stocks)} trades")
        return approved

    async def _optimize_portfolio(self, approved_trades: List) -> Dict:
        """Optimize portfolio allocation"""
        logger.debug("Optimizing portfolio...")
        
        # Use portfolio manager to optimize allocation
        allocation = self.portfolio_manager.optimize_allocation(approved_trades)
        
        return allocation

    async def _execute_trades(self, allocation: Dict):
        """Execute approved trades"""
        logger.debug("Executing trades...")
        
        for symbol, position_info in allocation.items():
            try:
                if position_info["action"] == "buy":
                    await self.executor.buy(
                        symbol, 
                        quantity=position_info["quantity"],
                        limit_price=position_info.get("limit_price")
                    )
                elif position_info["action"] == "sell":
                    await self.executor.sell(
                        symbol,
                        quantity=position_info["quantity"],
                        limit_price=position_info.get("limit_price")
                    )
            except Exception as e:
                logger.error(f"Trade execution failed for {symbol}: {e}")

    async def _update_portfolio(self):
        """Update portfolio state"""
        positions = await self.executor.get_positions()
        account = await self.executor.get_account()
        
        self.state.positions = positions
        self.state.cash_balance = account.get("cash", 0)
        self.state.total_value = account.get("portfolio_value", 0)
        
        self.portfolio_manager.update_state(positions, account)

    async def _monitor_performance(self):
        """Monitor and log performance"""
        # Log portfolio value
        self.metrics.record_portfolio_value(self.state.total_value)
        
        # Calculate returns
        returns = (self.state.total_value / self.config.trading.initial_capital - 1) * 100
        
        logger.info(
            f"Portfolio Value: ${self.state.total_value:,.2f} "
            f"| Return: {returns:.2f}% "
            f"| Positions: {len(self.state.positions)}"
        )

    async def emergency_shutdown(self):
        """Emergency shutdown procedure"""
        logger.critical("EMERGENCY SHUTDOWN INITIATED")
        
        try:
            # Close all positions
            for symbol in list(self.state.positions.keys()):
                await self.executor.close_position(symbol, reason="emergency_shutdown")
            
            # Cancel all open orders
            await self.executor.cancel_all_orders()
            
            logger.critical("Emergency shutdown completed")
            
        except Exception as e:
            logger.critical(f"Error during emergency shutdown: {e}")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Stock DeepSeeker System...")
        
        self.state.is_running = False
        
        # Save state
        # Close connections
        # Final reporting
        
        logger.info("System shutdown complete")


async def main():
    """Main entry point"""
    system = StockDeepSeekerSystem()
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
