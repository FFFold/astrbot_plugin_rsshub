from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub.src.application.llmtools import build_llm_tools


def _build_deps():
    return {
        "subscribe_cmd": MagicMock(),
        "unsubscribe_cmd": MagicMock(),
        "update_sub_cmd": MagicMock(),
        "get_subs_query": MagicMock(),
        "set_user_settings_cmd": MagicMock(),
        "get_user_settings_cmd": MagicMock(),
        "subscription_repo": MagicMock(),
        "export_cmd": MagicMock(),
    }


def _make_ctx():
    event = MagicMock()
    event.get_sender_id.return_value = "u1"
    event.unified_msg_origin = "p:g:1"
    event.get_platform_name.return_value = "aiocqhttp"
    event.is_admin.return_value = False
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
        "rsshub_build_subscribe_url",
    }


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
async def test_llm_tool_build_subscribe_url():
    deps = _build_deps()
    ctx, plugin_ctx = _make_ctx()
    tools = build_llm_tools(deps=deps, plugin_context=plugin_ctx)
    tool = next(t for t in tools if t.name == "rsshub_build_subscribe_url")

    result = await tool.handler(ctx, "/bilibili/user/dynamic/123", '{"key":"v"}', "")
    assert "subscribe_url" in result
