"""RSSHub Plugin Pages Web API

提供基于 AstrBot Plugin Pages bridge 的 HTTP API 处理函数。
所有端点注册为 /astrbot_plugin_rsshub/<endpoint>。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from quart import Response, jsonify, request

from ..infrastructure.config import RsshubPluginConfig, set_config
from ..infrastructure.config.settings_adapter import build_application_settings

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig
    from astrbot.api.star import Context

    from ..application.commands.batch_activate_cmd import BatchActivateCommand
    from ..application.commands.batch_deactivate_cmd import BatchDeactivateCommand
    from ..application.commands.batch_unsubscribe_cmd import BatchUnsubscribeCommand
    from ..application.commands.export_subscriptions_cmd import (
        ExportSubscriptionsCommand,
    )
    from ..application.commands.get_user_settings_cmd import GetUserSettingsCommand
    from ..application.commands.import_subscriptions_cmd import (
        ImportSubscriptionsCommand,
    )
    from ..application.commands.set_user_settings_cmd import SetUserSettingsCommand
    from ..application.commands.subscribe_feed_cmd import SubscribeFeedCommand
    from ..application.commands.test_subscription_cmd import TestSubscriptionCommand
    from ..application.commands.unsubscribe_feed_cmd import UnsubscribeFeedCommand
    from ..application.commands.update_subscription_cmd import UpdateSubscriptionCommand
    from ..application.queries.get_feed_items_query import GetFeedItemsQuery
    from ..application.services.feed_polling_service import FeedPollingService
    from ..domain.repositories.feed_repository import FeedRepository
    from ..domain.repositories.push_history_repository import PushHistoryRepository
    from ..domain.repositories.subscription_repository import SubscriptionRepository
    from ..domain.repositories.user_repository import UserRepository
PLUGIN_NAME = "astrbot_plugin_rsshub"


class WebApiHandler:
    """Web API 处理函数容器

    持有所有命令/查询引用，提供各端点的 async handler。
    """

    def __init__(
        self,
        subscribe_cmd: SubscribeFeedCommand,
        unsubscribe_cmd: UnsubscribeFeedCommand,
        update_sub_cmd: UpdateSubscriptionCommand,
        batch_activate_cmd: BatchActivateCommand,
        batch_deactivate_cmd: BatchDeactivateCommand,
        batch_unsub_cmd: BatchUnsubscribeCommand,
        export_cmd: ExportSubscriptionsCommand,
        import_cmd: ImportSubscriptionsCommand,
        get_user_settings_cmd: GetUserSettingsCommand,
        set_user_settings_cmd: SetUserSettingsCommand,
        test_sub_cmd: TestSubscriptionCommand,
        get_items_query: GetFeedItemsQuery,
        polling_service: FeedPollingService,
        feed_repo: FeedRepository,
        sub_repo: SubscriptionRepository,
        user_repo: UserRepository,
        push_history_repo: PushHistoryRepository,
        config: RsshubPluginConfig | None = None,
        raw_config: AstrBotConfig | None = None,
    ):
        self._sse_clients: list[asyncio.Queue] = []
        self._change_counter: int = 0

        self._subscribe_cmd = subscribe_cmd
        self._unsubscribe_cmd = unsubscribe_cmd
        self._update_sub_cmd = update_sub_cmd
        self._batch_activate_cmd = batch_activate_cmd
        self._batch_deactivate_cmd = batch_deactivate_cmd
        self._batch_unsub_cmd = batch_unsub_cmd
        self._export_cmd = export_cmd
        self._import_cmd = import_cmd
        self._get_user_settings_cmd = get_user_settings_cmd
        self._set_user_settings_cmd = set_user_settings_cmd
        self._test_sub_cmd = test_sub_cmd
        self._get_items_query = get_items_query
        self._polling_service = polling_service
        self._feed_repo = feed_repo
        self._sub_repo = sub_repo
        self._user_repo = user_repo
        self._push_history_repo = push_history_repo
        self._config = config
        self._raw_config = raw_config

    def register_all(self, context: Context) -> None:
        """注册所有 API 端点到 AstrBot"""
        prefix = f"/{PLUGIN_NAME}"

        routes = [
            ("GET", "/events", self.handle_events, "SSE 事件推送"),
            ("GET", "/updates", self.handle_updates, "检查更新"),
            ("GET", "/subscriptions", self.handle_list_subscriptions, "列出所有订阅"),
            ("GET", "/users", self.handle_users, "列出所有用户"),
            ("GET", "/feeds", self.handle_feeds, "列出所有 Feed"),
            ("POST", "/subscribe", self.handle_subscribe, "订阅 RSS"),
            ("POST", "/unsubscribe", self.handle_unsubscribe, "取消订阅"),
            (
                "POST",
                "/subscriptions/update",
                self.handle_update_subscription,
                "更新订阅",
            ),
            ("GET", "/feeds/items", self.handle_feed_items, "获取 Feed 条目"),
            ("POST", "/feeds/refresh", self.handle_refresh_feed, "刷新 Feed"),
            ("GET", "/settings", self.handle_get_settings, "获取用户设置"),
            ("POST", "/settings", self.handle_set_settings, "更新用户设置"),
            (
                "GET",
                "/plugin-settings",
                self.handle_get_plugin_settings,
                "获取插件设置",
            ),
            (
                "POST",
                "/plugin-settings",
                self.handle_set_plugin_settings,
                "更新插件设置",
            ),
            ("POST", "/test-subscription", self.handle_test_subscription, "测试订阅"),
            ("POST", "/test-url", self.handle_test_url, "测试 URL"),
            ("POST", "/batch/activate", self.handle_batch_activate, "批量启用"),
            ("POST", "/batch/deactivate", self.handle_batch_deactivate, "批量禁用"),
            ("POST", "/batch/unsubscribe", self.handle_batch_unsubscribe, "批量取消"),
            ("POST", "/export", self.handle_export, "导出订阅"),
            ("POST", "/import", self.handle_import, "导入订阅"),
            ("GET", "/stats", self.handle_stats, "插件统计"),
            ("GET", "/push-history", self.handle_push_history, "推送历史"),
            (
                "POST",
                "/push-history/delete",
                self.handle_delete_push_history,
                "删除推送历史",
            ),
            (
                "POST",
                "/push-history/cleanup",
                self.handle_cleanup_push_history,
                "清理推送历史",
            ),
            ("GET", "/users/detail", self.handle_user_details, "用户详情列表"),
            ("POST", "/users/update", self.handle_update_user, "更新用户配置"),
            ("POST", "/users/delete", self.handle_delete_user, "删除用户"),
        ]

        for method, endpoint, handler, desc in routes:
            context.register_web_api(
                f"{prefix}{endpoint}",
                handler,
                [method],
                desc,
            )

    # ─── SSE 事件推送 ─────────────────────────────────────────

    def _bump_counter(self) -> None:
        self._change_counter += 1

    async def _broadcast(self, event_data: dict) -> None:
        """向所有 SSE 客户端广播事件"""
        dead: list[asyncio.Queue] = []
        for q in self._sse_clients:
            try:
                q.put_nowait(event_data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._sse_clients.remove(q)

    async def handle_events(self):
        """SSE 事件流端点"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._sse_clients.append(queue)

        async def _stream():
            try:
                yield f"data: {json.dumps({'event': 'connected'})}\n\n"
                while True:
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps(data)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            except (asyncio.CancelledError, GeneratorExit):
                pass
            finally:
                if queue in self._sse_clients:
                    self._sse_clients.remove(queue)

        return Response(
            _stream(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ─── 更新检查 ─────────────────────────────────────────────

    async def handle_updates(self):
        """轻量更新检查（无认证限制，通过 bridge apiGet 代理调用）"""
        return jsonify({"ok": True, "changed": False, "counter": self._change_counter})

    # ─── 订阅列表 ─────────────────────────────────────────────

    async def handle_list_subscriptions(self):
        """列出所有订阅（含 Feed 信息）"""
        user_id = request.args.get("user_id")
        if user_id:
            subs = await self._sub_repo.get_by_user(user_id)
        else:
            subs = await self._sub_repo.get_all_active()
        feed_ids = {s.feed_id for s in subs if s.feed_id}
        feeds: dict[int, Any] = {}
        for fid in feed_ids:
            f = await self._feed_repo.get_by_id(fid)
            if f:
                feeds[fid] = f

        items = []
        for s in subs:
            feed = feeds.get(s.feed_id) if s.feed_id else None
            items.append(
                {
                    "id": s.id,
                    "state": s.state,
                    "user_id": s.user_id,
                    "feed_id": s.feed_id,
                    "feed_title": feed.title if feed else "",
                    "feed_link": feed.link if feed else "",
                    "title": s.title,
                    "tags": s.tags,
                    "target_session": s.target_session,
                    "platform_name": s.platform_name,
                    "interval": s.interval,
                    "notify": s.notify,
                    "send_mode": s.send_mode,
                    "length_limit": s.length_limit,
                    "link_preview": s.link_preview,
                    "display_author": s.display_author,
                    "display_via": s.display_via,
                    "display_title": s.display_title,
                    "display_entry_tags": s.display_entry_tags,
                    "style": s.style,
                    "display_media": s.display_media,
                    "use_sub_config": s.use_sub_config,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
            )

        return jsonify({"ok": True, "items": items, "total": len(items)})

    # ─── 用户列表 ─────────────────────────────────────────────

    async def handle_users(self):
        """列出所有用户及其订阅统计"""
        subs = await self._sub_repo.get_all_active()
        user_map: dict[str, dict] = {}
        for s in subs:
            uid = s.user_id or "unknown"
            if uid not in user_map:
                user_map[uid] = {"user_id": uid, "total": 0, "active": 0}
            user_map[uid]["total"] += 1
            if s.state == 1:
                user_map[uid]["active"] += 1
        return jsonify(
            {"ok": True, "items": list(user_map.values()), "total": len(user_map)}
        )

    async def handle_user_details(self):
        """列出所有用户详情（从 UserRepository）"""
        users = await self._user_repo.get_all(limit=1000)
        items = []
        for u in users:
            items.append(
                {
                    "user_id": u.id,
                    "state": u.state,
                    "interval": u.interval,
                    "notify": u.notify,
                    "send_mode": u.send_mode,
                    "length_limit": u.length_limit,
                    "link_preview": u.link_preview,
                    "display_author": u.display_author,
                    "display_via": u.display_via,
                    "display_title": u.display_title,
                    "display_entry_tags": u.display_entry_tags,
                    "style": u.style,
                    "display_media": u.display_media,
                    "default_target_session": u.default_target_session,
                    "use_user_config": u.use_user_config,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                }
            )
        return jsonify({"ok": True, "items": items, "total": len(items)})

    async def handle_update_user(self):
        """更新用户配置"""
        data = await request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "请求体为空"})

        user_id = data.get("user_id", "")
        settings = data.get("settings", {})
        if not user_id:
            return jsonify({"ok": False, "error": "user_id 不能为空"})

        result = await self._set_user_settings_cmd.execute(
            user_id=user_id, settings=settings
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    async def handle_delete_user(self):
        """删除用户"""
        data = await request.get_json()
        user_id = data.get("user_id", "") if data else ""
        if not user_id:
            return jsonify({"ok": False, "error": "user_id 不能为空"})

        # 先删除用户的所有订阅
        await self._sub_repo.delete_all_by_user(user_id)
        # 再删除用户
        ok = await self._user_repo.delete(user_id)
        if ok:
            self._bump_counter()
            asyncio.create_task(self._broadcast({"event": "data_changed"}))
            return jsonify({"ok": True, "message": f"用户 {user_id} 已删除"})
        return jsonify({"ok": False, "error": "用户不存在或删除失败"})

    # ─── Feed 列表 ────────────────────────────────────────────

    async def handle_feeds(self):
        """列出所有 Feed 源及其订阅统计"""
        feeds = await self._feed_repo.get_all()
        subs = await self._sub_repo.get_all_active()
        sub_counts: dict[int, int] = {}
        for s in subs:
            if s.feed_id:
                sub_counts[s.feed_id] = sub_counts.get(s.feed_id, 0) + 1

        items = []
        for f in feeds:
            items.append(
                {
                    "id": f.id,
                    "title": f.title or "",
                    "link": f.link or "",
                    "state": f.state,
                    "last_modified": f.last_modified.isoformat()
                    if f.last_modified
                    else None,
                    "updated_at": f.updated_at.isoformat() if f.updated_at else None,
                    "subscription_count": sub_counts.get(f.id, 0),
                }
            )
        return jsonify({"ok": True, "items": items, "total": len(items)})

    # ─── 订阅管理 ─────────────────────────────────────────────

    async def handle_subscribe(self):
        """订阅 RSS 源"""
        data = await request.get_json()
        url = (data or {}).get("url", "").strip()
        if not url:
            return jsonify({"ok": False, "error": "url 不能为空"})

        user_id = (data or {}).get("user_id", "webadmin")
        target_session = (data or {}).get("target_session")
        platform_name = (data or {}).get("platform_name")

        result = await self._subscribe_cmd.execute(
            url=url,
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
        )

        resp = {"ok": result.success, "message": result.message}
        if result.data:
            resp["data"] = (
                {"id": result.data.id} if hasattr(result.data, "id") else result.data
            )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify(resp)

    async def handle_unsubscribe(self):
        """取消订阅"""
        data = await request.get_json()
        sub_id = (data or {}).get("sub_id", 0)
        user_id = (data or {}).get("user_id", "webadmin")

        if not sub_id:
            return jsonify({"ok": False, "error": "sub_id 不能为空"})

        result = await self._unsubscribe_cmd.execute(
            sub_id=int(sub_id), user_id=user_id
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    async def handle_update_subscription(self):
        """更新订阅选项"""
        data = await request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "请求体为空"})

        sub_id = data.get("sub_id", 0)
        user_id = data.get("user_id", "webadmin")
        options = data.get("options", {})

        if not sub_id:
            return jsonify({"ok": False, "error": "sub_id 不能为空"})

        result = await self._update_sub_cmd.execute(
            sub_id=int(sub_id),
            user_id=user_id,
            **options,
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    # ─── Feed 操作 ────────────────────────────────────────────

    async def handle_feed_items(self):
        """获取 Feed 条目"""
        feed_id = request.args.get("feed_id", type=int)
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)

        if not feed_id:
            return jsonify({"ok": False, "error": "feed_id 不能为空"})

        result = await self._get_items_query.execute(
            feed_id=feed_id,
            page=page,
            page_size=page_size,
        )

        items = []
        for item in result.items:
            items.append(
                {
                    "title": item.title,
                    "link": item.link,
                    "summary": item.summary[:300] + "..."
                    if item.summary and len(item.summary) > 300
                    else item.summary,
                    "author": item.author,
                    "published_at": item.published_at.isoformat()
                    if item.published_at
                    else None,
                }
            )

        return jsonify(
            {
                "ok": not result.error,
                "items": items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "error": result.error or "",
            }
        )

    async def handle_refresh_feed(self):
        """手动刷新 Feed"""
        data = await request.get_json()
        feed_id = (data or {}).get("feed_id", 0)

        if not feed_id:
            return jsonify({"ok": False, "error": "feed_id 不能为空"})

        try:
            result = await self._polling_service.poll_feed(int(feed_id))
            self._bump_counter()
            asyncio.create_task(self._broadcast({"event": "data_changed"}))
            return jsonify(
                {
                    "ok": result.success,
                    "message": result.message,
                    "status": result.status,
                    "feed_id": result.feed_id,
                    "total_entries": result.total_entries,
                    "new_entries": result.new_entries,
                    "dispatched": result.dispatched,
                    "bootstrap_skipped": result.bootstrap_skipped,
                    "error": result.error,
                }
            )
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    # ─── 用户设置 ─────────────────────────────────────────────

    async def handle_get_settings(self):
        """获取用户默认设置"""
        user_id = request.args.get("user_id", "webadmin")
        result = await self._get_user_settings_cmd.execute(user_id=user_id)
        if result.success and result.data:
            return jsonify({"ok": True, "settings": result.data})
        return jsonify({"ok": False, "error": result.message})

    async def handle_set_settings(self):
        """更新用户默认设置"""
        data = await request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "请求体为空"})

        user_id = data.get("user_id", "webadmin")
        settings = data.get("settings", {})

        result = await self._set_user_settings_cmd.execute(
            user_id=user_id, settings=settings
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    async def handle_get_plugin_settings(self):
        """获取插件级订阅默认值和内容管线配置"""
        if self._config is None:
            return jsonify({"ok": False, "error": "插件配置未初始化"})
        settings = build_application_settings(self._config)
        return jsonify(
            {
                "ok": True,
                "subscription_defaults": _dump_dataclass_like(
                    settings.subscription_defaults
                ),
                "pipeline": _dump_dataclass_like(settings.pipeline),
            }
        )

    async def handle_set_plugin_settings(self):
        """更新插件级订阅默认值和内容管线配置"""
        if self._config is None:
            return jsonify({"ok": False, "error": "插件配置未初始化"})
        if self._raw_config is None or not hasattr(self._raw_config, "save_config"):
            return jsonify({"ok": False, "error": "当前运行环境不支持保存插件配置"})

        data = await request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "请求体为空"})

        pipeline_updates = data.get("pipeline") or {}
        subscription_updates = data.get("subscription_defaults") or {}
        if (
            not isinstance(pipeline_updates, dict)
            or not isinstance(subscription_updates, dict)
        ):
            return jsonify({"ok": False, "error": "配置格式无效"})

        try:
            config_dict = self._config.model_dump()
            if subscription_updates:
                config_dict["global_config"] = {
                    **config_dict.get("global_config", {}),
                    **subscription_updates,
                }
            if pipeline_updates:
                config_dict["pipeline"] = {
                    **config_dict.get("pipeline", {}),
                    **pipeline_updates,
                }

            updated = RsshubPluginConfig.from_astrbot_config(config_dict)
            updated.save(self._raw_config)
            self._config = updated
            set_config(updated)
            self._bump_counter()
            asyncio.create_task(self._broadcast({"event": "settings_changed"}))
            settings = build_application_settings(updated)
            return jsonify(
                {
                    "ok": True,
                    "message": "插件设置已保存，部分运行时设置需重启插件后完全生效",
                    "subscription_defaults": _dump_dataclass_like(
                        settings.subscription_defaults
                    ),
                    "pipeline": _dump_dataclass_like(settings.pipeline),
                }
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": f"保存失败: {exc}"})

    # ─── 测试 ─────────────────────────────────────────────────

    async def handle_test_subscription(self):
        """测试订阅推送"""
        data = await request.get_json()
        sub_id = (data or {}).get("sub_id", 0)
        user_id = (data or {}).get("user_id", "webadmin")

        if not sub_id:
            return jsonify({"ok": False, "error": "sub_id 不能为空"})

        result = await self._test_sub_cmd.execute(sub_id=int(sub_id), user_id=user_id)
        if result.success and result.data:
            return jsonify({"ok": True, "message": result.message, "data": result.data})
        return jsonify({"ok": False, "error": result.message})

    async def handle_test_url(self):
        """测试 URL（无需订阅）"""
        data = await request.get_json()
        url = (data or {}).get("url", "").strip()

        if not url:
            return jsonify({"ok": False, "error": "url 不能为空"})

        result = await self._test_sub_cmd.execute_by_url(url=url)
        if result.success and result.data:
            return jsonify({"ok": True, "message": result.message, "data": result.data})
        return jsonify({"ok": False, "error": result.message})

    # ─── 批量操作 ─────────────────────────────────────────────

    async def handle_batch_activate(self):
        """批量启用订阅"""
        data = await request.get_json()
        sub_ids = (data or {}).get("sub_ids", [])
        user_id = (data or {}).get("user_id", "webadmin")

        if not sub_ids:
            return jsonify({"ok": False, "error": "sub_ids 不能为空"})

        result = await self._batch_activate_cmd.execute(
            sub_ids=sub_ids, user_id=user_id
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    async def handle_batch_deactivate(self):
        """批量禁用订阅"""
        data = await request.get_json()
        sub_ids = (data or {}).get("sub_ids", [])
        user_id = (data or {}).get("user_id", "webadmin")

        if not sub_ids:
            return jsonify({"ok": False, "error": "sub_ids 不能为空"})

        result = await self._batch_deactivate_cmd.execute(
            sub_ids=sub_ids, user_id=user_id
        )
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    async def handle_batch_unsubscribe(self):
        """批量取消订阅"""
        data = await request.get_json()
        sub_ids = (data or {}).get("sub_ids", [])
        user_id = (data or {}).get("user_id", "webadmin")

        if not sub_ids:
            return jsonify({"ok": False, "error": "sub_ids 不能为空"})

        result = await self._batch_unsub_cmd.execute(sub_ids=sub_ids, user_id=user_id)
        self._bump_counter()
        asyncio.create_task(self._broadcast({"event": "data_changed"}))
        return jsonify({"ok": result.success, "message": result.message})

    # ─── 导出 / 统计 ──────────────────────────────────────────

    async def handle_export(self):
        """导出订阅（返回 OPML/TOML 内容）"""
        data = await request.get_json()
        user_id = (data or {}).get("user_id", "webadmin")

        result = await self._export_cmd.execute(user_id=user_id)
        if result.success and result.data:
            return jsonify(
                {
                    "ok": True,
                    "message": result.message,
                    "data": {
                        "content": result.data.content,
                        "filename": result.data.filename,
                        "count": result.data.count,
                    },
                }
            )
        return jsonify({"ok": False, "error": result.message})

    async def handle_import(self):
        """导入 TOML 订阅内容"""
        data = await request.get_json()
        content = (data or {}).get("content", "")
        user_id = (data or {}).get("user_id", "webadmin")
        target_session = (data or {}).get("target_session")
        platform_name = (data or {}).get("platform_name")
        skip_existing = bool((data or {}).get("skip_existing", True))

        if not str(content).strip():
            return jsonify({"ok": False, "error": "content 不能为空"})

        result = await self._import_cmd.execute(
            content=str(content),
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
            skip_existing=skip_existing,
        )
        if result.success:
            self._bump_counter()
            asyncio.create_task(self._broadcast({"event": "data_changed"}))
            payload = {
                "ok": True,
                "message": result.message,
            }
            if result.data:
                payload["data"] = {
                    "total": result.data.total,
                    "success_count": result.data.success_count,
                    "failure_count": result.data.failure_count,
                    "skipped_count": result.data.skipped_count,
                }
            return jsonify(payload)
        return jsonify({"ok": False, "error": result.message})

    async def handle_stats(self):
        """获取插件统计概览"""
        subs = await self._sub_repo.get_all_active()
        all_subs = subs

        total_active = sum(1 for s in all_subs if s.state == 1)
        feed_ids = {s.feed_id for s in all_subs if s.feed_id}
        unique_users = {s.user_id for s in all_subs if s.user_id}

        return jsonify(
            {
                "ok": True,
                "stats": {
                    "total_subscriptions": len(all_subs),
                    "active_subscriptions": total_active,
                    "total_feeds": len(feed_ids),
                    "unique_users": len(unique_users),
                },
            }
        )

    # ─── 推送历史 ─────────────────────────────────────────────

    async def handle_push_history(self):
        """获取推送历史列表"""
        status = request.args.get("status")
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        offset = (page - 1) * page_size

        items = await self._push_history_repo.get_all(
            limit=page_size, offset=offset, status=status
        )
        stats = await self._push_history_repo.get_stats()

        data = []
        for h in items:
            data.append(
                {
                    "id": h.id,
                    "sub_id": h.sub_id,
                    "user_id": h.user_id,
                    "feed_id": h.feed_id,
                    "entry_title": h.entry_title,
                    "entry_link": h.entry_link,
                    "feed_title": h.feed_title,
                    "platform_name": h.platform_name,
                    "target_session": h.target_session,
                    "status": h.status,
                    "retry_count": h.retry_count,
                    "max_retries": h.max_retries,
                    "fail_reason": h.fail_reason,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "updated_at": h.updated_at.isoformat() if h.updated_at else None,
                    "completed_at": h.completed_at.isoformat()
                    if h.completed_at
                    else None,
                }
            )

        return jsonify(
            {
                "ok": True,
                "items": data,
                "total": stats.get("total", 0),
                "page": page,
                "page_size": page_size,
            }
        )

    async def handle_delete_push_history(self):
        """删除推送历史"""
        data = await request.get_json()
        history_id = data.get("history_id", 0) if data else 0
        if not history_id:
            return jsonify({"ok": False, "error": "history_id 不能为空"})
        ok = await self._push_history_repo.delete(int(history_id))
        return jsonify({"ok": ok, "message": "已删除" if ok else "记录不存在"})

    async def handle_cleanup_push_history(self):
        """清理旧推送历史"""
        data = await request.get_json()
        days = data.get("days", 30) if data else 30
        count = await self._push_history_repo.delete_old_records(int(days))
        self._bump_counter()
        return jsonify({"ok": True, "message": f"已清理 {count} 条记录"})


def _dump_dataclass_like(value: Any) -> dict[str, Any]:
    return {
        key: list(item) if isinstance(item, tuple) else item
        for key, item in vars(value).items()
        if not key.startswith("_")
    }
