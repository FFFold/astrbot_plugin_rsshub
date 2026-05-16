"""基础消息发送器

提供跨平台消息发送的默认实现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.star_tools import StarTools

from ...pipeline import MessageFormatter
from ...utils import get_logger
from ...utils.caching import caching
from ...utils.lock import locked
from .types import MessageContext, PreparedMedia, SendRequest, SendResult

if TYPE_CHECKING:
    pass

logger = get_logger()


class DefaultMessageSender:
    """默认跨平台发送器策略

    提供基础的消息发送和媒体处理功能。
    组件排序统一由 MessageFormatter 决定，此处只负责发送。
    """

    _timeout_seconds: int = 30
    _proxy: str = ""
    _download_media_before_send: bool = True

    _formatter: MessageFormatter = MessageFormatter()

    @classmethod
    def configure_runtime(cls, *, timeout_seconds: int, proxy: str = "") -> None:
        """配置运行时参数"""
        DefaultMessageSender._timeout_seconds = max(1, int(timeout_seconds))
        DefaultMessageSender._proxy = proxy or ""

    @classmethod
    def configure_behavior(
        cls,
        *,
        download_media_before_send: bool,
    ) -> None:
        """配置发送行为"""
        cls._download_media_before_send = bool(download_media_before_send)

    @classmethod
    def _get_timeout_seconds(cls) -> int:
        return max(1, int(getattr(cls, "_timeout_seconds", 30)))

    @classmethod
    def _get_proxy(cls) -> str:
        proxy = getattr(cls, "_proxy", None)
        if proxy is None:
            proxy = getattr(DefaultMessageSender, "_proxy", None)
        return str(proxy or "")

    @classmethod
    def _should_download_media_before_send(cls) -> bool:
        return bool(getattr(cls, "_download_media_before_send", True))

    @caching("media_cache", key="#media", ttl=900)
    async def prepare_media(
        self,
        media: list[tuple[str, str]] | None,
        timeout: int = 30,
        proxy: str = "",
    ) -> list[PreparedMedia]:
        """预处理媒体文件（使用缓存装饰器）"""
        if not media:
            return []

        prepared: list[PreparedMedia] = []
        seen_urls: set[str] = set()

        from ...media import MediaDownloader

        downloader = MediaDownloader()

        for media_type, media_url in media:
            if not media_url:
                continue
            if media_type not in {"image", "audio", "video", "file"}:
                continue

            if media_url in seen_urls:
                prepared.append(
                    PreparedMedia(
                        media_type=media_type,
                        original_url=media_url,
                    )
                )
                continue

            seen_urls.add(media_url)

            if not self._should_download_media_before_send():
                prepared.append(
                    PreparedMedia(media_type=media_type, original_url=media_url)
                )
                continue

            try:
                local_path = await downloader.get_or_download(
                    url=media_url,
                    timeout_seconds=timeout,
                    proxy=proxy,
                )
                prepared.append(
                    PreparedMedia(
                        media_type=media_type,
                        original_url=media_url,
                        local_path=local_path,
                    )
                )
            except Exception as ex:
                prepared.append(
                    PreparedMedia(
                        media_type=media_type,
                        original_url=media_url,
                        download_failed=True,
                    )
                )
                logger.warning(
                    "Prepare media failed: type=%s, url=%s, err=%s",
                    media_type,
                    media_url,
                    ex,
                )

        return prepared

    @staticmethod
    def _is_transient_network_error(err: Exception) -> bool:
        """判断是否为临时网络错误（可重试）"""
        text = f"{type(err).__name__}: {err}"
        keywords = (
            "ClientConnectorError",
            "Cannot connect to host",
            "TimeoutError",
            "ConnectionResetError",
            "Network is unreachable",
        )
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _collect_failed_urls(
        prepared_media: list[PreparedMedia],
    ) -> list[str]:
        """从 PreparedMedia 中收集下载失败的 URL"""
        return [item.original_url for item in prepared_media if item.download_failed]

    @locked("'global_web'")
    async def _send_chain(self, session_id: str, chain: list) -> SendResult:
        """发送消息链（使用全局网络锁）"""
        message_chain = MessageChain(chain=chain)

        try:
            sent = await StarTools.send_message(session_id, message_chain)
            if sent:
                logger.debug("Message send success: session=%s", session_id)
                return SendResult(ok=True)
            else:
                logger.warning("Message send returned False: session=%s", session_id)
                return SendResult(ok=False, needs_rebind=True, detail="platform_or_session")
        except Exception as ex:
            logger.error(
                "Message send raised exception: session=%s, error=%s",
                session_id,
                ex,
                exc_info=True,
            )
            return SendResult(ok=False, transient=True, detail=str(ex))

    async def send_to_user(
        self,
        request: SendRequest,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息给用户（默认实现）

        组件排序由 MessageFormatter 统一处理。
        """
        try:
            session_id = request.session_id
            timeout = context.timeout_seconds if context else self._get_timeout_seconds()
            proxy = context.proxy if context else self._get_proxy()
            platform = context.platform_name if context else ""

            effective_prepared = request.prepared_media
            if effective_prepared is None and request.media:
                effective_prepared = await self.prepare_media(
                    request.media, timeout=timeout, proxy=proxy
                )

            failed_urls: list[str] = []
            if effective_prepared:
                failed_urls = self._collect_failed_urls(effective_prepared)

            chain = self._formatter.build_chain(
                prepared_media=effective_prepared,
                text=request.message,
                failed_urls=failed_urls,
                platform=platform,
            )

            if not chain:
                return SendResult(ok=False, detail="empty_message")

            return await self._send_chain(session_id, chain)

        except Exception as err:
            logger.error("Send to user failed: session=%s, error=%s", request.session_id, err)
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=str(err),
            )

    async def send_to_group(
        self,
        platform: str,
        group_id: str,
        message: str = "",
        media: list[tuple[str, str]] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到群组"""
        request = SendRequest(
            session_id=f"{platform}:GroupMessage:{group_id}",
            message=message,
            media=media,
        )
        return await self.send_to_user(request, context=context)
