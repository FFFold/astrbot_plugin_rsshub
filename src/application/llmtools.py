"""RSSHub LLM 工具注册。"""

from __future__ import annotations

import json
from dataclasses import dataclass as py_dataclass
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import parse_qsl, urlencode, urljoin

try:
    from astrbot.core.agent.tool import FunctionTool
except Exception:  # pragma: no cover - test/mocking fallback

    @py_dataclass
    class FunctionTool:  # type: ignore[no-redef]
        name: str
        description: str
        parameters: dict
        handler: Any = None


if TYPE_CHECKING:
    from astrbot.core.agent.run_context import ContextWrapper
    from astrbot.core.astr_agent_context import AstrAgentContext

from ..interfaces import handlers as h


class LLMToolDeps(TypedDict):
    subscribe_cmd: Any
    unsubscribe_cmd: Any
    update_sub_cmd: Any
    get_subs_query: Any
    set_user_settings_cmd: Any
    get_user_settings_cmd: Any
    subscription_repo: Any
    export_cmd: Any


LLM_TOOL_NAMES = [
    "rss_subscribe",
    "rss_unsubscribe",
    "rss_unsubscribe_all",
    "rss_list_subscriptions",
    "rss_set_subscription_option",
    "rss_set_user_default_option",
    "rss_set_session_default_option",
    "rss_get_session_defaults",
    "rsshub_build_subscribe_url",
]


def _resolve_base_url(explicit_base_url: str = "") -> str:
    if explicit_base_url.strip():
        return explicit_base_url.strip().rstrip("/")
    try:
        from ..infrastructure.config import get_config

        cfg = get_config()
        if cfg and cfg.rsshub_base_url:
            return str(cfg.rsshub_base_url).rstrip("/")
    except Exception:
        pass
    return "https://rsshub.app"


def _parse_params_input(params_json: str) -> dict[str, Any]:
    raw = (params_json or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if v is not None}
    except json.JSONDecodeError:
        pass
    if "=" in raw:
        return dict(parse_qsl(raw, keep_blank_values=True))
    return {}


def _tool(
    *,
    name: str,
    description: str,
    parameters: dict,
    handler,
) -> FunctionTool:
    return FunctionTool(
        name=name,
        description=description,
        parameters=parameters,
        handler=handler,
    )


