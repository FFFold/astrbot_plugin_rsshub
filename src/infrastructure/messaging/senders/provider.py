"""Infrastructure adapter for the application message sender port."""

from __future__ import annotations

from ....application.ports import (
    MessageContext,
    MessageSender,
    SendRequest,
    SendResult,
)
from ....application.settings import SenderStrategySettings
from ...utils import get_logger
from .factory import get_sender_for_platform
from .types import MessageContext as InfraMessageContext
from .types import SendRequest as InfraSendRequest
from .types import ChannelInfo

logger = get_logger()


class InfrastructureMessageSenderAdapter:
    """Adapter from application send requests to concrete infrastructure senders."""

    def __init__(self, sender) -> None:
        self._sender = sender

    async def send_to_user(
        self,
        request: SendRequest,
        context: MessageContext | None = None,
    ) -> SendResult:
        infra_context = InfraMessageContext(
            channel=ChannelInfo(
                title=context.channel_title if context else "",
                link=context.channel_link if context else "",
            ),
            platform_name=context.platform_name if context else "",
            timeout_seconds=context.timeout_seconds if context else 30,
            proxy=context.proxy if context else "",
        )
        result = await self._sender.send_to_user(
            InfraSendRequest(
                session_id=request.session_id,
                message=request.message,
                media=request.media,
            ),
            context=infra_context,
        )
        return SendResult(
            ok=result.ok,
            needs_rebind=result.needs_rebind,
            transient=result.transient,
            detail=result.detail,
            http_status=result.http_status,
        )


class InfrastructureMessageSenderProvider:
    """Resolve message senders using infrastructure sender implementations."""

    def __init__(
        self,
        sender_strategies: SenderStrategySettings | None = None,
    ) -> None:
        self._sender_strategies = sender_strategies

    def get(self, platform_name: str | None) -> MessageSender:
        sender_class = get_sender_for_platform(
            platform_name,
            sender_strategies=self._sender_strategies,
        )
        logger.debug(
            "Resolved sender for platform '%s': %s",
            platform_name,
            sender_class.__name__,
        )
        return InfrastructureMessageSenderAdapter(sender_class())
