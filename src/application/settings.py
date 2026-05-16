"""Application-level settings.

This module contains configuration values after infrastructure-specific config
loading has already happened. Application services and commands may depend on
these dataclasses without importing the AstrBot config adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _get_nested(source: Any, key: str) -> Any:
    return _get_value(source, key)


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
    translate: bool = False
    translate_target_lang: str = "zh-CN"


@dataclass(frozen=True)
class BaiduTranslationSettings:
    """Baidu Translate credentials."""

    app_id: str = ""
    secret_key: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.secret_key)


@dataclass(frozen=True)
class TranslationSettings:
    """Traditional translation settings."""

    provider: str = "google"
    target_lang: str = "zh-CN"
    auto_translate: bool = False
    force_translate: bool = False
    translate_title: bool = True
    translate_content: bool = True
    display_original_content: bool = False
    cache_translations: bool = True
    google_translate_api_key: str = ""
    baidu: BaiduTranslationSettings = field(default_factory=BaiduTranslationSettings)


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
    translation: TranslationSettings = field(default_factory=TranslationSettings)
    baidu: BaiduTranslationSettings = field(default_factory=BaiduTranslationSettings)
    sender_strategies: SenderStrategySettings = field(
        default_factory=SenderStrategySettings
    )

    @classmethod
    def from_config(cls, config: Any) -> ApplicationSettings:
        """Build application settings from any config-like object.

        `config` is intentionally typed as `Any` so this module does not import
        the infrastructure config adapter.
        """
        basic_cfg = _get_nested(config, "basic_config")
        global_cfg = _get_nested(config, "global_config")
        trans_cfg = _get_nested(config, "translation")
        sender_cfg = _get_nested(config, "sender_strategies")
        baidu_cfg = _get_nested(config, "baidu_translate")

        basic = BasicSettings(
            proxy=str(
                _get_value(basic_cfg, "proxy", _get_value(config, "proxy", "")) or ""
            ),
            timeout=int(
                _get_value(basic_cfg, "timeout", _get_value(config, "timeout", 30))
                or 30
            ),
            rsshub_base_url=str(
                _get_value(
                    basic_cfg,
                    "rsshub_base_url",
                    _get_value(config, "rsshub_base_url", "https://rsshub.app"),
                )
                or "https://rsshub.app"
            ),
            minimal_interval=int(
                _get_value(
                    basic_cfg,
                    "minimal_interval",
                    _get_value(config, "minimal_interval", 1),
                )
                or 1
            ),
            history_entry_limit=int(
                _get_value(
                    basic_cfg,
                    "history_entry_limit",
                    _get_value(config, "history_entry_limit", 0),
                )
                or 0
            ),
            download_media_before_send=bool(
                _get_value(
                    basic_cfg,
                    "download_media_before_send",
                    _get_value(config, "download_media_before_send", False),
                )
            ),
            download_media_timeout=int(
                _get_value(
                    basic_cfg,
                    "download_media_timeout",
                    _get_value(config, "download_media_timeout", 30),
                )
                or 30
            ),
        )

        baidu = BaiduTranslationSettings(
            app_id=str(
                _get_value(
                    baidu_cfg,
                    "app_id",
                    _get_value(trans_cfg, "baidu_translate_app_id", ""),
                )
                or ""
            ),
            secret_key=str(
                _get_value(
                    baidu_cfg,
                    "secret_key",
                    _get_value(trans_cfg, "baidu_translate_secret_key", ""),
                )
                or ""
            ),
        )

        translation = TranslationSettings(
            provider=str(_get_value(trans_cfg, "provider", "google") or "google"),
            target_lang=str(_get_value(trans_cfg, "target_lang", "zh-CN") or "zh-CN"),
            auto_translate=bool(_get_value(trans_cfg, "auto_translate", False)),
            force_translate=bool(_get_value(trans_cfg, "force_translate", False)),
            translate_title=bool(_get_value(trans_cfg, "translate_title", True)),
            translate_content=bool(_get_value(trans_cfg, "translate_content", True)),
            display_original_content=bool(
                _get_value(trans_cfg, "display_original_content", False)
            ),
            cache_translations=bool(_get_value(trans_cfg, "cache_translations", True)),
            google_translate_api_key=str(
                _get_value(trans_cfg, "google_translate_api_key", "") or ""
            ),
            baidu=baidu,
        )

        return cls(
            basic=basic,
            fetch=FeedFetchSettings(
                timeout=basic.timeout,
                proxy=basic.proxy,
                rsshub_base_url=basic.rsshub_base_url,
            ),
            rss=RSSSettings(
                hash_history_min=int(
                    _get_value(basic_cfg, "hash_history_min", 200) or 200
                ),
                hash_history_multiplier=int(
                    _get_value(basic_cfg, "hash_history_multiplier", 2) or 2
                ),
                hash_history_hard_limit=int(
                    _get_value(basic_cfg, "hash_history_hard_limit", 5000) or 5000
                ),
                tracking_query_params=tuple(
                    _get_value(basic_cfg, "tracking_query_params", []) or []
                ),
                bootstrap_skip_history=bool(
                    _get_value(basic_cfg, "bootstrap_skip_history", True)
                ),
            ),
            scheduler=SchedulerSettings(
                default_interval=int(_get_value(global_cfg, "interval", 10) or 10),
                history_entry_limit=basic.history_entry_limit,
            ),
            subscription_defaults=SubscriptionDefaults(
                interval=int(_get_value(global_cfg, "interval", 10) or 10),
                notify=bool(_get_value(global_cfg, "notify", True)),
                send_mode=str(_get_value(global_cfg, "send_mode", "自动") or "自动"),
                length_limit=int(_get_value(global_cfg, "length_limit", 0) or 0),
                link_preview=str(
                    _get_value(global_cfg, "link_preview", "自动") or "自动"
                ),
                display_author=str(
                    _get_value(global_cfg, "display_author", "自动") or "自动"
                ),
                display_via=str(
                    _get_value(global_cfg, "display_via", "自动") or "自动"
                ),
                display_title=str(
                    _get_value(global_cfg, "display_title", "自动") or "自动"
                ),
                display_entry_tags=bool(
                    _get_value(global_cfg, "display_entry_tags", False)
                ),
                style=str(_get_value(global_cfg, "style", "RSStT") or "RSStT"),
                display_media=bool(_get_value(global_cfg, "display_media", True)),
                translate=bool(_get_value(global_cfg, "translate", False)),
                translate_target_lang=str(
                    _get_value(global_cfg, "translate_target_lang", "zh-CN") or "zh-CN"
                ),
            ),
            translation=translation,
            baidu=baidu,
            sender_strategies=SenderStrategySettings(
                telegram=bool(_get_value(sender_cfg, "telegram", True)),
                aiocqhttp=bool(_get_value(sender_cfg, "aiocqhttp", True)),
                qq_official=bool(_get_value(sender_cfg, "qq_official", True)),
                weixin_oc=bool(_get_value(sender_cfg, "weixin_oc", True)),
            ),
        )