def build_llm_tools(*, deps: LLMToolDeps, plugin_context) -> list[FunctionTool]:
    """构建 RSSHub 插件 LLM 工具列表。"""

    async def rss_subscribe(
        context: ContextWrapper[AstrAgentContext],
        url: str,
    ) -> str:
        result = await h.handle_sub(context.context.event, url, deps)
        return result.get("plain", "")

    async def rss_unsubscribe(
        context: ContextWrapper[AstrAgentContext],
        sub_id: str,
    ) -> str:
        result = await h.handle_unsub(context.context.event, sub_id, deps)
        return result.get("plain", "")

    async def rss_unsubscribe_all(
        context: ContextWrapper[AstrAgentContext],
        scope: str = "",
    ) -> str:
        result = await h.handle_unsub_all(context.context.event, scope, deps)
        return result.get("plain", "")

    async def rss_list_subscriptions(
        context: ContextWrapper[AstrAgentContext],
        page: str = "",
        page_size: str = "",
    ) -> str:
        args = " ".join(part for part in (page, page_size) if str(part).strip())
        result = await h.handle_sub_list(context.context.event, args, deps)
        return result.get("plain", "")

    async def rss_set_subscription_option(
        context: ContextWrapper[AstrAgentContext],
        sub_id: str,
        key: str,
        value: str,
    ) -> str:
        try:
            sub_id_int = int(sub_id)
        except ValueError:
            return "订阅 ID 必须是数字"
        result = await h.handle_sub_set(
            context.context.event,
            sub_id_int,
            key,
            value,
            deps,
        )
        return result.get("plain", "")

    async def rss_set_user_default_option(
        context: ContextWrapper[AstrAgentContext],
        key: str,
        value: str,
    ) -> str:
        result = await h.handle_sub_set_user(context.context.event, key, value, deps)
        return result.get("plain", "")

    async def rss_set_session_default_option(
        context: ContextWrapper[AstrAgentContext],
        key: str,
        value: str,
    ) -> str:
        result = await h.handle_sub_set_session(
            context.context.event,
            key,
            value,
            deps,
            plugin_context,
        )
        return result.get("plain", "")

    async def rss_get_session_defaults(
        context: ContextWrapper[AstrAgentContext],
    ) -> str:
        result = await h.handle_sub_get_session(
            context.context.event,
            "",
            deps,
            plugin_context,
        )
        return result.get("plain", "")

    async def rsshub_build_subscribe_url(
        context: ContextWrapper[AstrAgentContext],
        uri: str = "",
        params_json: str = "",
        base_url: str = "",
    ) -> str:
        del context
        if not uri.strip():
            return "请提供 uri，例如 /bilibili/user/dynamic/12345"
        resolved = _resolve_base_url(base_url)
        clean_uri = uri.strip()
        if not clean_uri.startswith("/"):
            clean_uri = f"/{clean_uri}"
        params = _parse_params_input(params_json)
        subscribe_url = urljoin(f"{resolved}/", clean_uri.lstrip("/"))
        if params:
            subscribe_url = f"{subscribe_url}?{urlencode(params, doseq=True)}"
        return json.dumps(
            {
                "resolved_base_url": resolved,
                "uri": clean_uri,
                "params": params,
                "subscribe_url": subscribe_url,
            },
            ensure_ascii=False,
            indent=2,
        )

    return [
        _tool(
            name="rss_subscribe",
            description="订阅 RSS 源，支持空格分隔多个 URL。",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "一个或多个 RSS URL，空格分隔。",
                    }
                },
                "required": ["url"],
            },
            handler=rss_subscribe,
        ),
        _tool(
            name="rss_unsubscribe",
            description="取消订阅，支持 ID/URL，支持空格分隔多个目标。",
            parameters={
                "type": "object",
                "properties": {
                    "sub_id": {
                        "type": "string",
                        "description": "订阅 ID 或 URL，支持多个。",
                    }
                },
                "required": ["sub_id"],
            },
            handler=rss_unsubscribe,
        ),
        _tool(
            name="rss_unsubscribe_all",
            description="取消全部订阅。scope=global 需要管理员权限。",
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "可选: 留空(当前会话) 或 global(所有会话)",
                    }
                },
            },
            handler=rss_unsubscribe_all,
        ),
        _tool(
            name="rss_list_subscriptions",
            description="查看当前会话订阅列表。",
            parameters={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "页码，默认1"},
                    "page_size": {
                        "type": "string",
                        "description": "每页数量，默认5，最大100",
                    },
                },
            },
            handler=rss_list_subscriptions,
        ),
        _tool(
            name="rss_set_subscription_option",
            description="设置订阅级配置项。",
            parameters={
                "type": "object",
                "properties": {
                    "sub_id": {"type": "string", "description": "订阅 ID"},
                    "key": {"type": "string", "description": "配置项名称"},
                    "value": {"type": "string", "description": "配置项值"},
                },
                "required": ["sub_id", "key", "value"],
            },
            handler=rss_set_subscription_option,
        ),
        _tool(
            name="rss_set_user_default_option",
            description="设置用户默认配置项。",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "配置项名称"},
                    "value": {"type": "string", "description": "配置项值"},
                },
                "required": ["key", "value"],
            },
            handler=rss_set_user_default_option,
        ),
        _tool(
            name="rss_set_session_default_option",
            description="设置当前会话默认配置项。",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "配置项名称"},
                    "value": {"type": "string", "description": "配置项值"},
                },
                "required": ["key", "value"],
            },
            handler=rss_set_session_default_option,
        ),
        _tool(
            name="rss_get_session_defaults",
            description="查看当前会话默认配置。",
            parameters={"type": "object", "properties": {}},
            handler=rss_get_session_defaults,
        ),
        _tool(
            name="rsshub_build_subscribe_url",
            description="基于 uri 和参数构建 RSSHub 订阅 URL。",
            parameters={
                "type": "object",
                "properties": {
                    "uri": {"type": "string", "description": "路由 URI"},
                    "params_json": {
                        "type": "string",
                        "description": "JSON 对象或 query-string 参数串",
                    },
                    "base_url": {
                        "type": "string",
                        "description": "可选 RSSHub base URL 覆盖值",
                    },
                },
                "required": ["uri"],
            },
            handler=rsshub_build_subscribe_url,
        ),
    ]
