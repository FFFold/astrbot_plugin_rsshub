"""订阅相关命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ...application.services.session_push_queue import SessionPushQueue


async def handle_sub(event: AstrMessageEvent, url: str, deps: dict) -> dict:
    """订阅 RSS 源"""
    if not url:
        return {"plain": "请提供 RSS 源的 URL\n用法: /sub <url>"}

    user_id = event.get_sender_id()
    target_session = event.unified_msg_origin
    platform_name = event.get_platform_name()

    url_list = [u.strip() for u in url.split() if u.strip()]
    valid_urls = [u for u in url_list if u.startswith(("http://", "https://"))]

    if not valid_urls:
        return {"plain": "请提供有效的 RSS 链接（需以 http 或 https 开头）"}

    if len(valid_urls) == 1:
        result = await deps["subscribe_cmd"].execute(
            url=valid_urls[0],
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
        )
        return {"plain": result.message}

    results = []
    for single_url in valid_urls:
        r = await deps["subscribe_cmd"].execute(
            url=single_url,
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
        )
        results.append(r)

    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    if failed_count == 0:
        return {"plain": f"成功订阅 {success_count} 个 RSS 源"}
    elif success_count == 0:
        return {"plain": f"全部失败: {failed_count} 个订阅失败"}
    else:
        return {"plain": f"部分成功: {success_count} 个订阅成功, {failed_count} 个失败"}


async def handle_unsub(event: AstrMessageEvent, sub_id: int, deps: dict) -> dict:
    """取消订阅"""
    if sub_id <= 0:
        return {"plain": "请提供订阅 ID\n用法: /unsub <ID>"}

    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin
    is_admin = event.is_admin()
    result = await deps["unsubscribe_cmd"].execute(
        sub_id=sub_id,
        user_id=user_id,
        current_session=current_session,
        is_admin=is_admin,
    )
    return {"plain": result.message}


async def handle_sub_list(event: AstrMessageEvent, deps: dict) -> dict:
    """查看订阅列表"""
    user_id = event.get_sender_id()
    result = await deps["get_subs_query"].execute(user_id=user_id)
    if not result.subscriptions:
        return {"plain": "暂无订阅\n使用 /sub <url> 添加订阅"}

    current_session = event.unified_msg_origin
    visible = [
        sub
        for sub in result.subscriptions
        if (sub.target_session or current_session) == current_session
    ]

    if not visible:
        return {"plain": "当前会话没有订阅\n使用 /sub <url> 添加订阅"}

    total_count = len(visible)
    active_count = sum(1 for sub in visible if sub.state == 1)
    inactive_count = total_count - active_count
    lines = [
        "您的订阅列表（当前会话）:",
        f"共 {total_count} 个订阅 | 启用: {active_count} | 禁用: {inactive_count}",
    ]
    for i, sub in enumerate(visible, 1):
        state_icon = "✓" if sub.state == 1 else "✗"
        feed_title = sub.feed_title or f"Feed #{sub.feed_id}"
        custom_title = f" ({sub.title})" if sub.title else ""
        lines.append(f"{i}. [{sub.id}] {state_icon} {feed_title}{custom_title}")
        if sub.feed_link:
            lines.append(f"    {sub.feed_link}")
    return {"plain": "\n".join(lines)}


async def handle_refresh(event: AstrMessageEvent, feed_id: int, deps: dict) -> dict:
    """刷新订阅"""
    if feed_id <= 0:
        return {"plain": "请提供 Feed ID\n用法: /refresh <feed_id>"}
    result = await deps["polling_service"].poll_feed(feed_id)
    return {"plain": result.message}


def handle_rss_stop(event: AstrMessageEvent, queue: SessionPushQueue) -> dict:
    """停止当前会话正在运行的 RSS 推送任务"""
    current_session = event.unified_msg_origin
    result = queue.stop_current(current_session)
    if result.stopped:
        queued = (
            f"，队列中还有 {result.queued_count} 个任务" if result.queued_count else ""
        )
        return {"plain": f"{result.message}{queued}"}
    return {"plain": result.message}


async def handle_sub_state(
    event: AstrMessageEvent, sub_id_str: str, deps: dict
) -> dict:
    """订阅状态管理"""
    if not sub_id_str:
        return {"plain": "用法: /sub_state <订阅ID> on/off\n示例: /sub_state 123 on"}

    parts = sub_id_str.split()
    if len(parts) < 2:
        return {"plain": "用法: /sub_state <订阅ID> on/off\n示例: /sub_state 123 on"}

    try:
        sub_id = int(parts[0])
    except ValueError:
        return {"plain": "订阅 ID 必须是数字"}

    state_str = parts[1].lower()
    if state_str in ("on", "true", "yes", "y", "1", "开启"):
        enable = True
    elif state_str in ("off", "false", "no", "n", "0", "关闭"):
        enable = False
    else:
        return {
            "plain": "不支持的状态值，请使用: on/off, true/false, yes/no, y/n, 1/0, 开启/关闭"
        }

    user_id = event.get_sender_id()
    result = await deps["sub_state_cmd"].execute(
        sub_id=sub_id, user_id=user_id, enable=enable
    )
    return {"plain": result.message}
