"""配置相关命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

SESSION_DEFAULT_KV_PREFIX = "rsshub_session_defaults_"
SESSION_DEFAULT_KEYS = {
    "interval",
    "notify",
    "send_mode",
    "length_limit",
    "link_preview",
    "display_author",
    "display_via",
    "display_title",
    "display_entry_tags",
    "style",
    "display_media",
    "translate",
    "translate_target_lang",
    "title",
    "tags",
}


async def handle_sub_set(
    event: AstrMessageEvent, sub_id: int, option: str, value: str, deps: dict
) -> dict:
    """修改订阅配置"""
    if sub_id <= 0 or not option:
        return {
            "plain": "用法: /sub_set <sub_id> <option> <value>\n示例: /sub_set 1 interval 30"
        }
    user_id = event.get_sender_id()
    result = await deps["update_sub_cmd"].execute(
        sub_id=sub_id, user_id=user_id, **{option: value}
    )
    return {"plain": result.message}


async def handle_sub_set_user(
    event: AstrMessageEvent, key: str, value: str, deps: dict
) -> dict:
    """设置用户配置"""
    if not key or not value:
        result = await deps["get_user_settings_cmd"].execute(
            user_id=event.get_sender_id()
        )
        return {"plain": result.message}
    user_id = event.get_sender_id()
    result = await deps["set_user_settings_cmd"].execute(
        user_id=user_id,
        key=key.strip().lower(),
        value=value,
    )
    return {"plain": result.message}


async def handle_sub_get_user(event: AstrMessageEvent, key: str, deps: dict) -> dict:
    """获取用户配置"""
    user_id = event.get_sender_id()
    result = await deps["get_user_settings_cmd"].execute(
        user_id=user_id,
        key=key.strip().lower() if key else None,
    )
    return {"plain": result.message}


async def handle_sub_set_session(
    event: AstrMessageEvent, key: str, value: str, deps: dict, ctx
) -> dict:
    """设置会话默认配置"""
    if not key or not value:
        return {
            "plain": "用法: /sub_set_session <选项> <值>\n可用选项: interval, notify, send_mode, length_limit, display_title, display_media, translate 等"
        }

    session_id = event.unified_msg_origin
    defaults = await _get_session_defaults(ctx, session_id)

    option_key = key.strip().lower()
    if option_key not in SESSION_DEFAULT_KEYS:
        return {"plain": f"未知选项: {option_key}"}

    parsed_value = value
    if option_key not in {"title", "tags"}:
        try:
            parsed_value = int(value)
        except ValueError:
            return {"plain": f"选项 {option_key} 需要数字值"}

    defaults[option_key] = parsed_value
    await _set_session_defaults(ctx, session_id, defaults)
    return {"plain": f"会话默认配置已更新: {option_key} = {parsed_value}"}


async def handle_sub_get_session(
    event: AstrMessageEvent, key: str, deps: dict, ctx
) -> dict:
    """获取会话默认配置"""
    session_id = event.unified_msg_origin
    defaults = await _get_session_defaults(ctx, session_id)

    if not defaults:
        return {"plain": "当前会话未设置任何默认值\n新订阅将继承用户/全局配置"}

    option_key = key.strip().lower() if key else ""
    if option_key:
        return {"plain": f"{option_key} = {defaults.get(option_key, '未设置')}"}
    else:
        lines = ["会话默认配置:"]
        for k, v in defaults.items():
            lines.append(f"  {k} = {v}")
        return {"plain": "\n".join(lines)}


async def _get_session_defaults(ctx, session_id: str) -> dict:
    key = f"{SESSION_DEFAULT_KV_PREFIX}{session_id}"
    raw = await ctx.get_kv_data(key, {})
    if not isinstance(raw, dict):
        return {}
    return raw


async def _set_session_defaults(ctx, session_id: str, defaults: dict):
    key = f"{SESSION_DEFAULT_KV_PREFIX}{session_id}"
    await ctx.put_kv_data(key, defaults)
