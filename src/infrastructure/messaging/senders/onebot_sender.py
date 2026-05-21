"""QQ OneBot 消息发送器

针对 QQ OneBot 协议的特定优化。
支持合并转发节点（Nodes）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astrbot.api.message_components import Node, Nodes, Plain

from ...config import get_config_manager
from ...pipeline import MessageFormatter
from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .telegraph_client import TelegraphClient
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

    @staticmethod
    def _strategy_value(strategy, key: str, default=None):
        if strategy is None:
            return default
        if isinstance(strategy, dict):
            return strategy.get(key, default)
        return getattr(strategy, key, default)

    @staticmethod
    def _strategy_from_templates(sender_strategies, template_key: str):
        templates = (
            sender_strategies.get("platform_strategies")
            if isinstance(sender_strategies, dict)
            else getattr(sender_strategies, "platform_strategies", None)
        )
        if not isinstance(templates, list):
            return None
        return next(
            (
                item
                for item in templates
                if isinstance(item, dict) and item.get("__template_key") == template_key
            ),
            None,
        )

    @classmethod
    def _resolve_video_path(cls, item, context: MessageContext | None) -> str:
        strategy = getattr(context, "sender_strategy", None) if context else None
        prefer_local = bool(cls._strategy_value(strategy, "prefer_local_video", False))
        if prefer_local and item.local_path:
            return str(item.local_path)
        return item.original_url

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
                strategy = cls._strategy_from_templates(
                    sender_strategies, "onebot_strategy"
                )
                if strategy is None:
                    strategy = (
                        sender_strategies.get("aiocqhttp")
                        if isinstance(sender_strategies, dict)
                        else getattr(
                            sender_strategies,
                            "aiocqhttp_settings",
                            getattr(sender_strategies, "aiocqhttp", None),
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
        nickname: str,
        token: str,
    ) -> SendResult:
        media_urls = MessageFormatter.collect_original_urls(prepared_media)
        client = TelegraphClient(
            access_token=token,
            timeout_seconds=context.timeout_seconds
            if context
            else self._get_timeout_seconds(),
        )
        page_url = await client.create_media_page(
            title=context.channel.title
            if context and context.channel.title
            else nickname,
            content=request.message,
            media_urls=media_urls,
            channel=context.channel if context else None,
        )
        node_text = request.message or "RSS update"
        node_text = f"{node_text}\n\nTelegraph: {page_url}" if node_text else page_url
        return await self._send_chain(
            session_id,
            [Nodes([Node(content=[Plain(node_text)], name=nickname)])],
        )

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
                        nickname=nickname,
                        token=telegraph_token,
                    )
                except Exception as err:
                    logger.warning(
                        "OneBot Telegraph fallback to native send: session=%s, error=%s",
                        session_id,
                        err,
                    )

            nodes: list[Node] = []

            # 从 Formatter 获取分类组件（images / Plain / tails）
            from astrbot.api.message_components import File, Image, Record, Video

            image_components: list = []
            tail_components: list = []
            failed_media_urls: list[str] = []
            original_media_urls = MessageFormatter.collect_original_urls(
                effective_prepared
            )

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
                            image_components.append(
                                Video(file=self._resolve_video_path(item, context))
                            )
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
                request.message,
                failed_media_urls,
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
            fallback_text = self._formatter._append_failed_links(
                request.message or "RSS update",
                original_media_urls or failed_media_urls,
            )
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
                detail=self._normalize_error_detail(str(err)),
            )
