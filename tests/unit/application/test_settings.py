"""Application settings tests."""

from __future__ import annotations


def test_application_settings_maps_fetch_and_pipeline_config():
    from astrbot_plugin_rsshub.src.infrastructure.config.config_manager import (
        RsshubPluginConfig,
    )
    from astrbot_plugin_rsshub.src.infrastructure.config.settings_adapter import (
        build_application_settings,
    )

    config = RsshubPluginConfig.from_astrbot_config(
        {
            "basic_config": {
                "timeout": 12,
                "proxy": "http://proxy.local",
                "rsshub_base_url": "https://rss.example.test",
            },
            "global_config": {
                "interval": 15,
                "translate": True,
            },
            "translation": {
                "provider": "baidu",
                "target_lang": "zh",
                "display_original": True,
                "cache_enabled": False,
                "baidu_translate_app_id": "app-id",
                "baidu_translate_secret_key": "secret",
            },
            "pipeline": {
                "keyword_blacklist": ["spam"],
                "min_content_length": 18,
                "min_media_count": 1,
                "ai_filter_enabled": True,
                "ai_filter_prompt": "keep only important entries",
                "ai_enrich_enabled": True,
                "ai_enrich_prompt": "summarize as json",
                "ai_timeout_seconds": 9,
                "translate_enabled": True,
                "translate_engine": "baidu",
                "translate_fallback_engine": "google",
                "translate_target_lang": "ja",
                "translate_mark_errors": True,
            },
        }
    )

    settings = build_application_settings(config)

    assert settings.fetch.timeout == 12
    assert settings.fetch.proxy == "http://proxy.local"
    assert settings.fetch.rsshub_base_url == "https://rss.example.test"
    assert settings.scheduler.default_interval == 15
    assert not hasattr(settings.subscription_defaults, "translate")
    assert not hasattr(settings, "translation")
    assert not hasattr(settings, "baidu")
    assert settings.pipeline.keyword_blacklist == ("spam",)
    assert settings.pipeline.min_content_length == 18
    assert settings.pipeline.min_media_count == 1
    assert settings.pipeline.ai_filter_enabled is True
    assert settings.pipeline.ai_filter_prompt == "keep only important entries"
    assert settings.pipeline.ai_enrich_enabled is True
    assert settings.pipeline.ai_enrich_prompt == "summarize as json"
    assert settings.pipeline.ai_timeout_seconds == 9
    assert not hasattr(settings.pipeline, "translate_enabled")
    assert not hasattr(settings.pipeline, "translate_target_lang")


def test_config_ignores_removed_translation_template_credentials():
    from astrbot_plugin_rsshub.src.infrastructure.config.config_manager import (
        RsshubPluginConfig,
    )

    config = RsshubPluginConfig.from_astrbot_config(
        {
            "translation": {
                "translation_template": [
                    {
                        "provider": "baidu",
                        "appid": "legacy-app-id",
                        "key": "legacy-secret",
                    }
                ]
            }
        }
    )

    assert not hasattr(config, "translation")
    assert not hasattr(config, "baidu_translate")
