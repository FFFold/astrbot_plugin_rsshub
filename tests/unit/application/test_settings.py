"""Application settings tests."""

from __future__ import annotations


def test_application_settings_maps_fetch_and_translation_config():
    from astrbot_plugin_rsshub.src.application.settings import ApplicationSettings
    from astrbot_plugin_rsshub.src.infrastructure.config.config_manager import (
        RsshubPluginConfig,
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
        }
    )

    settings = ApplicationSettings.from_config(config)

    assert settings.fetch.timeout == 12
    assert settings.fetch.proxy == "http://proxy.local"
    assert settings.fetch.rsshub_base_url == "https://rss.example.test"
    assert settings.scheduler.default_interval == 15
    assert settings.subscription_defaults.translate is True
    assert settings.translation.provider == "baidu"
    assert settings.translation.display_original_content is True
    assert settings.translation.cache_translations is False
    assert settings.translation.baidu.app_id == "app-id"
    assert settings.translation.baidu.secret_key == "secret"
    assert settings.baidu.app_id == "app-id"
    assert settings.baidu.secret_key == "secret"


def test_config_extracts_baidu_credentials_from_legacy_template():
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

    assert config.translation.baidu_translate_app_id == "legacy-app-id"
    assert config.translation.baidu_translate_secret_key == "legacy-secret"
    assert config.baidu_translate.app_id == "legacy-app-id"
    assert config.baidu_translate.secret_key == "legacy-secret"
