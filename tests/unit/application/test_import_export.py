"""Subscription TOML import/export behavior tests."""

from __future__ import annotations

import pytest
from astrbot_plugin_rsshub.src.application.commands.export_subscriptions_cmd import (
    ExportSubscriptionsCommand,
)
from astrbot_plugin_rsshub.src.application.services.subscription_serializer import (
    parse_subscriptions_toml,
    serialize_subscriptions_to_toml,
)
from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription


def make_subscription(
    *,
    feed_id: int = 1,
    link: str = "https://example.com/feed.xml",
    feed_title: str = "Example Feed",
    **fields: object,
) -> Subscription:
    """Create a Subscription with its runtime Feed relation attached."""
    data = {
        "user_id": "user-001",
        "feed_id": feed_id,
        **fields,
    }
    subscription = Subscription(**data)
    subscription.feed = Feed(id=feed_id, link=link, title=feed_title)
    return subscription


class TestTOMLRoundtrip:
    """Verify export and parse are stable for subscription settings."""

    def test_roundtrip_single_subscription(self) -> None:
        subscription = make_subscription(
            title="Timeline",
            tags="twitter,art",
            notify=1,
            send_mode=2,
        )

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            subscriptions=[subscription],
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert len(payload.records) == 1
        record = payload.records[0]
        assert record.link == "https://example.com/feed.xml"
        assert record.feed_title == "Example Feed"
        assert record.options["title"] == "Timeline"
        assert record.options["tags"] == "twitter,art"
        assert record.options["notify"] == 1
        assert record.options["send_mode"] == 2

    def test_roundtrip_multiple_subscriptions(self) -> None:
        subscriptions = [
            make_subscription(
                feed_id=1,
                link="https://example.com/feed-1.xml",
                feed_title="Feed 1",
            ),
            make_subscription(
                feed_id=2,
                link="https://example.com/feed-2.xml",
                feed_title="Feed 2",
                title="Second",
            ),
            make_subscription(
                feed_id=3,
                link="https://example.com/feed-3.xml",
                feed_title="Feed 3",
                tags="third",
            ),
        ]

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            subscriptions=subscriptions,
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert [record.link for record in payload.records] == [
            "https://example.com/feed-1.xml",
            "https://example.com/feed-2.xml",
            "https://example.com/feed-3.xml",
        ]
        assert [record.feed_title for record in payload.records] == [
            "Feed 1",
            "Feed 2",
            "Feed 3",
        ]

    def test_roundtrip_preserves_options(self) -> None:
        subscription = make_subscription(
            title="Configured",
            tags="alerts,news",
            platform_name="telegram",
            interval=15,
            notify=1,
            send_mode=2,
            length_limit=500,
            link_preview=1,
            display_author=1,
            display_via=0,
            display_title=1,
            display_entry_tags=1,
            style=3,
            display_media=-1,
            translate=1,
            translate_target_lang="ja",
        )

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            subscriptions=[subscription],
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        options = payload.records[0].options
        assert options == {
            "display_author": 1,
            "display_entry_tags": 1,
            "display_media": -1,
            "display_title": 1,
            "display_via": 0,
            "interval": 15,
            "length_limit": 500,
            "link_preview": 1,
            "notify": 1,
            "platform_name": "telegram",
            "send_mode": 2,
            "style": 3,
            "tags": "alerts,news",
            "title": "Configured",
            "translate": 1,
            "translate_target_lang": "ja",
        }


class TestTOMLParsing:
    """Verify parser validation and best-effort import behavior."""

    def test_parse_empty_string(self) -> None:
        payload = parse_subscriptions_toml("")

        assert payload.records == []
        assert payload.errors

    def test_parse_invalid_toml(self) -> None:
        payload = parse_subscriptions_toml("[[subscriptions]")

        assert payload.records == []
        assert payload.errors

    def test_parse_missing_link(self) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            title = "No link"
            """
        )

        assert payload.records == []
        assert payload.errors

    def test_parse_minimal_valid(self) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            link = "https://example.com/feed.xml"
            """
        )

        assert payload.errors == []
        assert len(payload.records) == 1
        assert payload.records[0].link == "https://example.com/feed.xml"
        assert payload.records[0].feed_title is None
        assert payload.records[0].options == {}

    def test_parse_warns_on_version_mismatch(self) -> None:
        payload = parse_subscriptions_toml(
            """
            format = "another-format"
            version = 999

            [[subscriptions]]
            link = "https://example.com/feed.xml"
            """
        )

        assert payload.errors == []
        assert len(payload.records) == 1
        assert len(payload.warnings) == 2


class TestExportCommand:
    """Verify the export command hydrates Feed data before serializing."""

    @pytest.mark.asyncio
    async def test_export_hydrates_feed_for_subscription(self) -> None:
        subscription = Subscription(user_id="user-001", feed_id=1, title="Hydrated")
        feed = Feed(id=1, link="https://example.com/feed.xml", title="Hydrated Feed")

        class SubscriptionRepo:
            async def get_by_user(self, user_id: str) -> list[Subscription]:
                assert user_id == "user-001"
                return [subscription]

        class FeedRepo:
            async def get_by_id(self, feed_id: int) -> Feed | None:
                assert feed_id == 1
                return feed

        command = ExportSubscriptionsCommand(
            subscription_repo=SubscriptionRepo(),
            feed_repo=FeedRepo(),
        )

        result = await command.execute("user-001")
        payload = parse_subscriptions_toml(result.data.content)

        assert result.success is True
        assert payload.errors == []
        assert len(payload.records) == 1
        assert payload.records[0].link == "https://example.com/feed.xml"
        assert payload.records[0].feed_title == "Hydrated Feed"
        assert payload.records[0].options["title"] == "Hydrated"
