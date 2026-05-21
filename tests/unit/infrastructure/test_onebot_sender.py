from __future__ import annotations

import sys
from pathlib import Path

import pytest
from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender import (
    OneBotMessageSender,
)
from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.types import (
    ChannelInfo,
    MessageContext,
    PreparedMedia,
    SendRequest,
    SendResult,
)


class _Plain:
    def __init__(self, text: str) -> None:
        self.text = text


class _Node:
    def __init__(self, content: list, name: str) -> None:
        self.content = content
        self.name = name


class _Nodes:
    def __init__(self, nodes: list) -> None:
        self.nodes = nodes


class _Image:
    def __init__(self, file: str) -> None:
        self.file = file


class _Video:
    def __init__(self, file: str) -> None:
        self.file = file


@pytest.mark.asyncio
async def test_onebot_sender_fallback_text_includes_all_original_media_urls(monkeypatch):
    sender = OneBotMessageSender()
    calls: list[tuple[str, list]] = []

    async def fake_send_chain(session_id: str, chain: list):
        calls.append((session_id, chain))
        if len(calls) == 1:
            return SendResult(ok=False, detail="forward failed")
        return SendResult(ok=True)

    monkeypatch.setattr(sender, "_send_chain", fake_send_chain)
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Node",
        _Node,
    )
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Nodes",
        _Nodes,
    )
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Plain",
        _Plain,
    )
    monkeypatch.setattr(
        sys.modules["astrbot.api.message_components"], "Image", _Image, raising=False
    )
    monkeypatch.setattr(
        sys.modules["astrbot.api.message_components"], "Video", _Video, raising=False
    )

    request = SendRequest(
        session_id="default:GroupMessage:1",
        message="entry content",
        prepared_media=[
            PreparedMedia(
                media_type="video",
                original_url="https://example.com/video.mp4",
                local_path=Path("/tmp/video.mp4"),
            ),
            PreparedMedia(
                media_type="image",
                original_url="https://example.com/image.jpg",
                local_path=Path("/tmp/image.jpg"),
            ),
        ],
    )

    result = await sender.send_to_user(
        request,
        context=MessageContext(
            channel=ChannelInfo(title="Feed Title"),
            platform_name="aiocqhttp",
        ),
    )

    assert result.ok is True
    assert len(calls) == 2

    fallback_chain = calls[1][1]
    fallback_text = fallback_chain[0].nodes[0].content[0].text

    assert "媒体原始链接:" in fallback_text
    assert "https://example.com/video.mp4" in fallback_text
    assert "https://example.com/image.jpg" in fallback_text


@pytest.mark.asyncio
async def test_onebot_sender_prefers_remote_video_url_by_default(monkeypatch):
    sender = OneBotMessageSender()
    calls: list[tuple[str, list]] = []

    async def fake_send_chain(session_id: str, chain: list):
        calls.append((session_id, chain))
        return SendResult(ok=True)

    monkeypatch.setattr(sender, "_send_chain", fake_send_chain)
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Node",
        _Node,
    )
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Nodes",
        _Nodes,
    )
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.messaging.senders.onebot_sender.Plain",
        _Plain,
    )
    monkeypatch.setattr(
        sys.modules["astrbot.api.message_components"], "Image", _Image, raising=False
    )
    monkeypatch.setattr(
        sys.modules["astrbot.api.message_components"], "Video", _Video, raising=False
    )

    request = SendRequest(
        session_id="default:GroupMessage:1",
        message="entry content",
        prepared_media=[
            PreparedMedia(
                media_type="video",
                original_url="https://example.com/video.mp4",
                local_path=Path("/tmp/video.mp4"),
            ),
        ],
    )

    result = await sender.send_to_user(
        request,
        context=MessageContext(
            channel=ChannelInfo(title="Feed Title"),
            platform_name="aiocqhttp",
        ),
    )

    assert result.ok is True
    assert len(calls) == 1
    media_node = calls[0][1][0].nodes[1]
    assert media_node.content[0].file == "https://example.com/video.mp4"
