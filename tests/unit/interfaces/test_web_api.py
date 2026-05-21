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


def _handler(
    *,
    polling_service,
    config=None,
    raw_config=None,
    subscribe_cmd=None,
    unsubscribe_cmd=None,
    update_sub_cmd=None,
    batch_activate_cmd=None,
    batch_deactivate_cmd=None,
    batch_unsub_cmd=None,
    export_cmd=None,
    import_cmd=None,
    get_user_settings_cmd=None,
    set_user_settings_cmd=None,
    test_sub_cmd=None,
    route_knowledge_service=None,
):
    return WebApiHandler(
        subscribe_cmd=subscribe_cmd or MagicMock(),
        unsubscribe_cmd=unsubscribe_cmd or MagicMock(),
        update_sub_cmd=update_sub_cmd or MagicMock(),
        batch_activate_cmd=batch_activate_cmd or MagicMock(),
        batch_deactivate_cmd=batch_deactivate_cmd or MagicMock(),
        batch_unsub_cmd=batch_unsub_cmd or MagicMock(),
        export_cmd=export_cmd or MagicMock(),
        import_cmd=import_cmd or MagicMock(),
        get_user_settings_cmd=get_user_settings_cmd or MagicMock(),
        set_user_settings_cmd=set_user_settings_cmd or MagicMock(),
        test_sub_cmd=test_sub_cmd or MagicMock(),
        get_items_query=MagicMock(),
        polling_service=polling_service,
        feed_repo=MagicMock(),
        sub_repo=MagicMock(),
        user_repo=MagicMock(),
        push_history_repo=MagicMock(),
        route_knowledge_service=route_knowledge_service,
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
async def test_plugin_settings_endpoint_ignores_removed_pipeline_config():
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
    assert "pipeline" not in payload
    assert raw_config.saved is True
    assert "pipeline" not in raw_config


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
async def test_handlers_endpoint_returns_registry_schema():
    handler = _handler(polling_service=MagicMock())

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/handlers",
        method="GET",
    ):
        response = await handler.handle_handlers()

    payload = await response.get_json()
    assert payload["ok"] is True
    names = {item["name"] for item in payload["items"]}
    assert {"xml_parse", "ai_filter", "ai_transform"} <= names
    ai_filter = next(item for item in payload["items"] if item["name"] == "ai_filter")
    assert any(field["type"] == "select" for field in ai_filter["schema"])


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
        json={
            "content": "[[subscriptions]]\nurl='https://example.com/rss'",
            "user_id": "alice",
        },
    ):
        response = await handler.handle_import()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert "成功导入" in payload["message"]
    import_cmd.execute.assert_awaited_once_with(
        content="[[subscriptions]]\nurl='https://example.com/rss'",
        user_id="alice",
        target_session=None,
        platform_name=None,
        skip_existing=True,
    )


