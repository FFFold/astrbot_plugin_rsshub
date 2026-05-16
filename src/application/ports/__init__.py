"""Application ports used by use cases.

Ports live in the application layer. Infrastructure modules provide adapters
for these protocols at composition time.
"""

from .clock import Clock, SystemClock
from .feed_fetcher import FeedFetcher, FeedFetcherFactory
from .feed_parser import FeedParser
from .message_sender import (
    MessageContext,
    MessageSender,
    MessageSenderProvider,
    SendRequest,
    SendResult,
)

__all__ = [
    "Clock",
    "FeedFetcher",
    "FeedFetcherFactory",
    "FeedParser",
    "MessageContext",
    "MessageSender",
    "MessageSenderProvider",
    "SendRequest",
    "SendResult",
    "SystemClock",
]
