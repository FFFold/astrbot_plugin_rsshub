"""QQ OneBot 消息发送器

针对 QQ OneBot 协议的特定优化。
支持合并转发节点（Nodes）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astrbot.api.message_components import Node, Nodes, Plain

from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .types import MessageContext, SendRequest, SendResult

if TYPE_CHECKING:
    pass

logger = get_logger()


class OneBotMessageSender(DefaultMessageSender):
    """QQ OneBot 平台消息发送器

    特性：
    - 合并转发节点（Nodes）：文字 + 图片/视频/音频/文件各自一个节点
    - 失败时回退为文字合并转发节点
    """

    async def send_to_user(
        self,
        request: SendRequest,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送合并转发消息到 QQ OneBot 用户

        每条消息/媒体各自一个 Node，失败时回退为纯文字节点。
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

            nickname = (
                context.channel.title if context and context.channel.title else "RSSHub"
            )

            nodes: list[Node] = []

            # 从 Formatter 获取分类组件（images / Plain / tails）
            from astrbot.api.message_components import File, Image, Record, Video

            image_components: list = []
            tail_components: list = []
            failed_media_urls: list[str] = []

            if effective_prepared:
                for item in effective_prepared:
                    path = (
                        str(item.local_path) if item.local_path else item.original_url
                    )
                    if item.download_failed:
                        failed_media_urls.append(item.original_url)
                    match item.media_type:
                        case "image":
                            image_components.append(Image(file=path))
                        case "video":
                            image_components.append(Video(file=path))
                        case "audio":
                            tail_components.append(Record(file=path, text="audio"))
                        case "file":
                            from urllib.parse import unquote, urlparse

                            filename = (
                                unquote(
                                    urlparse(item.original_url).path.rsplit("/", 1)[-1]
                                )
                                or "attachment"
                            )
                            tail_components.append(
                                File(
                                    name=filename,
                                    file=path,
                                    url=item.original_url,
                                )
                            )

            # 将失败链接追加到文本
            final_text = self._formatter._append_failed_links(
                request.message, failed_media_urls
            )

            # 节点1：文字（header）
            header_text = final_text if final_text else "RSS update"
            nodes.append(Node(content=[Plain(header_text)], name=nickname))

            # 图片/视频各自一个节点
            for comp in image_components:
                nodes.append(Node(content=[comp], name=nickname))

            # 音频/文件各自一个节点
            for comp in tail_components:
                nodes.append(Node(content=[comp], name=nickname))

            if not nodes:
                return SendResult(ok=False, detail="empty_message")

            result = await self._send_chain(session_id, [Nodes(nodes)])
            if result.ok:
                return result

            # 失败回退：纯文字合并转发节点
            logger.warning(
                "OneBot merged-forward send failed, fallback to text-only: "
                "session=%s, detail=%s",
                session_id,
                result.detail,
            )
            fallback_text = final_text if final_text else "RSS update"
            fallback_nodes = [Node(content=[Plain(fallback_text)], name=nickname)]
            return await self._send_chain(session_id, [Nodes(fallback_nodes)])

        except Exception as err:
            logger.error(
                "OneBot merged-forward send exception: session=%s, err=%s",
                request.session_id,
                err,
                exc_info=True,
            )
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=str(err),
            )
