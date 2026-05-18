from __future__ import annotations

from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.types import (
    PreparedMedia,
)
from astrbot_plugin_rsshub.src.infrastructure.pipeline.formatter import MessageFormatter


def test_default_chain_keeps_failed_media_as_url_component():
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
    assert len(chain) >= 2


def test_telegram_chain_keeps_failed_media_as_url_component():
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
    assert len(chain) >= 2
