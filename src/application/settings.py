"""Application-level settings.

This module contains configuration values after infrastructure-specific config
loading has already happened. Application services and commands may depend on
these dataclasses without importing the AstrBot config adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BasicSettings:
    """Global infrastructure-facing defaults used by application use cases."""

    proxy: str = ""
    timeout: int = 30
    rsshub_base_url: str = "https://rsshub.app"
    minimal_interval: int = 1
    history_entry_limit: int = 0
    download_media_before_send: bool = False
    download_media_timeout: int = 30


@dataclass(frozen=True)
class FeedFetchSettings:
    """HTTP/RSS fetch defaults."""

    timeout: int = 30
    proxy: str = ""
    rsshub_base_url: str = "https://rsshub.app"


@dataclass(frozen=True)
class RSSSettings:
    """RSS parser and dedup history settings."""

    hash_history_min: int = 200
    hash_history_multiplier: int = 2
    hash_history_hard_limit: int = 5000
    tracking_query_params: tuple[str, ...] = field(default_factory=tuple)
    bootstrap_skip_history: bool = True


@dataclass(frozen=True)
class SchedulerSettings:
    """Scheduler defaults."""

    default_interval: int = 10
    history_retention_days: int = 30
    history_entry_limit: int = 0


@dataclass(frozen=True)
class SubscriptionDefaults:
    """Default values applied to new subscriptions."""

    interval: int = 10
    notify: bool = True
    send_mode: str = "自动"
    length_limit: int = 0
    link_preview: str = "自动"
    display_author: str = "自动"
    display_via: str = "自动"
    display_title: str = "自动"
    display_entry_tags: bool = False
    style: str = "RSStT"
    display_media: bool = True


@dataclass(frozen=True)
class PipelineSettings:
    """Content filtering and enrichment pipeline settings."""

    keyword_blacklist: tuple[str, ...] = field(default_factory=tuple)
    keyword_whitelist: tuple[str, ...] = field(default_factory=tuple)
    min_content_length: int = 0
    min_media_count: int = 0
    ai_filter_enabled: bool = False
    ai_filter_prompt: str = ""
    ai_enrich_enabled: bool = False
    ai_enrich_prompt: str = ""
    ai_timeout_seconds: int = 15


@dataclass(frozen=True)
class SenderStrategySettings:
    """Per-platform sender strategy toggles."""

    telegram: bool = True
    aiocqhttp: bool = True
    qq_official: bool = True
    weixin_oc: bool = True


@dataclass(frozen=True)
class ApplicationSettings:
    """Settings consumed by the application layer."""

    basic: BasicSettings = field(default_factory=BasicSettings)
    fetch: FeedFetchSettings = field(default_factory=FeedFetchSettings)
    rss: RSSSettings = field(default_factory=RSSSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    subscription_defaults: SubscriptionDefaults = field(
        default_factory=SubscriptionDefaults
    )
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    sender_strategies: SenderStrategySettings = field(
        default_factory=SenderStrategySettings
    )
