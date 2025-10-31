"""
Sentiment Analyzer
Analyzes sentiment of news, social media, and other text data
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime
from loguru import logger

# NLP libraries
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as VaderAnalyzer

from src.utils.config import get_config


@dataclass
class SentimentScore:
    """Sentiment score data structure"""

    text: str
    compound: float  # Overall sentiment (-1 to 1)
    positive: float  # Positive score (0 to 1)
    negative: float  # Negative score (0 to 1)
    neutral: float  # Neutral score (0 to 1)
    subjectivity: float  # Subjectivity (0 to 1)
    confidence: float  # Confidence in the score (0 to 1)
    timestamp: datetime
    source: str = "combined"


class SentimentCollector:
    """Collects and analyzes sentiment from various sources"""

    def __init__(self):
        self.config = get_config()

        # Initialize sentiment analyzers
        self._init_analyzers()

    def _init_analyzers(self):
        """Initialize sentiment analysis tools"""
        try:
            # Download required NLTK data
            try:
                nltk.data.find("vader_lexicon")
            except LookupError:
                nltk.download("vader_lexicon", quiet=True)

            # Initialize analyzers
            self.vader = VaderAnalyzer()
            self.nltk_sia = SentimentIntensityAnalyzer()

            logger.info("Sentiment analyzers initialized")

        except Exception as e:
            logger.error(f"Error initializing sentiment analyzers: {e}")

    def analyze_text(self, text: str) -> SentimentScore:
        """
        Analyze sentiment of text using multiple methods

        Args:
            text: Text to analyze

        Returns:
            SentimentScore object
        """
        # VADER sentiment
        vader_scores = self.vader.polarity_scores(text)

        # TextBlob sentiment
        blob = TextBlob(text)
        textblob_polarity = blob.sentiment.polarity
        textblob_subjectivity = blob.sentiment.subjectivity

        # Combine scores (weighted average)
        compound = (vader_scores["compound"] + textblob_polarity) / 2
        positive = vader_scores["pos"]
        negative = vader_scores["neg"]
        neutral = vader_scores["neu"]

        # Calculate confidence based on agreement
        confidence = 1 - abs(vader_scores["compound"] - textblob_polarity)

        score = SentimentScore(
            text=text[:200],  # Store first 200 chars
            compound=compound,
            positive=positive,
            negative=negative,
            neutral=neutral,
            subjectivity=textblob_subjectivity,
            confidence=confidence,
            timestamp=datetime.now(),
        )

        return score

    def analyze_news_article(self, title: str, content: str) -> SentimentScore:
        """
        Analyze sentiment of news article

        Args:
            title: Article title
            content: Article content

        Returns:
            SentimentScore object
        """
        # Weight title more heavily
        combined_text = f"{title} {title} {content}"

        return self.analyze_text(combined_text)

    def get_market_sentiment(
        self, news_articles: List[Dict], window_hours: int = 24
    ) -> Dict[str, float]:
        """
        Calculate overall market sentiment from news

        Args:
            news_articles: List of news articles
            window_hours: Time window in hours

        Returns:
            Dictionary with aggregated sentiment metrics
        """
        if not news_articles:
            return {
                "compound": 0.0,
                "positive": 0.5,
                "negative": 0.5,
                "neutral": 0.0,
                "article_count": 0,
            }

        scores = []
        for article in news_articles:
            text = f"{article.get('title', '')} {article.get('content', '')}"
            score = self.analyze_text(text)
            scores.append(score)

        # Aggregate scores
        if not scores:
            return {
                "compound": 0.0,
                "positive": 0.5,
                "negative": 0.5,
                "neutral": 0.0,
                "article_count": 0,
            }

        return {
            "compound": np.mean([s.compound for s in scores]),
            "positive": np.mean([s.positive for s in scores]),
            "negative": np.mean([s.negative for s in scores]),
            "neutral": np.mean([s.neutral for s in scores]),
            "subjectivity": np.mean([s.subjectivity for s in scores]),
            "confidence": np.mean([s.confidence for s in scores]),
            "article_count": len(scores),
        }

    def get_symbol_sentiment(
        self, symbol: str, news_articles: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate sentiment for a specific symbol

        Args:
            symbol: Stock symbol
            news_articles: List of news articles

        Returns:
            Dictionary with sentiment metrics
        """
        # Filter articles mentioning the symbol
        relevant_articles = [
            article
            for article in news_articles
            if symbol in article.get("symbols", [])
            or symbol.lower() in article.get("title", "").lower()
            or symbol.lower() in article.get("content", "").lower()
        ]

        return self.get_market_sentiment(relevant_articles)

    def calculate_sentiment_momentum(
        self, sentiment_history: List[float], window: int = 5
    ) -> float:
        """
        Calculate sentiment momentum (rate of change)

        Args:
            sentiment_history: List of historical sentiment scores
            window: Window for momentum calculation

        Returns:
            Sentiment momentum value
        """
        if len(sentiment_history) < window:
            return 0.0

        recent = sentiment_history[-window:]
        older = sentiment_history[-window * 2 : -window] if len(
            sentiment_history
        ) >= window * 2 else sentiment_history[:-window]

        if not older:
            return 0.0

        recent_avg = np.mean(recent)
        older_avg = np.mean(older)

        momentum = recent_avg - older_avg

        return momentum

    def detect_sentiment_shift(
        self, sentiment_history: List[float], threshold: float = 0.3
    ) -> Optional[str]:
        """
        Detect significant sentiment shifts

        Args:
            sentiment_history: List of historical sentiment scores
            threshold: Threshold for detecting shifts

        Returns:
            'bullish', 'bearish', or None
        """
        if len(sentiment_history) < 10:
            return None

        recent_avg = np.mean(sentiment_history[-5:])
        older_avg = np.mean(sentiment_history[-10:-5])

        change = recent_avg - older_avg

        if change > threshold:
            return "bullish"
        elif change < -threshold:
            return "bearish"
        else:
            return None

    def analyze_social_media(
        self, tweets: List[str]
    ) -> Dict[str, float]:
        """
        Analyze sentiment from social media posts

        Args:
            tweets: List of tweets/posts

        Returns:
            Aggregated sentiment metrics
        """
        if not tweets:
            return {
                "compound": 0.0,
                "positive": 0.5,
                "negative": 0.5,
                "post_count": 0,
            }

        scores = [self.analyze_text(tweet) for tweet in tweets]

        return {
            "compound": np.mean([s.compound for s in scores]),
            "positive": np.mean([s.positive for s in scores]),
            "negative": np.mean([s.negative for s in scores]),
            "neutral": np.mean([s.neutral for s in scores]),
            "post_count": len(scores),
        }

    def get_fear_greed_index(
        self, market_data: Dict, news_sentiment: float
    ) -> float:
        """
        Calculate custom Fear & Greed Index

        Args:
            market_data: Dictionary with market indicators
            news_sentiment: News sentiment score

        Returns:
            Fear & Greed score (0-100)
        """
        # Components of the index
        components = []

        # 1. News sentiment (0-100)
        news_component = (news_sentiment + 1) * 50  # Convert -1,1 to 0,100
        components.append(news_component)

        # 2. Market momentum (if available)
        if "momentum" in market_data:
            momentum = market_data["momentum"]
            momentum_component = (momentum + 1) * 50
            components.append(momentum_component)

        # 3. Volatility (if available)
        if "volatility" in market_data:
            volatility = market_data["volatility"]
            # Lower volatility = more greed
            vol_component = max(0, 100 - volatility * 100)
            components.append(vol_component)

        # 4. Put/Call ratio (if available)
        if "put_call_ratio" in market_data:
            pcr = market_data["put_call_ratio"]
            # Lower put/call = more greed
            pcr_component = max(0, 100 - pcr * 100)
            components.append(pcr_component)

        # Average all components
        if components:
            fear_greed = np.mean(components)
        else:
            fear_greed = 50.0

        return np.clip(fear_greed, 0, 100)
