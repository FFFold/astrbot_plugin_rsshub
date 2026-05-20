from __future__ import annotations

from astrbot.api.message_components import Plain

from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.types import (
    PreparedMedia,
)
from astrbot_plugin_rsshub.src.infrastructure.pipeline.formatter import MessageFormatter


def test_default_chain_keeps_failed_media_as_url_component():
    Plain.reset_mock()
    formatter = MessageFormatter()
    chain = formatter.build_chain(
        prepared_media=[
            PreparedMedia(
                media_type="image",
                original_url="https://example.com/a.jpg",
                local_path=None,
                download_failed=True,
            )
        ],
        text="hello",
        failed_urls=[],
        platform="",
    )
    assert len(chain) == 2
    assert Plain.call_args.args[0] == "hello\n媒体原始链接:\nhttps://example.com/a.jpg"


def test_telegram_chain_keeps_failed_media_as_url_component():
    Plain.reset_mock()
    formatter = MessageFormatter()
    chain = formatter.build_chain(
        prepared_media=[
            PreparedMedia(
                media_type="image",
                original_url="https://example.com/a.jpg",
                local_path=None,
                download_failed=True,
            )
        ],
        text="hello",
        failed_urls=[],
        platform="telegram",
    )
    assert len(chain) == 2
    assert Plain.call_args.args[0] == "hello\n媒体原始链接:\nhttps://example.com/a.jpg"
