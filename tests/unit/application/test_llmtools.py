from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub.src.application.llmtools import build_llm_tools
from astrbot_plugin_rsshub.src.application.services.agent_xml_push_service import (
    AgentXmlPushService,
)
from astrbot_plugin_rsshub.src.infrastructure.config import (
    BasicConfig,
    GlobalConfig,
    RsshubPluginConfig,
    set_config,
)


def _build_deps():
    return {
        "subscribe_cmd": MagicMock(),
        "unsubscribe_cmd": MagicMock(),
        "update_sub_cmd": MagicMock(),
        "get_subs_query": MagicMock(),
        "set_user_settings_cmd": MagicMock(),
        "get_user_settings_cmd": MagicMock(),
        "subscription_repo": MagicMock(),
        "push_history_repo": MagicMock(),
        "export_cmd": MagicMock(),
        "notification_dispatcher": AsyncMock(),
        "agent_xml_push_service": AgentXmlPushService(
            notification_dispatcher=AsyncMock()
        ),
    }


def _make_event():
    event = MagicMock()
    event.get_sender_id.return_value = "u1"
    event.unified_msg_origin = "p:g:1"
    event.get_platform_name.return_value = "aiocqhttp"
    event.is_admin.return_value = False
    return event


def _make_ctx():
    event = _make_event()
    plugin_ctx = MagicMock()
    wrapper = SimpleNamespace(context=SimpleNamespace(event=event))
    return wrapper, plugin_ctx


def test_build_llm_tools_names():
    deps = _build_deps()
    _, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    names = {tool.name for tool in tools}
    assert names == {
        "rss_subscribe",
        "rss_unsubscribe",
        "rss_unsubscribe_all",
        "rss_list_subscriptions",
        "rss_set_subscription_option",
        "rss_set_user_default_option",
        "rss_set_session_default_option",
        "rss_get_session_defaults",
        "rss_list_push_history",
        "rss_push_xml_entry",
    }


@pytest.mark.asyncio
async def test_llm_tool_rss_subscribe_supports_uri_with_default_base_url():
    set_config(
        RsshubPluginConfig(
            basic_config=BasicConfig(rsshub_base_url="https://rss.example.com"),
            global_config=GlobalConfig(),
        )
    )
    deps = _build_deps()
    deps["subscribe_cmd"].execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="订阅成功")
    )
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_subscribe")

    result = await tool.handler(ctx, uri="/twitter/user/dynamic/123")
    assert "订阅成功" in result
    deps["subscribe_cmd"].execute.assert_awaited_once()
    assert deps["subscribe_cmd"].execute.await_args.kwargs["url"] == (
        "https://rss.example.com/twitter/user/dynamic/123"
    )


@pytest.mark.asyncio
async def test_llm_tool_rss_subscribe_handler():
    deps = _build_deps()
    deps["subscribe_cmd"].execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="订阅成功")
    )
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_subscribe")

    result = await tool.handler(ctx, "https://example.com/rss.xml")
    assert "订阅成功" in result


@pytest.mark.asyncio
async def test_llm_tool_rss_subscribe_accepts_direct_event():
    deps = _build_deps()
    deps["subscribe_cmd"].execute = AsyncMock(
        return_value=SimpleNamespace(success=True, message="订阅成功")
    )
    event = _make_event()
    _, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_subscribe")

    result = await tool.handler(event, "https://example.com/rss.xml")

    assert "订阅成功" in result
    deps["subscribe_cmd"].execute.assert_awaited_once_with(
        url="https://example.com/rss.xml",
        user_id="u1",
        target_session="p:g:1",
        platform_name="aiocqhttp",
    )


@pytest.mark.asyncio
async def test_llm_tool_list_push_history_only_returns_current_session():
    deps = _build_deps()
    deps["push_history_repo"].get_by_user = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=1,
                source_type="agent",
                source_key="daily:ai-news",
                content="content-1",
                raw_xml="<entry><p>One</p></entry>",
                media_urls=["https://example.com/1.png"],
                entry_title="title-1",
                entry_link="https://example.com/1",
                entry_guid="guid-1",
                feed_title="Feed",
                feed_link="https://example.com/feed",
                platform_name="aiocqhttp",
                target_session="p:g:1",
                status="success",
                retry_count=0,
                max_retries=3,
                fail_reason=None,
                created_at=None,
                updated_at=None,
                completed_at=None,
            ),
        ]
    )
    deps["push_history_repo"].count_by_user = AsyncMock(return_value=1)
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_list_push_history")

    result = await tool.handler(ctx, "1", "20")
    data = json.loads(result)
    assert data["ok"] is True
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == 1
    assert "sub_id" not in data["items"][0]
    deps["push_history_repo"].get_by_user.assert_awaited_once_with(
        user_id="u1",
        limit=20,
        offset=0,
        target_session="p:g:1",
    )


@pytest.mark.asyncio
async def test_llm_tool_list_push_history_accepts_direct_event():
    deps = _build_deps()
    deps["push_history_repo"].get_by_user = AsyncMock(return_value=[])
    deps["push_history_repo"].count_by_user = AsyncMock(return_value=0)
    event = _make_event()
    _, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_list_push_history")

    result = await tool.handler(event, "1", "20")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["items"] == []
    deps["push_history_repo"].get_by_user.assert_awaited_once_with(
        user_id="u1",
        limit=20,
        offset=0,
        target_session="p:g:1",
    )


@pytest.mark.asyncio
async def test_llm_tool_rss_push_xml_entry_dry_run_validates_and_previews():
    deps = _build_deps()
    deps["notification_dispatcher"].dispatch_agent_entry = AsyncMock()
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_push_xml_entry")

    result = await tool.handler(
        ctx,
        "daily:ai-news",
        "Daily",
        "<entry><p>Hello</p><img src='https://example.com/a.jpg'/></entry>",
        "https://example.com/post",
        "Alice",
        "Feed",
        "",
        "",
        True,
    )

    data = json.loads(result)
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert data["preview"]["entry_guid"].startswith("agent:")
    deps["notification_dispatcher"].assert_not_called()


@pytest.mark.asyncio
async def test_llm_tool_rss_push_xml_entry_accepts_direct_event():
    deps = _build_deps()
    event = _make_event()
    _, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_push_xml_entry")

    result = await tool.handler(
        event,
        "daily:ai-news",
        "Daily",
        "<entry><p>Hello</p></entry>",
        dry_run=True,
    )

    data = json.loads(result)
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert data["preview"]["entry_guid"].startswith("agent:")


@pytest.mark.asyncio
async def test_llm_tool_rss_push_xml_entry_rejects_invalid_xml():
    deps = _build_deps()
    deps["notification_dispatcher"].dispatch_agent_entry = AsyncMock()
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rss_push_xml_entry")

    result = await tool.handler(ctx, "daily:ai-news", "Daily", "<entry><p>bad</entry>")

    assert "xml 格式错误" in result