@pytest.mark.asyncio
async def test_push_history_endpoint_filters_by_user_session_and_status():
    push_history_repo = MagicMock()
    push_history_repo.get_by_user = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=11,
                user_id="alice",
                feed_id=None,
                source_type="agent",
                source_key="daily:ai-news",
                content="hello",
                raw_xml="<entry><p>Hello</p></entry>",
                media_urls=["https://example.com/a.jpg"],
                handler_trace=[
                    {
                        "id": "builtin.ai_filter.default",
                        "name": "ai_filter",
                        "status": "ok",
                        "allow": False,
                        "reason": "广告",
                    }
                ],
                entry_title="日报",
                entry_link="https://example.com/post",
                entry_guid="guid-11",
                feed_title="AI Daily",
                feed_link="https://example.com/feed",
                platform_name="aiocqhttp",
                target_session="default:GroupMessage:1",
                status="failed",
                retry_count=1,
                max_retries=3,
                fail_reason="boom",
                created_at=None,
                updated_at=None,
                completed_at=None,
            )
        ]
    )
    push_history_repo.count_by_user = AsyncMock(return_value=1)
    handler = WebApiHandler(
        subscribe_cmd=MagicMock(),
        unsubscribe_cmd=MagicMock(),
        update_sub_cmd=MagicMock(),
        batch_activate_cmd=MagicMock(),
        batch_deactivate_cmd=MagicMock(),
        batch_unsub_cmd=MagicMock(),
        export_cmd=MagicMock(),
        import_cmd=MagicMock(),
        get_user_settings_cmd=MagicMock(),
        set_user_settings_cmd=MagicMock(),
        test_sub_cmd=MagicMock(),
        get_items_query=MagicMock(),
        polling_service=MagicMock(),
        feed_repo=MagicMock(),
        sub_repo=MagicMock(),
        user_repo=MagicMock(),
        push_history_repo=push_history_repo,
        route_knowledge_service=None,
        config=MagicMock(),
        raw_config=None,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/push-history?user_id=alice&target_session=default:GroupMessage:1&status=failed&page=1&page_size=20",
        method="GET",
    ):
        response = await handler.handle_push_history()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["total"] == 1
    assert payload["items"][0]["raw_xml"] == "<entry><p>Hello</p></entry>"
    assert payload["items"][0]["handler_trace"][0]["name"] == "ai_filter"
    assert payload["items"][0]["fail_reason"] == "boom"
    assert "sub_id" not in payload["items"][0]
    push_history_repo.get_by_user.assert_awaited_once_with(
        user_id="alice",
        limit=20,
        offset=0,
        target_session="default:GroupMessage:1",
        status="failed",
    )
    push_history_repo.count_by_user.assert_awaited_once_with(
        user_id="alice",
        target_session="default:GroupMessage:1",
        status="failed",
    )


