"""RSSHub Plugin Pages Web API

提供基于 AstrBot Plugin Pages bridge 的 HTTP API 处理函数。
所有端点注册为 /astrbot_plugin_rsshub/<endpoint>。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from quart import Response, jsonify, request

if TYPE_CHECKING:
    from astrbot.api.star import Context

    from ..application.commands.batch_activate_cmd import BatchActivateCommand
    from ..application.commands.batch_deactivate_cmd import BatchDeactivateCommand
    from ..application.commands.batch_unsubscribe_cmd import BatchUnsubscribeCommand
    from ..application.commands.export_subscriptions_cmd import (
        ExportSubscriptionsCommand,
    )
    from ..application.commands.get_user_settings_cmd import GetUserSettingsCommand
    from ..application.commands.set_user_settings_cmd import SetUserSettingsCommand
    from ..application.commands.subscribe_feed_cmd import SubscribeFeedCommand
    from ..application.commands.test_subscription_cmd import TestSubscriptionCommand
    from ..application.commands.unsubscribe_feed_cmd import UnsubscribeFeedCommand
    from ..application.commands.update_subscription_cmd import UpdateSubscriptionCommand
    from ..application.queries.get_feed_items_query import GetFeedItemsQuery
    from ..application.services.feed_polling_service import FeedPollingService
    from ..domain.repositories.feed_repository import FeedRepository
    from ..domain.repositories.subscription_repository import SubscriptionRepository
    from ..infrastructure.config.config_manager import RsshubPluginConfig

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
        get_user_settings_cmd: GetUserSettingsCommand,
        set_user_settings_cmd: SetUserSettingsCommand,
        test_sub_cmd: TestSubscriptionCommand,
        get_items_query: GetFeedItemsQuery,
        polling_service: FeedPollingService,
        feed_repo: FeedRepository,
        sub_repo: SubscriptionRepository,
        config: RsshubPluginConfig | None = None,
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
        self._get_user_settings_cmd = get_user_settings_cmd
        self._set_user_settings_cmd = set_user_settings_cmd
        self._test_sub_cmd = test_sub_cmd
        self._get_items_query = get_items_query
        self._polling_service = polling_service
        self._feed_repo = feed_repo
        self._sub_repo = sub_repo
        self._config = config

    def register_all(self, context: Context) -> None:
        """注册所有 API 端点到 AstrBot"""
        prefix = f"/{PLUGIN_NAME}"

        routes = [
            ("GET", "/events", self.handle_events, "SSE 事件推送"),
            ("GET", "/updates", self.handle_updates, "检查更新"),
            ("GET", "/subscriptions", self.handle_list_subscriptions, "列出所有订阅"),
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
            ("POST", "/test-subscription", self.handle_test_subscription, "测试订阅"),
            ("POST", "/test-url", self.handle_test_url, "测试 URL"),
            ("POST", "/batch/activate", self.handle_batch_activate, "批量启用"),
            ("POST", "/batch/deactivate", self.handle_batch_deactivate, "批量禁用"),
            ("POST", "/batch/unsubscribe", self.handle_batch_unsubscribe, "批量取消"),
            ("POST", "/export", self.handle_export, "导出订阅"),
            ("GET", "/stats", self.handle_stats, "插件统计"),
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
                    "translate": s.translate,
                    "translate_target_lang": s.translate_target_lang,
                    "use_sub_config": s.use_sub_config,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
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
