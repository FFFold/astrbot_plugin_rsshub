"""导入导出命令处理器（纯函数）"""

from __future__ import annotations

from pathlib import Path

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import File


async def handle_export(event: AstrMessageEvent, deps: dict) -> dict:
    """导出订阅为 OPML"""
    user_id = event.get_sender_id()
    is_admin = event.is_admin()
    result = await deps["export_cmd"].execute(user_id=user_id, is_admin=is_admin)

    if result.data and result.data.content:
        temp_dir = Path("/tmp")
        temp_dir.mkdir(exist_ok=True)
        filename = result.data.filename
        file_path = temp_dir / filename
        file_path.write_text(result.data.content)
        return {
            "chain": [File(name=filename, file=str(file_path))],
            "plain": result.message,
        }
    return {"plain": result.message}


async def handle_import(event: AstrMessageEvent, content: str, deps: dict) -> dict:
    """从 OPML 导入订阅"""
    if not content:
        return {"plain": "请提供 OPML 内容\n用法: /sub_import <opml_content>"}
    user_id = event.get_sender_id()
    target_session = event.unified_msg_origin
    platform_name = event.get_platform_name()
    result = await deps["import_cmd"].execute(
        content=content,
        user_id=user_id,
        target_session=target_session,
        platform_name=platform_name,
    )
    return {"plain": result.message}
