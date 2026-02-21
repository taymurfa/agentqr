"""News and RSS feed scraper for market news."""

import re
import httpx
import feedparser
from typing import Optional
from datetime import datetime
from bs4 import BeautifulSoup
from dataclasses import dataclass


@dataclass
class NewsArticle:
    title: str
    content: str
    source: str
    url: str
    published_date: str
    ticker: Optional[str] = None


class NewsFeedClient:
    """Scrapes financial news from RSS feeds and web sources."""

    RSS_FEEDS = {
        "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
        "seeking_alpha": "https://seekingalpha.com/market_currents.xml",
        "reuters_business": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
        "marketwatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
    }

    TICKER_RSS_TEMPLATE = {
        "yahoo": "https://finance.yahoo.com/rss/headline?s={ticker}",
        "google_news": "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en",
    }

    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (compatible; QuantResearcher/1.0)"},
            timeout=30,
            follow_redirects=True,
        )

    def fetch_feed(self, feed_url: str, max_items: int = 20) -> list[NewsArticle]:
        """Fetch and parse an RSS feed."""
        try:
            resp = self.client.get(feed_url)
            feed = feedparser.parse(resp.text)
        except Exception:
            return []

        articles = []
        for entry in feed.entries[:max_items]:
            content = entry.get("summary", "") or entry.get("description", "")
            content = self._clean_html(content)

            published = entry.get("published", "") or entry.get("updated", "")

            articles.append(NewsArticle(
                title=entry.get("title", ""),
                content=content,
                source=feed.feed.get("title", "Unknown"),
                url=entry.get("link", ""),
                published_date=published,
            ))

        return articles

    def fetch_ticker_news(self, ticker: str, max_items: int = 20) -> list[NewsArticle]:
        """Fetch news specifically about a ticker."""
        articles = []
        for source, template in self.TICKER_RSS_TEMPLATE.items():
            url = template.format(ticker=ticker)
            feed_articles = self.fetch_feed(url, max_items=max_items)
            for article in feed_articles:
                article.ticker = ticker.upper()
            articles.extend(feed_articles)

        return articles[:max_items]

    def fetch_market_news(self, max_items: int = 50) -> list[NewsArticle]:
        """Fetch general market news from all configured feeds."""
        articles = []
        for name, url in self.RSS_FEEDS.items():
            feed_articles = self.fetch_feed(url, max_items=max_items // len(self.RSS_FEEDS))
            articles.extend(feed_articles)

        return articles[:max_items]

    def scrape_article(self, url: str) -> str:
        """Attempt to scrape full article content from a URL."""
        try:
            resp = self.client.get(url)
            soup = BeautifulSoup(resp.text, "lxml")

            for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            article_tag = soup.find("article") or soup.find("main") or soup.find("body")
            if article_tag:
                text = article_tag.get_text(separator="\n")
            else:
                text = soup.get_text(separator="\n")

            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            return text.strip()[:10000]

        except Exception:
            return ""

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from text."""
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator=" ").strip()
