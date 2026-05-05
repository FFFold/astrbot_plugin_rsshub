"""RSSHub 插件入口

基于 DDD 架构的 RSS 订阅推送插件。
"""

from __future__ import annotations

from pathlib import Path

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .src.application.commands import (
    BatchActivateCommand,
    BatchDeactivateCommand,
    BatchUnsubscribeCommand,
    ExportSubscriptionsCommand,
    GetUserSettingsCommand,
    ImportSubscriptionsCommand,
    RefreshFeedCommand,
    SetUserSettingsCommand,
    SubscribeFeedCommand,
    TestSubscriptionCommand,
    UnsubscribeFeedCommand,
    UpdateSubscriptionCommand,
)
from .src.application.queries import (
    GetFeedItemsQuery,
    GetFeedListQuery,
    GetSubscriptionsQuery,
    SearchFeedsQuery,
)
from .src.application.services import FeedSyncService
from .src.infrastructure.config import (
    RsshubPluginConfig,
    get_config_manager,
    set_config,
)
from .src.infrastructure.fetcher.rss import RSSFeedFetcher
from .src.infrastructure.fetcher.rss.parser import RSSParser
from .src.infrastructure.messaging import get_notification_service
from .src.infrastructure.persistence import (
    get_database,
    get_feed_repository,
    get_push_history_repository,
    get_subscription_repository,
    get_user_repository,
)
from .src.infrastructure.schedule import RSSScheduler
from .src.infrastructure.utils import get_logger
from astrbot.api import AstrBotConfig

logger = get_logger()


