"""QQ 官方 Bot 消息发送器

针对 QQ 官方 Bot 的特定优化。
组件排序由 MessageFormatter 统一处理，此处只负责发送。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base_sender import DefaultMessageSender
from .types import MessageContext, SendRequest, SendResult

if TYPE_CHECKING:
    pass


class QQOfficialMessageSender(DefaultMessageSender):
    """QQ 官方 Bot 消息发送器

    特性：
    - 支持 Markdown 消息
    - 组件排序由 MessageFormatter 统一
    - 多媒体消息按媒体优先、文本最后拆分发送
    """

    async def send_to_user(
        self,
        request: SendRequest,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到 QQ 官方 Bot"""
        try:
            if self._is_original_style(context) and request.layout:
                return await self._send_components_in_order(
                    request.session_id,
                    self._layout_to_components(request),
                    combine_image_text=True,
                    default_text=request.message,
                )

            prepared_media = await self._prepare_effective_media(request, context)
            components = self._build_components(
                request,
                prepared_media,
                context,
                platform="qq_official",
            )
            has_media = any(self._is_media_component(item) for item in components)
            if not has_media:
                return await super().send_to_user(request, context)
            if self._can_send_single_image_with_text(components):
                chain = self._chain_from_components(components)
                if not chain:
                    return SendResult(ok=False, detail="empty_message")
                return await self._send_chain(request.session_id, chain)
            return await self._send_components_media_first(
                request.session_id,
                components,
                default_text=request.message,
            )
        except Exception as err:
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=self._normalize_error_detail(str(err)),
            )

    @staticmethod
    def _can_send_single_image_with_text(components) -> bool:
        media = [item for item in components if item.kind == "media"]
        tails = [item for item in components if item.kind == "tail"]
        texts = [item for item in components if item.kind == "text" and item.text]
        return (
            len(media) == 1
            and media[0].media_type == "image"
            and not tails
            and len(texts) == 1
        )