@pytest.mark.asyncio
async def test_push_history_endpoint_keeps_empty_fail_reason_empty_for_success():
    push_history_repo = MagicMock()
    push_history_repo.get_by_user = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=12,
                user_id="alice",
                feed_id=1,
                source_type="feed",
                source_key=None,
                content="ok",
                raw_xml=None,
                media_urls=None,
                handler_trace=None,
                entry_title="成功记录",
                entry_link="https://example.com/post",
                entry_guid="guid-12",
                feed_title="AI Daily",
                feed_link="https://example.com/feed",
                platform_name="aiocqhttp",
                target_session="default:GroupMessage:1",
                status="success",
                retry_count=0,
                max_retries=3,
                fail_reason=None,
                created_at=None,
                updated_at=None,
                completed_at=None,
                sub_id=1,
            )
        ]
    )
    push_history_repo.count_by_user = AsyncMock(return_value=1)
    handler = WebApiHandler(
        subscribe_cmd=MagicMock(),
        unsubscribe_cmd=MagicMock(),
        update_sub_cmd=MagicMock(),
        batch_activate_cmd=MagicMock(),
        batch_deactivate_cmd=MagicMock(),
        batch_unsub_cmd=MagicMock(),
        export_cmd=MagicMock(),
        import_cmd=MagicMock(),
        get_user_settings_cmd=MagicMock(),
        set_user_settings_cmd=MagicMock(),
        test_sub_cmd=MagicMock(),
        get_items_query=MagicMock(),
        polling_service=MagicMock(),
        feed_repo=MagicMock(),
        sub_repo=MagicMock(),
        user_repo=MagicMock(),
        push_history_repo=push_history_repo,
        route_knowledge_service=None,
        config=MagicMock(),
        raw_config=None,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/push-history?user_id=alice&target_session=default:GroupMessage:1&status=success&page=1&page_size=20",
        method="GET",
    ):
        response = await handler.handle_push_history()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["items"][0]["fail_reason"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "command_attr", "json_payload"),
    [
        ("handle_subscribe", "_subscribe_cmd", {"url": "https://example.com/rss"}),
        ("handle_unsubscribe", "_unsubscribe_cmd", {"sub_id": 1}),
        ("handle_update_subscription", "_update_sub_cmd", {"sub_id": 1}),
        ("handle_get_settings", "_get_user_settings_cmd", None),
        ("handle_set_settings", "_set_user_settings_cmd", {"settings": {}}),
        ("handle_test_subscription", "_test_sub_cmd", {"sub_id": 1}),
        ("handle_batch_activate", "_batch_activate_cmd", {"sub_ids": [1]}),
        ("handle_batch_deactivate", "_batch_deactivate_cmd", {"sub_ids": [1]}),
        ("handle_batch_unsubscribe", "_batch_unsub_cmd", {"sub_ids": [1]}),
        ("handle_export", "_export_cmd", {}),
        (
            "handle_import",
            "_import_cmd",
            {"content": "[[subscriptions]]\nurl='https://example.com/rss'"},
        ),
    ],
)
async def test_user_command_endpoints_reject_missing_user_id(
    handler_name, command_attr, json_payload
):
    handler = _handler(polling_service=MagicMock())
    command = getattr(handler, command_attr)
    command.execute = AsyncMock()

    app = Quart(__name__)
    method = "GET" if handler_name == "handle_get_settings" else "POST"
    async with app.test_request_context(
        f"/astrbot_plugin_rsshub/{handler_name}",
        method=method,
        json=json_payload,
    ):
        response = await getattr(handler, handler_name)()

    payload = await response.get_json()
    assert payload == {"ok": False, "error": "user_id 不能为空"}
    command.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "command_attr", "json_payload", "path"),
    [
        (
            "handle_subscribe",
            "_subscribe_cmd",
            {"url": "https://example.com/rss", "user_id": " "},
            "/astrbot_plugin_rsshub/subscribe",
        ),
        (
            "handle_unsubscribe",
            "_unsubscribe_cmd",
            {"sub_id": 1, "user_id": ""},
            "/astrbot_plugin_rsshub/unsubscribe",
        ),
        (
            "handle_update_subscription",
            "_update_sub_cmd",
            {"sub_id": 1, "user_id": " "},
            "/astrbot_plugin_rsshub/subscriptions/update",
        ),
        (
            "handle_get_settings",
            "_get_user_settings_cmd",
            None,
            "/astrbot_plugin_rsshub/settings?user_id=",
        ),
        (
            "handle_set_settings",
            "_set_user_settings_cmd",
            {"settings": {}, "user_id": ""},
            "/astrbot_plugin_rsshub/settings",
        ),
        (
            "handle_test_subscription",
            "_test_sub_cmd",
            {"sub_id": 1, "user_id": " "},
            "/astrbot_plugin_rsshub/test-subscription",
        ),
        (
            "handle_batch_activate",
            "_batch_activate_cmd",
            {"sub_ids": [1], "user_id": ""},
            "/astrbot_plugin_rsshub/batch/activate",
        ),
        (
            "handle_batch_deactivate",
            "_batch_deactivate_cmd",
            {"sub_ids": [1], "user_id": " "},
            "/astrbot_plugin_rsshub/batch/deactivate",
        ),
        (
            "handle_batch_unsubscribe",
            "_batch_unsub_cmd",
            {"sub_ids": [1], "user_id": ""},
            "/astrbot_plugin_rsshub/batch/unsubscribe",
        ),
        (
            "handle_export",
            "_export_cmd",
            {"user_id": " "},
            "/astrbot_plugin_rsshub/export",
        ),
        (
            "handle_import",
            "_import_cmd",
            {
                "content": "[[subscriptions]]\nurl='https://example.com/rss'",
                "user_id": "",
            },
            "/astrbot_plugin_rsshub/import",
        ),
    ],
)
async def test_user_command_endpoints_reject_blank_user_id(
    handler_name, command_attr, json_payload, path
):
    handler = _handler(polling_service=MagicMock())
    command = getattr(handler, command_attr)
    command.execute = AsyncMock()

    app = Quart(__name__)
    method = "GET" if handler_name == "handle_get_settings" else "POST"
    async with app.test_request_context(path, method=method, json=json_payload):
        response = await getattr(handler, handler_name)()

    payload = await response.get_json()
    assert payload == {"ok": False, "error": "user_id 不能为空"}
    command.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_subscription_passes_real_user_id():
    command = MagicMock()
    command.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="ok")
    )
    handler = _handler(polling_service=MagicMock(), update_sub_cmd=command)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/subscriptions/update",
        method="POST",
        json={
            "sub_id": 12,
            "user_id": "alice",
            "options": {"notify": False, "handlers_mode": "override"},
        },
    ):
        response = await handler.handle_update_subscription()

    payload = await response.get_json()
    assert payload["ok"] is True
    command.execute.assert_awaited_once_with(
        sub_id=12,
        user_id="alice",
        handlers_mode="override",
        notify=False,
    )


