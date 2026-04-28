"""RSS 服务包

提供 RSS 抓取、解析和自动发现功能。
"""

from ...application.dto import WebFeed
from .feed_discoverer import FeedDiscoverer, FeedDiscoveryResult
from .rss_fetcher import RSSFeedFetcher
from .rss_parser import Enclosure, EntryParsed, RSSParser

__all__ = [
    "WebFeed",
    "RSSFeedFetcher",
    "RSSParser",
    "EntryParsed",
    "Enclosure",
    "FeedDiscoverer",
    "FeedDiscoveryResult",
]
