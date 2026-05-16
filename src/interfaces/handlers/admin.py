"""管理员命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def handle_test_sub(event: AstrMessageEvent, sub_id: int, deps: dict) -> dict:
    """测试订阅推送"""
    if sub_id <= 0:
        return {"plain": "请提供订阅 ID\n用法: /test_sub <ID>"}
    user_id = event.get_sender_id()
    result = await deps["test_sub_cmd"].execute(sub_id=sub_id, user_id=user_id)
    return {"plain": result.message}


async def handle_admin_panel(event: AstrMessageEvent, action: str, deps: dict) -> dict:
    """RSSHub 管理面板"""
    if action == "stats":
        return {"plain": "RSSHub 插件运行中"}
    elif action == "restart":
        return {"plain": "请通过重启 AstrBot 来重启调度器"}
    else:
        return {
            "plain": "RSSHub 管理命令:\n  /rsshub_admin stats - 查看状态\n  /rsshub_admin restart - 重启调度器"
        }