@pytest.mark.asyncio
async def test_list_subscriptions_returns_handlers_mode():
    sub_repo = MagicMock()
    feed_repo = MagicMock()
    sub_repo.get_all_active = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=1,
                state=1,
                user_id="alice",
                feed_id=2,
                title="Daily",
                tags="news",
                target_session="default:GroupMessage:1",
                platform_name="aiocqhttp",
                interval=15,
                notify=1,
                send_mode=0,
                handlers_mode="disabled",
                handlers=[],
                length_limit=300,
                display_author=1,
                display_via=0,
                display_title=1,
                display_entry_tags=0,
                style=0,
                display_media=0,
                created_at=None,
                updated_at=None,
            )
        ]
    )
    feed_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            title="Feed Title",
            link="https://example.com/feed.xml",
        )
    )
    handler = WebApiHandler(
        subscribe_cmd=MagicMock(),
        unsubscribe_cmd=MagicMock(),
        update_sub_cmd=MagicMock(),
        batch_activate_cmd=MagicMock(),
        batch_deactivate_cmd=MagicMock(),
        batch_unsub_cmd=MagicMock(),
        export_cmd=MagicMock(),
        import_cmd=MagicMock(),
        get_user_settings_cmd=MagicMock(),
        set_user_settings_cmd=MagicMock(),
        test_sub_cmd=MagicMock(),
        get_items_query=MagicMock(),
        polling_service=MagicMock(),
        feed_repo=feed_repo,
        sub_repo=sub_repo,
        user_repo=MagicMock(),
        push_history_repo=MagicMock(),
        route_knowledge_service=None,
        config=MagicMock(),
        raw_config=None,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/subscriptions",
        method="GET",
    ):
        response = await handler.handle_list_subscriptions()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["items"][0]["handlers_mode"] == "disabled"


@pytest.mark.asyncio
async def test_unsubscribe_passes_real_user_id():
    command = MagicMock()
    command.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="ok")
    )
    handler = _handler(polling_service=MagicMock(), unsubscribe_cmd=command)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/unsubscribe",
        method="POST",
        json={"sub_id": 12, "user_id": "alice"},
    ):
        response = await handler.handle_unsubscribe()

    payload = await response.get_json()
    assert payload["ok"] is True
    command.execute.assert_awaited_once_with(sub_id=12, user_id="alice")


@pytest.mark.asyncio
async def test_test_subscription_passes_real_user_id():
    command = MagicMock()
    command.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="ok", data={"sent": True})
    )
    handler = _handler(polling_service=MagicMock(), test_sub_cmd=command)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/test-subscription",
        method="POST",
        json={"sub_id": 12, "user_id": "alice"},
    ):
        response = await handler.handle_test_subscription()

    payload = await response.get_json()
    assert payload["ok"] is True
    command.execute.assert_awaited_once_with(sub_id=12, user_id="alice")


