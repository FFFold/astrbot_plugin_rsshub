"""管理员命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def handle_test_sub(event: AstrMessageEvent, sub_id: int, deps: dict) -> dict:
    """测试订阅推送"""
    args = sub_id.strip() if isinstance(sub_id, str) else str(sub_id).strip()
    if not args:
        return {"plain": "请提供目标\n用法: /sub_test <ID|URL> [start] [end]"}

    parts = [p.strip() for p in args.split() if p.strip()]
    target = parts[0]

    try:
        start = int(parts[1]) if len(parts) >= 2 else 1
        end = int(parts[2]) if len(parts) >= 3 else start
    except ValueError:
        return {"plain": "条目编号必须是数字，用法: /sub_test <ID|URL> [start] [end]"}

    if start <= 0 or end <= 0:
        return {"plain": "条目编号从 1 开始"}
    if end < start:
        return {"plain": "结束编号不能小于起始编号"}

    user_id = event.get_sender_id()
    result = await deps["test_sub_cmd"].execute_target(
        target=target,
        user_id=user_id,
        target_session=event.unified_msg_origin,
        platform_name=event.get_platform_name(),
        start=start,
        end=end,
        event=event,
    )
    return {"plain": result.message}
