"""批量操作命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def handle_batch_activate(
    event: AstrMessageEvent, sub_ids: str, deps: dict
) -> dict:
    """启用订阅"""
    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin

    if sub_ids:
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return {"plain": "请提供订阅 ID 列表\n用法: /activate_subs 1,2,3"}
        result = await deps["batch_activate_cmd"].execute(sub_ids=ids, user_id=user_id)
    else:
        result = await deps["batch_activate_cmd"].execute_by_session(
            user_id=user_id,
            current_session=current_session,
        )
    return {"plain": result.message}


async def handle_batch_deactivate(
    event: AstrMessageEvent, sub_ids: str, deps: dict
) -> dict:
    """禁用订阅"""
    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin

    if sub_ids:
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return {"plain": "请提供订阅 ID 列表\n用法: /deactivate_subs 1,2,3"}
        result = await deps["batch_deactivate_cmd"].execute(
            sub_ids=ids, user_id=user_id
        )
    else:
        result = await deps["batch_deactivate_cmd"].execute_by_session(
            user_id=user_id,
            current_session=current_session,
        )
    return {"plain": result.message}


async def handle_unsub_all(event: AstrMessageEvent, scope: str, deps: dict) -> dict:
    """取消全部订阅"""
    user_id = event.get_sender_id()
    is_admin = event.is_admin()
    current_session = event.unified_msg_origin

    scope_value = scope.strip().lower() if scope else ""
    is_global = scope_value == "global"

    if is_global and not is_admin:
        return {"plain": "清除所有会话订阅需要管理员权限"}

    subscriptions = await deps["subscription_repo"].get_by_user(user_id)
    if not subscriptions:
        return {"plain": "您当前没有可删除的订阅"}

    if is_global:
        to_delete = subscriptions
        scope_desc = "所有会话"
    else:
        to_delete = [
            sub
            for sub in subscriptions
            if (sub.target_session or current_session) == current_session
        ]
        scope_desc = "当前会话"

    if not to_delete:
        return {"plain": f"当前{scope_desc}没有订阅"}

    # 导出备份
    from pathlib import Path

    export_result = await deps["export_cmd"].execute(user_id=user_id, is_admin=is_admin)
    result: dict = {}

    if export_result.success and export_result.data and export_result.data.content:
        temp_dir = Path("/tmp")
        temp_dir.mkdir(exist_ok=True)
        filename = export_result.data.filename
        file_path = temp_dir / filename
        file_path.write_text(export_result.data.content)
        from astrbot.api.message_components import File

        result["chain"] = [File(name=filename, file=str(file_path))]

    # 删除订阅
    deleted_count = 0
    for sub in to_delete:
        await deps["subscription_repo"].delete(sub)
        deleted_count += 1

    result["plain"] = f"已取消{scope_desc}订阅，共删除 {deleted_count} 条"
    return result


async def handle_batch_unsub(event: AstrMessageEvent, sub_ids: str, deps: dict) -> dict:
    """批量取消订阅"""
    if not sub_ids:
        return {"plain": "请提供订阅 ID 列表\n用法: /batch_unsub 1,2,3"}
    ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
    user_id = event.get_sender_id()
    result = await deps["batch_unsub_cmd"].execute(sub_ids=ids, user_id=user_id)
    return {"plain": result.message}