@pytest.mark.asyncio
async def test_batch_operations_pass_real_user_id():
    activate_cmd = MagicMock()
    activate_cmd.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="activated")
    )
    deactivate_cmd = MagicMock()
    deactivate_cmd.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="deactivated")
    )
    unsub_cmd = MagicMock()
    unsub_cmd.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="unsubscribed")
    )
    handler = _handler(
        polling_service=MagicMock(),
        batch_activate_cmd=activate_cmd,
        batch_deactivate_cmd=deactivate_cmd,
        batch_unsub_cmd=unsub_cmd,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/batch/activate",
        method="POST",
        json={"sub_ids": [1, 2], "user_id": "alice"},
    ):
        activate_response = await handler.handle_batch_activate()
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/batch/deactivate",
        method="POST",
        json={"sub_ids": [3], "user_id": "alice"},
    ):
        deactivate_response = await handler.handle_batch_deactivate()
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/batch/unsubscribe",
        method="POST",
        json={"sub_ids": [4], "user_id": "alice"},
    ):
        unsub_response = await handler.handle_batch_unsubscribe()

    assert (await activate_response.get_json())["ok"] is True
    assert (await deactivate_response.get_json())["ok"] is True
    assert (await unsub_response.get_json())["ok"] is True
    activate_cmd.execute.assert_awaited_once_with(sub_ids=[1, 2], user_id="alice")
    deactivate_cmd.execute.assert_awaited_once_with(sub_ids=[3], user_id="alice")
    unsub_cmd.execute.assert_awaited_once_with(sub_ids=[4], user_id="alice")


@pytest.mark.asyncio
async def test_export_passes_real_user_id():
    command = MagicMock()
    command.execute = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            message="ok",
            data=SimpleNamespace(content="toml", filename="subs.toml", count=1),
        )
    )
    handler = _handler(polling_service=MagicMock(), export_cmd=command)

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/export",
        method="POST",
        json={"user_id": "alice"},
    ):
        response = await handler.handle_export()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["filename"] == "subs.toml"
    command.execute.assert_awaited_once_with(user_id="alice")


@pytest.mark.asyncio
async def test_route_kb_status_endpoint_returns_service_status():
    service = MagicMock()
    service.get_status = AsyncMock(
        return_value=SimpleNamespace(
            kb_name="RSSHub Routes",
            kb_id="kb-1",
            source_version="v1",
            source_generated_at="",
            last_sync_at="2026-05-19T00:00:00Z",
            managed_files=3,
            kb_docs=3,
            last_error="",
            task=SimpleNamespace(status="idle", task_id="", processed=0, total=0),
        )
    )
    handler = _handler(
        polling_service=MagicMock(),
        route_knowledge_service=service,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/route-kb/status",
        method="GET",
    ):
        response = await handler.handle_route_kb_status()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["status"]["kb_name"] == "RSSHub Routes"
    assert payload["status"]["task"]["status"] == "idle"
    service.get_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_kb_sync_endpoint_starts_service_task():
    service = MagicMock()
    service.start_sync = AsyncMock(
        return_value=SimpleNamespace(
            task_id="task-1",
            status="queued",
            kb_name="RSSHub Routes",
            processed=0,
            total=0,
        )
    )
    handler = _handler(
        polling_service=MagicMock(),
        route_knowledge_service=service,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/route-kb/sync",
        method="POST",
        json={},
    ):
        response = await handler.handle_route_kb_sync()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["task"]["task_id"] == "task-1"
    assert payload["task"]["status"] == "queued"
    service.start_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_kb_task_endpoint_returns_latest_task():
    service = MagicMock()
    service.get_task_status.return_value = SimpleNamespace(
        task_id="task-1",
        status="running",
        processed=2,
        total=5,
    )
    handler = _handler(
        polling_service=MagicMock(),
        route_knowledge_service=service,
    )

    app = Quart(__name__)
    async with app.test_request_context(
        "/astrbot_plugin_rsshub/route-kb/task",
        method="GET",
    ):
        response = await handler.handle_route_kb_task()

    payload = await response.get_json()
    assert payload["ok"] is True
    assert payload["task"]["status"] == "running"
    assert payload["task"]["processed"] == 2
    service.get_task_status.assert_called_once()
