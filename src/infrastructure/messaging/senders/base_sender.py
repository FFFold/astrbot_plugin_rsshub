"""基础消息发送器

提供跨平台消息发送的默认实现。
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import TYPE_CHECKING

from astrbot.api.message_components import File, Image, Plain, Record, Video
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.star_tools import StarTools

from ...utils import get_logger
from .types import MessageContext, PreparedMedia, SendResult

if TYPE_CHECKING:
    pass

logger = get_logger()


class DefaultMessageSender:
    """默认跨平台发送器策略

    提供基础的消息发送和媒体处理功能。
    各平台发送器可以继承此类并覆盖特定方法。
    """

    _timeout_seconds: int = 30
    _proxy: str = ""
    _download_media_before_send: bool = True

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

    async def prepare_media(
        self,
        media: list[tuple[str, str]] | None,
        timeout: int = 30,
        proxy: str = "",
    ) -> list[PreparedMedia]:
        """预处理媒体文件

        Args:
            media: 媒体列表 [(type, url), ...]
            timeout: 下载超时
            proxy: 代理地址

        Returns:
            预处理后的媒体列表
        """
        if not media:
            return []

        prepared: list[PreparedMedia] = []
        seen_urls: set[str] = set()

        from ...utils import MediaDownloader

        downloader = MediaDownloader(timeout=timeout, proxy=proxy)

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
                local_path = await downloader.download(media_url)
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

    async def _build_media_components(
        self,
        prepared_media: list[PreparedMedia],
    ) -> tuple[list, list, list[str]]:
        """构建媒体组件

        Returns:
            (image_components, tail_components, failed_urls)
        """
        image_components = []
        tail_components = []
        failed_media_urls: list[str] = []

        for item in prepared_media:
            media_type = item.media_type
            media_url = item.original_url
            local_path = item.local_path

            if item.download_failed:
                failed_media_urls.append(media_url)
                continue

            media_file_value = str(local_path) if local_path else media_url

            if media_type == "image":
                image_components.append(Image(file=media_file_value))
            elif media_type == "video":
                image_components.append(Video(file=media_file_value))
            elif media_type == "audio":
                tail_components.append(Record(file=media_file_value, text="audio"))
            elif media_type == "file":
                parsed = urlparse(media_url)
                filename = unquote(parsed.path.rsplit("/", 1)[-1]) or "attachment"
                tail_components.append(
                    File(name=filename, file=media_file_value, url=media_url)
                )

        return image_components, tail_components, failed_media_urls

    @staticmethod
    def _append_failed_media_links(message: str, failed_media_urls: list[str]) -> str:
        """在消息末尾添加失败的媒体链接"""
        if not failed_media_urls:
            return message

        unique_urls: list[str] = []
        seen: set[str] = set()
        for url in failed_media_urls:
            if url and url not in seen:
                unique_urls.append(url)
                seen.add(url)

        if not unique_urls:
            return message

        lines = [message] if message else []
        lines.append("媒体原始链接:")
        lines.extend(unique_urls)
        return "\n".join(lines)

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

    async def _send_chain(self, session_id: str, chain: list) -> SendResult:
        """发送消息链"""
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
        session_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        prepared_media: list[PreparedMedia] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息给用户（默认实现）"""
        try:
            timeout = context.timeout_seconds if context else self._get_timeout_seconds()
            proxy = context.proxy if context else self._get_proxy()

            image_components = []
            tail_components = []
            failed_media_urls: list[str] = []

            effective_prepared = prepared_media
            if effective_prepared is None and media:
                effective_prepared = await self.prepare_media(
                    media, timeout=timeout, proxy=proxy
                )

            if effective_prepared:
                (
                    image_components,
                    tail_components,
                    failed_media_urls,
                ) = await self._build_media_components(effective_prepared)
                message = self._append_failed_media_links(message, failed_media_urls)

            # 构建消息链
            chain = []
            if image_components:
                chain.extend(image_components)
            if message:
                chain.append(Plain(message))
            if tail_components:
                chain.extend(tail_components)

            if not chain:
                return SendResult(ok=False, detail="empty_message")

            return await self._send_chain(session_id, chain)

        except Exception as err:
            logger.error("Send to user failed: session=%s, error=%s", session_id, err)
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=str(err),
            )

    async def send_to_group(
        self,
        platform: str,
        group_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到群组"""
        session_id = f"{platform}:GroupMessage:{group_id}"
        return await self.send_to_user(session_id, message, media, context=context)