class Main(Star):
    """RSS订阅推送插件 - 多平台支持，定时监控RSS源并推送更新"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self._config = config

        self._scheduler: RSSScheduler | None = None
        self._db_initialized = False

        self._subscribe_cmd: SubscribeFeedCommand | None = None
        self._unsubscribe_cmd: UnsubscribeFeedCommand | None = None
        self._refresh_cmd: RefreshFeedCommand | None = None
        self._update_sub_cmd: UpdateSubscriptionCommand | None = None
        self._list_query: GetFeedListQuery | None = None
        self._batch_activate_cmd: BatchActivateCommand | None = None
        self._batch_deactivate_cmd: BatchDeactivateCommand | None = None
        self._batch_unsub_cmd: BatchUnsubscribeCommand | None = None
        self._export_cmd: ExportSubscriptionsCommand | None = None
        self._import_cmd: ImportSubscriptionsCommand | None = None
        self._get_user_settings_cmd: GetUserSettingsCommand | None = None
        self._set_user_settings_cmd: SetUserSettingsCommand | None = None
        self._test_sub_cmd: TestSubscriptionCommand | None = None
        self._get_subs_query: GetSubscriptionsQuery | None = None
        self._get_items_query: GetFeedItemsQuery | None = None
        self._search_feeds_query: SearchFeedsQuery | None = None
        self._sync_service: FeedSyncService | None = None

    async def initialize(self):
        """初始化插件"""
        try:
            logger.info("正在初始化 RSSHub 插件...")

            await self._init_config()
            await self._init_database()
            self._init_repositories()
            self._init_scheduler()

            logger.info("RSSHub 插件初始化完成")
        except Exception as e:
            logger.exception("RSSHub 插件初始化失败: %s", e)

    async def terminate(self):
        """停止插件"""
        logger.info("正在停止 RSSHub 插件...")
        if self._scheduler:
            await self._scheduler.stop()
        db = get_database()
        if db:
            await db.close()
        logger.info("RSSHub 插件已停止")

    async def _init_config(self):
        """初始化配置"""
        raw_config = dict(self._config) if self._config else {}
        plugin_config = RsshubPluginConfig.from_astrbot_config(raw_config)
        set_config(plugin_config)
        logger.debug("配置已加载")

    async def _init_database(self):
        """初始化数据库"""
        from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

        config = get_config_manager()
        db_file = config.db_file if config else "rsshub.db"
        data_dir = Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_rsshub"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / db_file)

        db = get_database()
        await db.init(db_path)
        self._db_initialized = True
        logger.info("数据库已初始化: %s", db_path)

    def _init_repositories(self):
        """初始化仓库和命令"""
        feed_repo = get_feed_repository()
        sub_repo = get_subscription_repository()
        user_repo = get_user_repository()
        push_history_repo = get_push_history_repository()

        self._subscribe_cmd = SubscribeFeedCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
        )
        self._unsubscribe_cmd = UnsubscribeFeedCommand(
            subscription_repo=sub_repo,
        )
        self._refresh_cmd = RefreshFeedCommand(
            feed_repo=feed_repo,
        )
        self._update_sub_cmd = UpdateSubscriptionCommand(
            subscription_repo=sub_repo,
        )
        self._list_query = GetFeedListQuery(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
        )
        self._batch_activate_cmd = BatchActivateCommand(
            subscription_repo=sub_repo,
        )
        self._batch_deactivate_cmd = BatchDeactivateCommand(
            subscription_repo=sub_repo,
        )
        self._batch_unsub_cmd = BatchUnsubscribeCommand(
            subscription_repo=sub_repo,
        )
        self._export_cmd = ExportSubscriptionsCommand(
            subscription_repo=sub_repo,
        )
        self._import_cmd = ImportSubscriptionsCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
        )
        self._get_user_settings_cmd = GetUserSettingsCommand(
            user_repo=user_repo,
        )
        self._set_user_settings_cmd = SetUserSettingsCommand(
            user_repo=user_repo,
        )
        self._test_sub_cmd = TestSubscriptionCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
            fetcher=RSSFeedFetcher(),
            parser=RSSParser(),
        )
        self._get_subs_query = GetSubscriptionsQuery(
            subscription_repo=sub_repo,
        )
        self._get_items_query = GetFeedItemsQuery(
            feed_repo=feed_repo,
        )
        self._search_feeds_query = SearchFeedsQuery(
            feed_repo=feed_repo,
        )
        self._sync_service = FeedSyncService(
            feed_repo=feed_repo,
            subscription_repo=sub_repo,
        )

    def _init_scheduler(self):
        """初始化调度器"""
        config = get_config_manager()
        feed_repo = get_feed_repository()
        sub_repo = get_subscription_repository()
        push_history_repo = get_push_history_repository()

        notification_svc = get_notification_service(
            subscription_repo=sub_repo,
            push_history_repo=push_history_repo,
        )

        basic = config.basic_config if config else None
        self._scheduler = RSSScheduler(
            notification_service=notification_svc,
            hash_history_min=getattr(basic, "hash_history_min", 200),
            hash_history_multiplier=getattr(basic, "hash_history_multiplier", 2),
            hash_history_hard_limit=getattr(basic, "hash_history_hard_limit", 5000),
            bootstrap_skip_history=getattr(basic, "bootstrap_skip_history", True),
            history_entry_limit=getattr(basic, "history_entry_limit", 0),
        )

    @filter.command("sub")
    async def sub_feed(self, event: AstrMessageEvent, url: str = ""):
        """订阅 RSS 源
        用法: /sub <url>
        """
        if not url:
            yield event.plain_result("请提供 RSS 源的 URL\n用法: /sub <url>")
            return
        user_id = event.get_sender_id()
        target_session = event.unified_msg_origin
        platform_name = event.get_platform_name()
        result = await self._subscribe_cmd.execute(
            url=url,
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
        )
        yield event.plain_result(result.message)

    @filter.command("unsub")
    async def unsub_feed(self, event: AstrMessageEvent, sub_id: int = 0):
        """取消订阅
        用法: /unsub <订阅ID>
        """
        if sub_id <= 0:
            yield event.plain_result("请提供订阅 ID\n用法: /unsub <ID>")
            return
        user_id = event.get_sender_id()
        result = await self._unsubscribe_cmd.execute(sub_id=sub_id, user_id=user_id)
        yield event.plain_result(result.message)

    @filter.command("list")
    async def list_subs(self, event: AstrMessageEvent):
        """列出所有订阅"""
        user_id = event.get_sender_id()
        result = await self._list_query.execute(user_id=user_id)
        if not result.feeds:
            yield event.plain_result("暂无订阅\n使用 /sub <url> 添加订阅")
            return
        lines = [f"📡 订阅列表 (共 {result.total} 个):"]
        for i, feed in enumerate(result.feeds, 1):
            title = feed.title or feed.link
            lines.append(f"{i}. [{feed.id}] {title[:60]}")
        yield event.plain_result("\n".join(lines))

    @filter.command("refresh")
    async def refresh_feed(self, event: AstrMessageEvent, feed_id: int = 0):
        """手动刷新订阅
        用法: /refresh <feed_id>
        """
        if feed_id <= 0:
            yield event.plain_result("请提供 Feed ID\n用法: /refresh <feed_id>")
            return
        await self._sync_service.sync_feed(feed_id)
        yield event.plain_result(f"Feed {feed_id} 刷新完成")

    @filter.command("sub_set")
    async def sub_set(
        self,
        event: AstrMessageEvent,
        sub_id: int = 0,
        option: str = "",
        value: str = "",
    ):
        """修改订阅配置
        用法: /sub_set <sub_id> <option> <value>
        """
        if sub_id <= 0 or not option:
            yield event.plain_result(
                "用法: /sub_set <sub_id> <option> <value>\n示例: /sub_set 1 interval 30"
            )
            return
        user_id = event.get_sender_id()
        result = await self._update_sub_cmd.execute(
            sub_id=sub_id,
            user_id=user_id,
            **{option: value},
        )
        yield event.plain_result(result.message)

    @filter.command("sub_list")
    async def sub_list(self, event: AstrMessageEvent):
        """查看订阅详情"""
        user_id = event.get_sender_id()
        result = await self._get_subs_query.execute(user_id=user_id)
        lines = []
        for sub in result.subscriptions:
            title = sub.title or f"Feed #{sub.feed_id}"
            lines.append(
                f"[{sub.id}] {title[:40]} - {'启用' if sub.state == 1 else '停用'}"
            )
        if not lines:
            yield event.plain_result("暂无订阅")
            return
        yield event.plain_result("\n".join(lines))

    @filter.command("batch_active")
    async def batch_activate(self, event: AstrMessageEvent, sub_ids: str = ""):
        """批量启用订阅
        用法: /batch_active <id1,id2,...>
        """
        if not sub_ids:
            yield event.plain_result("请提供订阅 ID 列表\n用法: /batch_active 1,2,3")
            return
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        user_id = event.get_sender_id()
        result = await self._batch_activate_cmd.execute(sub_ids=ids, user_id=user_id)
        yield event.plain_result(result.message)

    @filter.command("batch_deactivate")
    async def batch_deactivate(self, event: AstrMessageEvent, sub_ids: str = ""):
        """批量停用订阅
        用法: /batch_deactivate <id1,id2,...>
        """
        if not sub_ids:
            yield event.plain_result(
                "请提供订阅 ID 列表\n用法: /batch_deactivate 1,2,3"
            )
            return
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        user_id = event.get_sender_id()
        result = await self._batch_deactivate_cmd.execute(sub_ids=ids, user_id=user_id)
        yield event.plain_result(result.message)

    @filter.command("batch_unsub")
    async def batch_unsub(self, event: AstrMessageEvent, sub_ids: str = ""):
        """批量取消订阅
        用法: /batch_unsub <id1,id2,...>
        """
        if not sub_ids:
            yield event.plain_result("请提供订阅 ID 列表\n用法: /batch_unsub 1,2,3")
            return
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        user_id = event.get_sender_id()
        result = await self._batch_unsub_cmd.execute(sub_ids=ids, user_id=user_id)
        yield event.plain_result(result.message)

    @filter.command("export")
    async def export_subs(self, event: AstrMessageEvent):
        """导出订阅为 OPML"""
        user_id = event.get_sender_id()
        result = await self._export_cmd.execute(user_id=user_id)
        yield event.plain_result(result.message)

    @filter.command("import")
    async def import_subs(self, event: AstrMessageEvent, content: str = ""):
        """从 OPML 导入订阅
        用法: /import <opml_content>
        """
        if not content:
            yield event.plain_result("请提供 OPML 内容\n用法: /import <opml_content>")
            return
        user_id = event.get_sender_id()
        target_session = event.unified_msg_origin
        platform_name = event.get_platform_name()
        result = await self._import_cmd.execute(
            content=content,
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
        )
        yield event.plain_result(result.message)

    @filter.command("test_sub")
    async def test_sub(self, event: AstrMessageEvent, sub_id: int = 0):
        """测试订阅推送
        用法: /test_sub <sub_id>
        """
        if sub_id <= 0:
            yield event.plain_result("请提供订阅 ID\n用法: /test_sub <ID>")
            return
        user_id = event.get_sender_id()
        result = await self._test_sub_cmd.execute(sub_id=sub_id, user_id=user_id)
        yield event.plain_result(result.message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("rsshub_admin")
    async def admin_panel(self, event: AstrMessageEvent, action: str = ""):
        """RSSHub 管理面板
        用法: /rsshub_admin <action>
        """
        if action == "stats":
            yield event.plain_result("RSSHub 插件运行中")
        elif action == "restart":
            if self._scheduler:
                await self._scheduler.stop()
                self._init_scheduler()
                await self._scheduler.start()
            yield event.plain_result("调度器已重启")
        else:
            yield event.plain_result(
                "RSSHub 管理命令:\n"
                "  /rsshub_admin stats - 查看状态\n"
                "  /rsshub_admin restart - 重启调度器"
            )
