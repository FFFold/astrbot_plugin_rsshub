"""应用层包"""

from .commands import (
    RefreshFeedCommand,
    SubscribeFeedCommand,
    UnsubscribeFeedCommand,
    UpdateSubscriptionCommand,
)
from .dto import CommandResult, FeedDTO, ItemDTO, SubscriptionDTO
from .queries import (
    FeedItemsResult,
    FeedListResult,
    GetFeedItemsQuery,
    GetFeedListQuery,
    GetSubscriptionsQuery,
    SearchFeedsQuery,
    SearchFeedsResult,
    SubscriptionsResult,
)
from .services import FeedSyncService, NotificationDispatcher

__all__ = [
    # Commands
    "RefreshFeedCommand",
    "SubscribeFeedCommand",
    "UnsubscribeFeedCommand",
    "UpdateSubscriptionCommand",
    # Queries
    "GetFeedListQuery",
    "GetFeedItemsQuery",
    "GetSubscriptionsQuery",
    "SearchFeedsQuery",
    # Query Results
    "FeedListResult",
    "FeedItemsResult",
    "SubscriptionsResult",
    "SearchFeedsResult",
    # DTOs
    "CommandResult",
    "FeedDTO",
    "ItemDTO",
    "SubscriptionDTO",
    # Services
    "FeedSyncService",
    "NotificationDispatcher",
]
