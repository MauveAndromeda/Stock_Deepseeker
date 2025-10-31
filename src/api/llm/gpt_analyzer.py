"""
GPT Market Analyzer
Uses ChatGPT API for advanced market analysis
"""

import openai
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
from src.utils.config import get_config

class GPTMarketAnalyzer:
    """Analyzes market using GPT models"""

    def __init__(self):
        self.config = get_config()
        openai.api_key = self.config.api.openai_key
        self.model = self.config.api.openai_model
        self.max_tokens = self.config.api.openai_max_tokens
        self.temperature = self.config.api.openai_temperature
        logger.info(f"GPT Analyzer initialized with model: {self.model}")

    async def analyze_market(self, market_data: Dict, news_sentiment: Dict) -> Dict:
        """Analyze overall market conditions"""
        prompt = self._build_market_analysis_prompt(market_data, news_sentiment)
        
        try:
            response = await self._call_gpt(prompt)
            analysis = self._parse_market_analysis(response)
            return analysis
        except Exception as e:
            logger.error(f"GPT market analysis failed: {e}")
            return {}

    async def analyze_stock(self, symbol: str, data: Dict, news: List) -> Dict:
        """Analyze specific stock"""
        prompt = self._build_stock_analysis_prompt(symbol, data, news)
        
        try:
            response = await self._call_gpt(prompt)
            analysis = self._parse_stock_analysis(response)
            return analysis
        except Exception as e:
            logger.error(f"GPT stock analysis failed for {symbol}: {e}")
            return {}

    async def generate_trading_idea(self, market_data: Dict) -> Dict:
        """Generate trading ideas"""
        prompt = f"""As an expert trader, analyze the following market data and suggest trading opportunities:
        
Market Data: {market_data}

Provide:
1. Top 3 stocks to buy with reasons
2. Risk assessment
3. Position sizing recommendations
4. Entry/exit strategies

Be concise and data-driven."""

        try:
            response = await self._call_gpt(prompt)
            return {"idea": response, "timestamp": datetime.now()}
        except Exception as e:
            logger.error(f"Trading idea generation failed: {e}")
            return {}

    async def explain_anomaly(self, symbol: str, anomaly_data: Dict) -> str:
        """Explain unusual price movements"""
        prompt = f"""Explain this unusual price movement for {symbol}:
        
Anomaly Data: {anomaly_data}

Provide possible explanations based on market dynamics, news, or technical factors."""

        try:
            response = await self._call_gpt(prompt)
            return response
        except Exception as e:
            logger.error(f"Anomaly explanation failed: {e}")
            return "Unable to explain anomaly"

    async def _call_gpt(self, prompt: str) -> str:
        """Call GPT API"""
        import asyncio
        
        # Simulate API call (replace with actual OpenAI call in production)
        await asyncio.sleep(0.1)
        
        # In production:
        # response = openai.ChatCompletion.create(
        #     model=self.model,
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=self.max_tokens,
        #     temperature=self.temperature
        # )
        # return response.choices[0].message.content
        
        return "Market analysis placeholder response"

    def _build_market_analysis_prompt(self, market_data: Dict, news_sentiment: Dict) -> str:
        """Build prompt for market analysis"""
        prompt = f"""Analyze current market conditions:

Market Data Summary:
- SPY Movement: {market_data.get('spy_change', 0)}%
- VIX Level: {market_data.get('vix', 20)}
- Sector Performance: {market_data.get('sectors', {})}

News Sentiment:
- Overall Sentiment: {news_sentiment.get('market', {}).get('compound', 0)}
- Key Events: {news_sentiment.get('events', [])}

Provide:
1. Market regime (bullish/bearish/neutral)
2. Key risks and opportunities
3. Recommended sectors
4. Overall trading strategy"""

        return prompt

    def _build_stock_analysis_prompt(self, symbol: str, data: Dict, news: List) -> str:
        """Build prompt for stock analysis"""
        news_summary = '; '.join([n.get('title', '') for n in news[:5]])
        
        prompt = f"""Analyze {symbol}:

Technical Data:
- Price: ${data.get('price', 0)}
- Change: {data.get('change_pct', 0)}%
- Volume: {data.get('volume', 0)}
- RSI: {data.get('rsi', 50)}
- MACD: {data.get('macd', 0)}

Recent News:
{news_summary}

Provide trading recommendation (buy/sell/hold) with reasoning."""

        return prompt

    def _parse_market_analysis(self, response: str) -> Dict:
        """Parse GPT response into structured data"""
        # Simplified parsing - in production, use more robust parsing
        return {
            "analysis": response,
            "timestamp": datetime.now(),
            "confidence": 0.7,  # Placeholder
            "regime": "neutral"  # Placeholder
        }

    def _parse_stock_analysis(self, response: str) -> Dict:
        """Parse stock analysis response"""
        return {
            "recommendation": "hold",  # Placeholder
            "reasoning": response,
            "confidence": 0.6,
            "timestamp": datetime.now()
        }
