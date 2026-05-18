"""Adapt AstrBot plugin config into application settings."""

from __future__ import annotations

from typing import Any

from ...application.settings import (
    ApplicationSettings,
    BasicSettings,
    FeedFetchSettings,
    PipelineSettings,
    RSSSettings,
    SchedulerSettings,
    SenderStrategySettings,
    SubscriptionDefaults,
)


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = value.replace(",", "\n").splitlines()
        return tuple(part.strip() for part in parts if part.strip())
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def build_application_settings(config: Any) -> ApplicationSettings:
    """Build application settings from an infrastructure config object.

    This is the adapter between the AstrBot-facing Pydantic config model and the
    application-layer dataclasses. Keep AstrBot compatibility parsing here, not
    in ``src.application.settings``.
    """
    basic_cfg = _get_value(config, "basic_config")
    global_cfg = _get_value(config, "global_config")
    pipeline_cfg = _get_value(config, "pipeline")
    sender_cfg = _get_value(config, "sender_strategies")

    basic = BasicSettings(
        proxy=str(_get_value(basic_cfg, "proxy", _get_value(config, "proxy", "")) or ""),
        timeout=int(
            _get_value(basic_cfg, "timeout", _get_value(config, "timeout", 30)) or 30
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

    pipeline = PipelineSettings(
        keyword_blacklist=_as_tuple(_get_value(pipeline_cfg, "keyword_blacklist", ())),
        keyword_whitelist=_as_tuple(_get_value(pipeline_cfg, "keyword_whitelist", ())),
        min_content_length=max(
            0, int(_get_value(pipeline_cfg, "min_content_length", 0) or 0)
        ),
        min_media_count=max(
            0, int(_get_value(pipeline_cfg, "min_media_count", 0) or 0)
        ),
        ai_filter_enabled=bool(_get_value(pipeline_cfg, "ai_filter_enabled", False)),
        ai_filter_prompt=str(_get_value(pipeline_cfg, "ai_filter_prompt", "") or ""),
        ai_enrich_enabled=bool(_get_value(pipeline_cfg, "ai_enrich_enabled", False)),
        ai_enrich_prompt=str(_get_value(pipeline_cfg, "ai_enrich_prompt", "") or ""),
        ai_timeout_seconds=max(
            1, int(_get_value(pipeline_cfg, "ai_timeout_seconds", 15) or 15)
        ),
    )

    return ApplicationSettings(
        basic=basic,
        fetch=FeedFetchSettings(
            timeout=basic.timeout,
            proxy=basic.proxy,
            rsshub_base_url=basic.rsshub_base_url,
        ),
        rss=RSSSettings(
            hash_history_min=int(_get_value(basic_cfg, "hash_history_min", 200) or 200),
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
            link_preview=str(_get_value(global_cfg, "link_preview", "自动") or "自动"),
            display_author=str(
                _get_value(global_cfg, "display_author", "自动") or "自动"
            ),
            display_via=str(_get_value(global_cfg, "display_via", "自动") or "自动"),
            display_title=str(_get_value(global_cfg, "display_title", "自动") or "自动"),
            display_entry_tags=bool(
                _get_value(global_cfg, "display_entry_tags", False)
            ),
            style=str(_get_value(global_cfg, "style", "RSStT") or "RSStT"),
            display_media=bool(_get_value(global_cfg, "display_media", True)),
        ),
        pipeline=pipeline,
        sender_strategies=SenderStrategySettings(
            telegram=bool(_get_value(sender_cfg, "telegram", True)),
            aiocqhttp=bool(_get_value(sender_cfg, "aiocqhttp", True)),
            qq_official=bool(_get_value(sender_cfg, "qq_official", True)),
            weixin_oc=bool(_get_value(sender_cfg, "weixin_oc", True)),
        ),
    )
