"""
News Collector
Collects financial news from multiple sources for sentiment and event analysis
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import feedparser
from newspaper import Article
from loguru import logger

from src.utils.config import get_config


@dataclass
class NewsArticle:
    """News article data structure"""

    title: str
    content: str
    summary: str
    url: str
    source: str
    published_date: datetime
    symbols: List[str]
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None


class NewsCollector:
    """Collects news from multiple sources"""

    def __init__(self):
        self.config = get_config()
        self.news_api_key = self.config.api.news_api_key

        # News sources
        self.rss_feeds = {
            "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
            "Reuters Business": "https://www.reedssews.com/finance",
            "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "Bloomberg": "https://www.bloomberg.com/feed/podcast/etf-report",
            "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
            "Seeking Alpha": "https://seekingalpha.com/feed.xml",
        }

    def get_news_for_symbol(
        self, symbol: str, days_back: int = 7, max_articles: int = 50
    ) -> List[NewsArticle]:
        """
        Get news articles for a specific symbol

        Args:
            symbol: Stock symbol
            days_back: Number of days to look back
            max_articles: Maximum number of articles to return

        Returns:
            List of NewsArticle objects
        """
        articles = []

        # Method 1: News API
        if self.news_api_key:
            articles.extend(
                self._fetch_from_news_api(symbol, days_back, max_articles)
            )

        # Method 2: Yahoo Finance
        articles.extend(self._fetch_from_yahoo(symbol, max_articles))

        # Method 3: Finnhub
        articles.extend(self._fetch_from_finnhub(symbol, days_back))

        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # Sort by date (newest first)
        unique_articles.sort(key=lambda x: x.published_date, reverse=True)

        return unique_articles[:max_articles]

    def get_market_news(self, max_articles: int = 100) -> List[NewsArticle]:
        """
        Get general market news

        Args:
            max_articles: Maximum number of articles

        Returns:
            List of NewsArticle objects
        """
        articles = []

        # Fetch from RSS feeds
        for source, feed_url in self.rss_feeds.items():
            try:
                feed_articles = self._fetch_from_rss(feed_url, source)
                articles.extend(feed_articles)
            except Exception as e:
                logger.error(f"Error fetching from {source}: {e}")

        # Sort by date
        articles.sort(key=lambda x: x.published_date, reverse=True)

        return articles[:max_articles]

    def _fetch_from_news_api(
        self, symbol: str, days_back: int, max_articles: int
    ) -> List[NewsArticle]:
        """Fetch news from NewsAPI.org"""
        articles = []

        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f"{symbol} OR stock OR shares",
                "from": (datetime.now() - timedelta(days=days_back)).strftime(
                    "%Y-%m-%d"
                ),
                "sortBy": "publishedAt",
                "apiKey": self.news_api_key,
                "language": "en",
                "pageSize": min(max_articles, 100),
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            for item in data.get("articles", []):
                article = NewsArticle(
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    summary=item.get("description", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "Unknown"),
                    published_date=datetime.strptime(
                        item.get("publishedAt", ""),
                        "%Y-%m-%dT%H:%M:%SZ",
                    ),
                    symbols=[symbol],
                )
                articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching from NewsAPI: {e}")

        return articles

    def _fetch_from_yahoo(
        self, symbol: str, max_articles: int
    ) -> List[NewsArticle]:
        """Fetch news from Yahoo Finance"""
        articles = []

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            news = ticker.news

            for item in news[:max_articles]:
                article = NewsArticle(
                    title=item.get("title", ""),
                    content="",
                    summary=item.get("summary", ""),
                    url=item.get("link", ""),
                    source=item.get("publisher", "Yahoo Finance"),
                    published_date=datetime.fromtimestamp(
                        item.get("providerPublishTime", 0)
                    ),
                    symbols=[symbol],
                )
                articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching from Yahoo Finance: {e}")

        return articles

    def _fetch_from_finnhub(
        self, symbol: str, days_back: int
    ) -> List[NewsArticle]:
        """Fetch news from Finnhub"""
        articles = []

        if not self.config.api.finnhub_key:
            return articles

        try:
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": symbol,
                "from": (datetime.now() - timedelta(days=days_back)).strftime(
                    "%Y-%m-%d"
                ),
                "to": datetime.now().strftime("%Y-%m-%d"),
                "token": self.config.api.finnhub_key,
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            for item in data:
                article = NewsArticle(
                    title=item.get("headline", ""),
                    content=item.get("summary", ""),
                    summary=item.get("summary", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "Finnhub"),
                    published_date=datetime.fromtimestamp(
                        item.get("datetime", 0)
                    ),
                    symbols=[symbol],
                )
                articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching from Finnhub: {e}")

        return articles

    def _fetch_from_rss(
        self, feed_url: str, source: str
    ) -> List[NewsArticle]:
        """Fetch news from RSS feed"""
        articles = []

        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:50]:
                published_date = datetime.now()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6])

                article = NewsArticle(
                    title=entry.get("title", ""),
                    content=entry.get("summary", ""),
                    summary=entry.get("summary", "")[:500],
                    url=entry.get("link", ""),
                    source=source,
                    published_date=published_date,
                    symbols=[],
                )
                articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching RSS from {source}: {e}")

        return articles

    def extract_full_article(self, url: str) -> Optional[str]:
        """
        Extract full article text from URL

        Args:
            url: Article URL

        Returns:
            Full article text or None
        """
        try:
            article = Article(url)
            article.download()
            article.parse()

            return article.text

        except Exception as e:
            logger.error(f"Error extracting article from {url}: {e}")
            return None

    def extract_mentioned_symbols(self, text: str) -> List[str]:
        """
        Extract stock symbols mentioned in text

        Args:
            text: Text to analyze

        Returns:
            List of symbols found
        """
        import re

        # Pattern to match stock symbols (simplified)
        pattern = r"\$([A-Z]{1,5})\b"
        symbols = re.findall(pattern, text)

        # Also look for explicit mentions like "Apple (AAPL)"
        pattern2 = r"\(([A-Z]{1,5})\)"
        symbols.extend(re.findall(pattern2, text))

        return list(set(symbols))
