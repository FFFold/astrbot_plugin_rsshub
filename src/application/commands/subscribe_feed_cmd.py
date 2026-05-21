"""
订阅 Feed 命令

处理用户订阅 RSS 源的业务用例。
"""

from ...domain.entities.feed import Feed
from ...domain.entities.handlers import parse_handlers_input
from ...domain.entities.subscription import SUPPORTED_HANDLERS_MODES
from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...domain.value_objects.feed_url import FeedUrl
from ...infrastructure.utils import get_logger
from ...shared.settings import FeedFetchSettings
from ..dto.result_dto import CommandResult
from ..dto.subscription_dto import SubscriptionDTO
from ..ports import FeedFetcherFactory

logger = get_logger()


class SubscribeFeedCommand:
    """
    订阅 Feed 命令

    处理用户订阅 RSS 源的业务用例。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository,
        fetch_settings: FeedFetchSettings | None = None,
        fetcher_factory: FeedFetcherFactory | None = None,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo
        self._fetch_settings = fetch_settings or FeedFetchSettings()
        self._fetcher_factory = fetcher_factory

    async def execute(
        self,
        url: str,
        user_id: str,
        target_session: str | None = None,
        platform_name: str | None = None,
        session_defaults: dict[str, int | str] | None = None,
    ) -> CommandResult:
        """
        执行订阅命令

        Args:
            url: RSS 源 URL
            user_id: 用户 ID
            target_session: 推送目标会话（可选）
            platform_name: 平台类型名（可选）
            session_defaults: 会话默认配置（可选）

        Returns:
            CommandResult: 命令执行结果
        """
        if not url:
            return CommandResult(
                success=False,
                message="请提供 RSS 链接，用法：/sub <RSS 链接>",
            )

        if not url.startswith(("http://", "https://")):
            return CommandResult(
                success=False,
                message="请提供有效的 RSS 链接（需以 http 或 https 开头）",
            )

        try:
            feed_url = FeedUrl(url)
        except ValueError as e:
            return CommandResult(success=False, message=str(e))

        if self._fetcher_factory is None:
            return CommandResult(
                success=False,
                message="订阅失败：RSS 抓取器未配置",
            )

        # 抓取 Feed 获取标题
        fetcher = self._fetcher_factory(
            timeout=self._fetch_settings.timeout,
            proxy=self._fetch_settings.proxy,
        )
        try:
            web_feed = await fetcher.fetch(feed_url.normalized())
        except Exception as e:
            logger.warning("订阅抓取失败: %s", e)
            return CommandResult(
                success=False,
                message=f"订阅失败：无法获取 RSS 内容 ({e})",
            )
        finally:
            await fetcher.close()

        if web_feed.error:
            return CommandResult(
                success=False,
                message=f"订阅失败：{web_feed.error.error_name}",
            )

        if web_feed.rss_d is None:
            return CommandResult(
                success=False,
                message="订阅失败：无法解析 RSS 内容",
            )

        title = web_feed.rss_d.feed.get("title", url)

        # 查找或创建 Feed
        feed = await self._feed_repo.get_by_link(feed_url.normalized())
        if feed is None:
            feed = Feed(link=feed_url.normalized(), title=title)
            feed = await self._feed_repo.save(feed)
        elif not feed.title and title:
            feed.title = title
            feed = await self._feed_repo.save(feed)

        # 检查重复订阅（同用户 + 同 Feed + 同目标会话）
        existing = await self._subscription_repo.get_by_user_and_feed(user_id, feed.id)
        if existing:
            return CommandResult(
                success=False,
                message=f"您已经订阅了此源：{title}",
            )

        # 创建订阅
        from ...domain.entities.subscription import Subscription

        subscription = Subscription(
            user_id=user_id,
            feed_id=feed.id,
            target_session=target_session,
            platform_name=platform_name,
        )
        subscription = await self._subscription_repo.save(subscription)

        # 应用会话默认设置
        if session_defaults:
            update_payload = {}
            removed_keys = {
                "translate",
                "translate_target_lang",
                "use_sub_config",
                "use_user_config",
            }
            for key, raw_value in session_defaults.items():
                if key in removed_keys:
                    continue
                if key in {"title", "tags"}:
                    update_payload[key] = str(raw_value)
                elif key == "handlers_mode":
                    normalized = str(raw_value or "").strip().lower()
                    if normalized in SUPPORTED_HANDLERS_MODES:
                        update_payload[key] = normalized
                elif key == "handlers":
                    try:
                        update_payload[key] = parse_handlers_input(raw_value)
                    except ValueError:
                        pass
                else:
                    try:
                        update_payload[key] = int(raw_value)
                    except (ValueError, TypeError):
                        pass
            if update_payload:
                await self._subscription_repo.update_options(
                    subscription.id, user_id, **update_payload
                )

        return CommandResult(
            success=True,
            message=(
                f"订阅成功!\n"
                f"源标题：{title}\n"
                f"订阅 ID: {subscription.id}\n"
                f"推送目标：{target_session or '未设置'}"
            ),
            data=SubscriptionDTO(
                id=subscription.id,
                user_id=subscription.user_id,
                feed_id=subscription.feed_id,
                title=subscription.title,
                tags=subscription.tags,
                target_session=subscription.target_session,
                platform_name=subscription.platform_name,
                state=subscription.state,
                created_at=subscription.created_at,
                updated_at=subscription.updated_at,
            ),
        )
