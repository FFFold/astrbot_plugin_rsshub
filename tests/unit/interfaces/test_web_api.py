from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
    FeedPollingResult,
)
from astrbot_plugin_rsshub.src.infrastructure.config import RsshubPluginConfig
from astrbot_plugin_rsshub.src.interfaces.web_api import WebApiHandler
from quart import Quart


class _WritableConfig(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved = False

    def save_config(self):
        self.saved = True


def _handler(*, polling_service, config=None, raw_config=None, import_cmd=None):
    return WebApiHandler(
        subscribe_cmd=MagicMock(),
        unsubscribe_cmd=MagicMock(),
        update_sub_cmd=MagicMock(),
        batch_activate_cmd=MagicMock(),
        batch_deactivate_cmd=MagicMock(),
        batch_unsub_cmd=MagicMock(),
        export_cmd=MagicMock(),
        import_cmd=import_cmd or MagicMock(),
        get_user_settings_cmd=MagicMock(),
        set_user_settings_cmd=MagicMock(),
        test_sub_cmd=MagicMock(),
        get_items_query=MagicMock(),
        polling_service=polling_service,
        feed_repo=MagicMock(),
        sub_repo=MagicMock(),
        user_repo=MagicMock(),
        push_history_repo=MagicMock(),
        config=config or MagicMock(),
        raw_config=raw_config,
    )


@pytest.mark.asyncio
async def test_refresh_feed_endpoint_uses_unified_polling_service():
    polling_service = MagicMock()
    polling_service.poll_feed = AsyncMock(
        return_value=FeedPollingResult(
            success=True,
            status="updated",
            message="ok",
            feed_id=12,
            total_entries=3,
            new_entries=1,
            dispatched=0,
        )
    )
    handler = _handler(polling_service=polling_service)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/feeds/refresh",
        method="POST",
        json={"feed_id": "12"},
    ):
        response = await handler.handle_refresh_feed()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["status"] == "updated"
    assert payload["feed_id"] == 12
    assert payload["total_entries"] == 3
    assert payload["new_entries"] == 1
    polling_service.poll_feed.assert_awaited_once_with(12)


@pytest.mark.asyncio
async def test_plugin_settings_endpoint_updates_pipeline_config():
    raw_config = _WritableConfig()
    config = RsshubPluginConfig.from_astrbot_config({})
    handler = _handler(
        polling_service=MagicMock(),
        config=config,
        raw_config=raw_config,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/plugin-settings",
        method="POST",
        json={
            "pipeline": {
                "keyword_blacklist": ["spam"],
                "ai_filter_enabled": True,
                "ai_timeout_seconds": 8,
            }
        },
    ):
        response = await handler.handle_set_plugin_settings()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["pipeline"]["keyword_blacklist"] == ["spam"]
    assert payload["pipeline"]["ai_filter_enabled"] is True
    assert payload["pipeline"]["ai_timeout_seconds"] == 8
    assert "translate_enabled" not in payload["pipeline"]
    assert raw_config.saved is True
    assert raw_config["pipeline"]["keyword_blacklist"] == ["spam"]
    assert raw_config["pipeline"]["ai_filter_enabled"] is True


@pytest.mark.asyncio
async def test_plugin_settings_endpoint_updates_subscription_defaults():
    raw_config = _WritableConfig()
    config = RsshubPluginConfig.from_astrbot_config({})
    handler = _handler(
        polling_service=MagicMock(),
        config=config,
        raw_config=raw_config,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/plugin-settings",
        method="POST",
        json={
            "subscription_defaults": {
                "interval": 25,
                "notify": False,
                "send_mode": "仅链接",
                "translate": True,
            }
        },
    ):
        response = await handler.handle_set_plugin_settings()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["subscription_defaults"]["interval"] == 25
    assert payload["subscription_defaults"]["notify"] is False
    assert payload["subscription_defaults"]["send_mode"] == "仅链接"
    assert "translate" not in payload["subscription_defaults"]
    assert raw_config.saved is True
    assert raw_config["global_config"]["interval"] == 25
    assert raw_config["global_config"]["notify"] is False
    assert "translate" not in raw_config["global_config"]


@pytest.mark.asyncio
async def test_plugin_settings_endpoint_ignores_removed_translation_payload():
    raw_config = _WritableConfig()
    config = RsshubPluginConfig.from_astrbot_config({})
    handler = _handler(
        polling_service=MagicMock(),
        config=config,
        raw_config=raw_config,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/plugin-settings",
        method="POST",
        json={
            "translation": {
                "target_lang": "ja",
                "auto_translate": True,
                "google_translate_api_key": "",
                "baidu_translate_app_id": "",
                "baidu_translate_secret_key": "",
            }
        },
    ):
        response = await handler.handle_set_plugin_settings()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert "translation" not in payload
    assert "translation" not in raw_config


@pytest.mark.asyncio
async def test_import_endpoint_uses_import_command():
    import_cmd = MagicMock()
    import_cmd.execute = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            message="成功导入 1 个订阅",
            data=None,
        )
    )
    handler = _handler(polling_service=MagicMock(), import_cmd=import_cmd)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/import",
        method="POST",
        json={"content": "[[subscriptions]]\nurl='https://example.com/rss'"},
    ):
        response = await handler.handle_import()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert "成功导入" in payload["message"]
    import_cmd.execute.assert_awaited_once()
