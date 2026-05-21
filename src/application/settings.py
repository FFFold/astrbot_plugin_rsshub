"""Compatibility exports for runtime settings.

Runtime settings are defined in ``src.shared.settings``. This module remains as
a stable import path for existing application code and tests.
"""

from __future__ import annotations

from ..shared.settings import (
    ApplicationSettings,
    BasicSettings,
    FeedFetchSettings,
    PlatformStrategySettings,
    RouteKnowledgeSettings,
    RSSSettings,
    SchedulerSettings,
    SenderStrategySettings,
    SubscriptionDefaults,
)

__all__ = [
    "ApplicationSettings",
    "BasicSettings",
    "FeedFetchSettings",
    "PlatformStrategySettings",
    "RSSSettings",
    "RouteKnowledgeSettings",
    "SchedulerSettings",
    "SenderStrategySettings",
    "SubscriptionDefaults",
]
