from __future__ import annotations

import pytest
from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender import (
    OneBotMessageSender,
)
from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.types import (
    MessageContext,
    SendRequest,
    SendResult,
)
from astrbot_plugin_rsshub.src.shared.constants import (
    MESSAGE_FORMAT_DIRECT,
    MESSAGE_FORMAT_IMAGE,
)


class _Plain:
    def __init__(self, text: str) -> None:
        self.text = text

    def __eq__(self, other):
        return isinstance(other, _Plain) and self.text == other.text


@pytest.mark.asyncio
async def test_onebot_direct_mode_sends_single_chain(monkeypatch):
    sender = OneBotMessageSender()
    sent_chain: list = []

    async def fake_send_chain(session_id, chain, **kwargs):
        sent_chain.append((session_id, chain))
        return SendResult(ok=True)

    monkeypatch.setattr(sender, "_send_chain", fake_send_chain)
    monkeypatch.setattr(
        sender, "_apply_generated_layout_local_paths", lambda r, pm, **kw: pm
    )
    monkeypatch.setattr(sender, "_apply_first_send_candidates", lambda c, pm, **kw: c)
    monkeypatch.setattr(sender, "_build_components", lambda r, pm, ctx, **kw: [])
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Plain",
        _Plain,
    )

    request = SendRequest(session_id="test", message="Hello")
    context = MessageContext(message_format=MESSAGE_FORMAT_DIRECT)

    result = await sender.send_to_user(request, context=context)
    assert result.ok
    assert len(sent_chain) == 1
    assert sent_chain[0][0] == "test"


@pytest.mark.asyncio
async def test_onebot_direct_mode_empty_message(monkeypatch):
    sender = OneBotMessageSender()
    sent_chain: list = []

    async def fake_send_chain(session_id, chain, **kwargs):
        sent_chain.append((session_id, chain))
        return SendResult(ok=True)

    monkeypatch.setattr(sender, "_send_chain", fake_send_chain)
    monkeypatch.setattr(
        sender, "_apply_generated_layout_local_paths", lambda r, pm, **kw: pm
    )
    monkeypatch.setattr(sender, "_apply_first_send_candidates", lambda c, pm, **kw: c)
    monkeypatch.setattr(sender, "_build_components", lambda r, pm, ctx, **kw: [])

    request = SendRequest(session_id="test", message="")
    context = MessageContext(message_format=MESSAGE_FORMAT_DIRECT)

    result = await sender.send_to_user(request, context=context)
    assert not result.ok
    assert result.detail == "empty_message"


@pytest.mark.asyncio
async def test_onebot_image_mode_calls_send_as_image(monkeypatch):
    sender = OneBotMessageSender()
    image_called = False

    async def fake_send_as_image(request, pm, ctx):
        nonlocal image_called
        image_called = True
        return SendResult(ok=True)

    monkeypatch.setattr(sender, "_send_as_image", fake_send_as_image)
    monkeypatch.setattr(
        sender, "_apply_generated_layout_local_paths", lambda r, pm, **kw: pm
    )

    request = SendRequest(session_id="test", message="Hello")
    context = MessageContext(message_format=MESSAGE_FORMAT_IMAGE)

    result = await sender.send_to_user(request, context=context)
    assert result.ok
    assert image_called
