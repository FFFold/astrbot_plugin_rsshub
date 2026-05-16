"""RSSHub 插件入口"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from astrbot.api import AstrBotConfig
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
    SubStateCommand,
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
from .src.application.settings import ApplicationSettings
from .src.domain.repositories.subscription_repository import SubscriptionRepository
from .src.infrastructure.config import (
    RsshubPluginConfig,
    get_config_manager,
    set_config,
)
from .src.infrastructure.fetcher.rss import RSSFeedFetcher
from .src.infrastructure.fetcher.rss.parser import RSSParser
from .src.infrastructure.messaging import (
    InfrastructureMessageSenderProvider,
    get_notification_service,
)
from .src.infrastructure.persistence import (
    get_database,
    get_feed_repository,
    get_push_history_repository,
    get_subscription_repository,
    get_user_repository,
)
from .src.infrastructure.schedule import RSSScheduler
from .src.infrastructure.utils import get_logger
from .src.interfaces import WebApiHandler
from .src.interfaces import handlers as _h

logger = get_logger()


class _Deps(TypedDict):
    subscribe_cmd: SubscribeFeedCommand
    unsubscribe_cmd: UnsubscribeFeedCommand
    sub_state_cmd: SubStateCommand
    refresh_cmd: RefreshFeedCommand
    update_sub_cmd: UpdateSubscriptionCommand
    list_query: GetFeedListQuery
    batch_activate_cmd: BatchActivateCommand
    batch_deactivate_cmd: BatchDeactivateCommand
    batch_unsub_cmd: BatchUnsubscribeCommand
    export_cmd: ExportSubscriptionsCommand
    import_cmd: ImportSubscriptionsCommand
    get_user_settings_cmd: GetUserSettingsCommand
    set_user_settings_cmd: SetUserSettingsCommand
    test_sub_cmd: TestSubscriptionCommand
    get_subs_query: GetSubscriptionsQuery
    get_items_query: GetFeedItemsQuery
    search_feeds_query: SearchFeedsQuery
    sync_service: FeedSyncService
    subscription_repo: SubscriptionRepository


class Main(Star):
    """RSS订阅推送插件"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self._config = config
        self._scheduler: RSSScheduler | None = None
        self._db_initialized = False
        self._web_api: WebApiHandler | None = None
        self._deps: _Deps = {}
        self._app_settings = ApplicationSettings()
        self._sender_provider = InfrastructureMessageSenderProvider()

    async def initialize(self):
        try:
            logger.info("正在初始化 RSSHub 插件...")
            await self._init_config()
            await self._init_database()
            self._init_repositories()
            await self._init_scheduler()
            self._init_web_api()
            logger.info("RSSHub 插件初始化完成")
        except Exception as e:
            logger.exception("RSSHub 插件初始化失败: %s", e)

    async def terminate(self):
        logger.info("正在停止 RSSHub 插件...")
        if self._scheduler:
            await self._scheduler.stop()
        db = get_database()
        if db:
            await db.close()
        logger.info("RSSHub 插件已停止")

    # ── 命令方法（装饰器留在 Main，委托到纯函数） ────────────────────────────

    async def _init_config(self):
        raw_config = dict(self._config) if self._config else {}
        plugin_config = RsshubPluginConfig.from_astrbot_config(raw_config)
        set_config(plugin_config)
        self._app_settings = ApplicationSettings.from_config(plugin_config)
        self._sender_provider = InfrastructureMessageSenderProvider(
            self._app_settings.sender_strategies
        )
        logger.debug("配置已加载")

    async def _init_database(self):
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
        feed_repo = get_feed_repository()
        sub_repo = get_subscription_repository()
        user_repo = get_user_repository()

        self._deps = _Deps(
            subscribe_cmd=SubscribeFeedCommand(
                subscription_repo=sub_repo,
                feed_repo=feed_repo,
                fetch_settings=self._app_settings.fetch,
                fetcher_factory=RSSFeedFetcher,
            ),
            unsubscribe_cmd=UnsubscribeFeedCommand(
                subscription_repo=sub_repo, feed_repo=feed_repo
            ),
            sub_state_cmd=SubStateCommand(subscription_repo=sub_repo),
            refresh_cmd=RefreshFeedCommand(
                feed_repo=feed_repo,
                fetch_settings=self._app_settings.fetch,
                fetcher_factory=RSSFeedFetcher,
            ),
            update_sub_cmd=UpdateSubscriptionCommand(subscription_repo=sub_repo),
            list_query=GetFeedListQuery(
                subscription_repo=sub_repo, feed_repo=feed_repo
            ),
            batch_activate_cmd=BatchActivateCommand(subscription_repo=sub_repo),
            batch_deactivate_cmd=BatchDeactivateCommand(subscription_repo=sub_repo),
            batch_unsub_cmd=BatchUnsubscribeCommand(subscription_repo=sub_repo),
            export_cmd=ExportSubscriptionsCommand(
                subscription_repo=sub_repo, feed_repo=feed_repo
            ),
            import_cmd=ImportSubscriptionsCommand(
                subscription_repo=sub_repo, feed_repo=feed_repo
            ),
            get_user_settings_cmd=GetUserSettingsCommand(user_repo=user_repo),
            set_user_settings_cmd=SetUserSettingsCommand(user_repo=user_repo),
            test_sub_cmd=TestSubscriptionCommand(
                subscription_repo=sub_repo,
                feed_repo=feed_repo,
                fetcher=RSSFeedFetcher(),
                parser=RSSParser(),
            ),
            get_subs_query=GetSubscriptionsQuery(subscription_repo=sub_repo),
            get_items_query=GetFeedItemsQuery(feed_repo=feed_repo),
            search_feeds_query=SearchFeedsQuery(feed_repo=feed_repo),
            sync_service=FeedSyncService(
                feed_repo=feed_repo,
                subscription_repo=sub_repo,
                fetch_settings=self._app_settings.fetch,
                fetcher_factory=RSSFeedFetcher,
                parser=RSSParser(),
            ),
            subscription_repo=sub_repo,
        )

    async def _init_scheduler(self):
        config = get_config_manager()
        sub_repo = get_subscription_repository()
        push_history_repo = get_push_history_repository()

        notification_svc = get_notification_service(
            subscription_repo=sub_repo,
            push_history_repo=push_history_repo,
            sender_provider=self._sender_provider,
        )

        basic = config.basic_config if config else None
        self._scheduler = RSSScheduler(
            notification_service=notification_svc,
            hash_history_min=getattr(basic, "hash_history_min", 200),
            hash_history_multiplier=getattr(basic, "hash_history_multiplier", 2),
            hash_history_hard_limit=getattr(basic, "hash_history_hard_limit", 5000),
            bootstrap_skip_history=getattr(basic, "bootstrap_skip_history", True),
            history_entry_limit=getattr(basic, "history_entry_limit", 0),
            sender_provider=self._sender_provider,
        )

        await self._scheduler.start()

        import asyncio

        async def _run_periodic():
            while self._scheduler and self._scheduler._running:
                try:
                    await self._scheduler.run_periodic_task()
                except Exception as e:
                    logger.exception("RSS 定时任务执行异常: %s", e)
                await asyncio.sleep(60)

        self._bg_scheduler_task = asyncio.create_task(_run_periodic())
        logger.info("RSS 调度器已启动并开始定时检查")

    def _init_web_api(self):
        config = get_config_manager()
        feed_repo = get_feed_repository()
        sub_repo = get_subscription_repository()

        self._web_api = WebApiHandler(
            subscribe_cmd=self._deps["subscribe_cmd"],
            unsubscribe_cmd=self._deps["unsubscribe_cmd"],
            update_sub_cmd=self._deps["update_sub_cmd"],
            batch_activate_cmd=self._deps["batch_activate_cmd"],
            batch_deactivate_cmd=self._deps["batch_deactivate_cmd"],
            batch_unsub_cmd=self._deps["batch_unsub_cmd"],
            export_cmd=self._deps["export_cmd"],
            get_user_settings_cmd=self._deps["get_user_settings_cmd"],
            set_user_settings_cmd=self._deps["set_user_settings_cmd"],
            test_sub_cmd=self._deps["test_sub_cmd"],
            get_items_query=self._deps["get_items_query"],
            sync_service=self._deps["sync_service"],
            feed_repo=feed_repo,
            sub_repo=sub_repo,
            config=config,
        )
        self._web_api.register_all(self.context)
        logger.info("Web API 已注册")

    # ── 命令方法（装饰器留在 Main，委托到纯函数） ────────────────────────────

    @filter.command("sub", alias={"订阅"})
    async def sub_feed(self, event: AstrMessageEvent, url: str = ""):
        result = await _h.handle_sub(event, url, self._deps)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("unsub")
    async def unsub_feed(self, event: AstrMessageEvent, sub_id: int = 0):
        result = await _h.handle_unsub(event, sub_id, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_list", alias={"订阅列表"})
    async def sub_list(self, event: AstrMessageEvent):
        result = await _h.handle_sub_list(event, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("refresh")
    async def refresh_feed(self, event: AstrMessageEvent, feed_id: int = 0):
        result = await _h.handle_refresh(event, feed_id, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_state", alias={"订阅状态"})
    async def sub_state(self, event: AstrMessageEvent, sub_id_str: str = ""):
        result = await _h.handle_sub_state(event, sub_id_str, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_set", alias={"设置订阅"})
    async def sub_set(
        self,
        event: AstrMessageEvent,
        sub_id: int = 0,
        option: str = "",
        value: str = "",
    ):
        result = await _h.handle_sub_set(event, sub_id, option, value, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_set_user", alias={"设置用户"})
    async def sub_set_user(
        self, event: AstrMessageEvent, key: str = "", value: str = ""
    ):
        result = await _h.handle_sub_set_user(event, key, value, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_get_user", alias={"获取用户"})
    async def sub_get_user(self, event: AstrMessageEvent, key: str = ""):
        result = await _h.handle_sub_get_user(event, key, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_set_session", alias={"设置会话"})
    async def sub_set_session(
        self, event: AstrMessageEvent, key: str = "", value: str = ""
    ):
        result = await _h.handle_sub_set_session(
            event, key, value, self._deps, self.context
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_get_session", alias={"获取会话"})
    async def sub_get_session(self, event: AstrMessageEvent, key: str = ""):
        result = await _h.handle_sub_get_session(event, key, self._deps, self.context)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("activate_subs", alias={"enable_subs", "启用全部订阅"})
    async def batch_activate(self, event: AstrMessageEvent, sub_ids: str = ""):
        result = await _h.handle_batch_activate(event, sub_ids, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("deactivate_subs", alias={"disable_subs", "禁用全部订阅"})
    async def batch_deactivate(self, event: AstrMessageEvent, sub_ids: str = ""):
        result = await _h.handle_batch_deactivate(event, sub_ids, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("unsub_all", alias={"取消全部订阅"})
    async def unsub_all(self, event: AstrMessageEvent, scope: str = ""):
        result = await _h.handle_unsub_all(event, scope, self._deps)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("batch_unsub")
    async def batch_unsub(self, event: AstrMessageEvent, sub_ids: str = ""):
        result = await _h.handle_batch_unsub(event, sub_ids, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_export", alias={"导出订阅"})
    async def export_subs(self, event: AstrMessageEvent):
        result = await _h.handle_export(event, self._deps)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_import", alias={"导入订阅"})
    async def import_subs(self, event: AstrMessageEvent, content: str = ""):
        result = await _h.handle_import(event, content, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("test_sub", alias={"测试订阅"})
    async def test_sub(self, event: AstrMessageEvent, sub_id: int = 0):
        result = await _h.handle_test_sub(event, sub_id, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("rsshub_admin")
    async def admin_panel(self, event: AstrMessageEvent, action: str = ""):
        result = await _h.handle_admin_panel(event, action, self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])
