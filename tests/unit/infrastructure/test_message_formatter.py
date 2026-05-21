from __future__ import annotations

import pytest

from astrbot_plugin_rsshub.src.infrastructure.messaging.senders.types import (
    PreparedMedia,
)
from astrbot_plugin_rsshub.src.infrastructure.pipeline import (
    EffectivePushOptions,
    EntryFormatInput,
    EntryTextFormatter,
    MessageChainFormatter,
    MessageFormatter,
)

from astrbot.api.message_components import Plain


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


def test_telegram_chain_does_not_truncate_caption_text():
    Plain.reset_mock()
    formatter = MessageFormatter()
    text = "x" * 1100

    chain = formatter.build_chain(
        prepared_media=[
            PreparedMedia(
                media_type="image",
                original_url="https://example.com/a.jpg",
                local_path="/tmp/a.jpg",
                download_failed=False,
            )
        ],
        text=text,
        failed_urls=[],
        platform="telegram",
    )

    assert len(chain) == 2
    assert Plain.call_args.args[0] == text


def test_message_formatter_alias_keeps_message_chain_formatter_compatibility():
    assert MessageFormatter is MessageChainFormatter


@pytest.mark.asyncio
async def test_entry_text_formatter_decodes_entity_escaped_html():
    formatter = EntryTextFormatter()

    text = await formatter.format_entry(
        EntryFormatInput(
            title="Title",
            content=(
                "Title&lt;br&gt;Body&lt;br&gt;"
                '&lt;img src="https://example.com/image.jpg"&gt;'
            ),
            link="https://example.com/post",
            author="Author",
            feed_title="Feed",
        ),
        EffectivePushOptions(),
    )

    assert "&lt;br" not in text
    assert "&lt;img" not in text
    assert "<img" not in text
    assert "Body" in text
    assert "via https://example.com/post | Feed (author: Author)" in text
