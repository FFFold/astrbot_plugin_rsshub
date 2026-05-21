"""Neutral runtime settings models.

These dataclasses are the single source of truth for application runtime
configuration after infrastructure adapters have normalized raw AstrBot config.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformStrategySettings:
    """Platform-specific sender strategy settings."""

    enable_telegraph: bool = False
    telegraph_token: str = ""
    prefer_local_video: bool = False


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
    display_author: str = "自动"
    display_via: str = "自动"
    display_title: str = "自动"
    display_entry_tags: bool = False
    style: str = "RSStT"
    display_media: bool = True


@dataclass(frozen=True)
class SenderStrategySettings:
    """Per-platform sender strategy toggles."""

    telegram: bool = True
    aiocqhttp: bool = True
    qq_official: bool = True
    weixin_oc: bool = True
    telegram_settings: PlatformStrategySettings = field(
        default_factory=PlatformStrategySettings
    )
    aiocqhttp_settings: PlatformStrategySettings = field(
        default_factory=PlatformStrategySettings
    )


@dataclass(frozen=True)
class RouteKnowledgeSettings:
    """RSSHub Routes knowledge-base sync settings."""

    kb_name: str = "RSSHub Routes"
    embedding_provider_id: str = ""
    rerank_provider_id: str = ""
    source_mode: str = "mirror"
    source_base_url: str = (
        "https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main"
    )
    fallback_base_url: str = (
        "https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main"
    )
    local_source_dir: str = ""
    timeout: int = 30
    batch_size: int = 32
    tasks_limit: int = 3
    max_retries: int = 3


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
    sender_strategies: SenderStrategySettings = field(
        default_factory=SenderStrategySettings
    )
    route_knowledge: RouteKnowledgeSettings = field(
        default_factory=RouteKnowledgeSettings
    )

