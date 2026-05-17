"""Subscription export read-model query."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..dto.subscription_export_record import (
    SubscriptionExportRecord,
    build_subscription_export_record,
)

if TYPE_CHECKING:
    from ...domain.repositories.feed_repository import FeedRepository
    from ...domain.repositories.subscription_repository import SubscriptionRepository


class GetSubscriptionExportsQuery:
    """Build export read models for a user's subscriptions."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo

    async def execute(self, user_id: str) -> list[SubscriptionExportRecord]:
        """Load subscriptions and hydrate export-ready records."""
        subscriptions = await self._subscription_repo.get_by_user(user_id)
        if not subscriptions or self._feed_repo is None:
            return []

        records: list[SubscriptionExportRecord] = []
        for subscription in subscriptions:
            feed = await self._feed_repo.get_by_id(subscription.feed_id)
            if feed is None:
                continue
            records.append(
                build_subscription_export_record(
                    subscription,
                    link=feed.link,
                    feed_title=feed.title or None,
                )
            )
        return records
