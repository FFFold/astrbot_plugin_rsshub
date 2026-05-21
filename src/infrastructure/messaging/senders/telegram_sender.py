"""Telegram 消息发送器

针对 Telegram 平台的特定优化。
组件排序由 MessageFormatter 统一处理，此处只负责发送。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...config import get_config_manager
from ...pipeline import MessageFormatter
from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .telegraph_client import TelegraphClient
from .types import MessageContext, SendRequest, SendResult

if TYPE_CHECKING:
    pass

logger = get_logger()


class TelegramMessageSender(DefaultMessageSender):
    """Telegram 平台消息发送器

    特性：
    - 媒体优先展示（caption = text）
    - 组件排序由 MessageFormatter 统一（platform="telegram"）
    """

    @staticmethod
    def _strategy_value(strategy, key: str, default=None):
        if strategy is None:
            return default
        if isinstance(strategy, dict):
            return strategy.get(key, default)
        return getattr(strategy, key, default)

    @classmethod
    def _get_timeout_seconds(cls) -> int:
        """Telegram 可能需要更长的超时"""
        return max(1, int(getattr(cls, "_timeout_seconds", 60)))

    @classmethod
    def _should_use_telegraph(
        cls,
        context: MessageContext | None,
        prepared_media,
    ) -> tuple[bool, str]:
        if context is None or context.send_mode != 0:
            return False, ""

        strategy = getattr(context, "sender_strategy", None)
        if strategy is None:
            try:
                config = get_config_manager()
                sender_strategies = getattr(config, "sender_strategies", None)
                strategy = (
                    sender_strategies.get("telegram")
                    if isinstance(sender_strategies, dict)
                    else getattr(
                        sender_strategies,
                        "telegram_settings",
                        getattr(sender_strategies, "telegram", None),
                    )
                )
            except Exception:
                strategy = None

        enabled = bool(cls._strategy_value(strategy, "enable_telegraph", False))
        token = str(cls._strategy_value(strategy, "telegraph_token", "") or "").strip()
        if not enabled or not token:
            return False, ""

        unique_urls = MessageFormatter.collect_original_urls(prepared_media)
        return len(unique_urls) > 1, token

    async def _send_via_telegraph(
        self,
        *,
        session_id: str,
        request: SendRequest,
        context: MessageContext | None,
        prepared_media,
        token: str,
    ) -> SendResult:
        media_urls = MessageFormatter.collect_original_urls(prepared_media)
        client = TelegraphClient(
            access_token=token,
            timeout_seconds=context.timeout_seconds if context else self._get_timeout_seconds(),
        )
        page_url = await client.create_media_page(
            title=context.channel.title if context and context.channel.title else "RSSHub",
            content=request.message,
            media_urls=media_urls,
            channel=context.channel if context else None,
        )
        message = request.message or ""
        message = f"{message}\n\nTelegraph: {page_url}" if message else page_url
        return await self._send_chain(
            session_id,
            self._formatter.build_chain(
                prepared_media=None,
                text=message,
                failed_urls=[],
                platform="telegram",
            ),
        )

    async def send_to_user(
        self,
        request: SendRequest,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到 Telegram 用户

        平台标记为 telegram，由 MessageFormatter 选择 Telegram 专属链式顺序。
        """
        try:
            session_id = request.session_id
            timeout = (
                context.timeout_seconds if context else self._get_timeout_seconds()
            )
            proxy = context.proxy if context else self._get_proxy()

            effective_prepared = request.prepared_media
            if effective_prepared is None and request.media:
                effective_prepared = await self.prepare_media(
                    request.media, timeout=timeout, proxy=proxy
                )

            failed_urls: list[str] = []
            if effective_prepared:
                failed_urls = self._collect_failed_urls(effective_prepared)

            use_telegraph, telegraph_token = self._should_use_telegraph(
                context,
                effective_prepared,
            )
            if use_telegraph:
                try:
                    return await self._send_via_telegraph(
                        session_id=session_id,
                        request=request,
                        context=context,
                        prepared_media=effective_prepared,
                        token=telegraph_token,
                    )
                except Exception as err:
                    logger.warning(
                        "Telegram Telegraph fallback to native send: session=%s, error=%s",
                        session_id,
                        err,
                    )

            chain = self._formatter.build_chain(
                prepared_media=effective_prepared,
                text=request.message,
                failed_urls=failed_urls,
                platform="telegram",
            )

            if not chain:
                return SendResult(ok=False, detail="empty_message")

            return await self._send_chain(session_id, chain)

        except Exception as err:
            logger.error(
                "Telegram send failed: session=%s, error=%s", request.session_id, err
            )
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=self._normalize_error_detail(str(err)),
            )
