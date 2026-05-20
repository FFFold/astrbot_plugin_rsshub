from __future__ import annotations

from datetime import datetime, timezone

from astrbot_plugin_rsshub.src.domain.entities.push_history import (
    MAX_FAIL_REASON_LENGTH,
)
from astrbot_plugin_rsshub.src.infrastructure.persistence.models import PushHistoryORM
from astrbot_plugin_rsshub.src.infrastructure.persistence.push_history_repository_impl import (
    PushHistoryRepositoryImpl,
)


def test_to_entity_truncates_overlong_legacy_fail_reason_without_crashing():
    now = datetime.now(timezone.utc)
    orm = PushHistoryORM(
        id=1,
        sub_id=1,
        user_id="user-1",
        feed_id=10,
        content="content",
        entry_title="entry title",
        entry_link="https://example.com/entry",
        feed_title="feed title",
        feed_link="https://example.com/feed",
        status="failed",
        retry_count=0,
        max_retries=3,
        fail_reason="seed",
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    dirty_reason = "x" * (MAX_FAIL_REASON_LENGTH + 128)
    orm.fail_reason = dirty_reason

    entity = PushHistoryRepositoryImpl._to_entity(orm)

    assert entity.fail_reason is not None
    assert entity.fail_reason != dirty_reason
    assert len(entity.fail_reason) <= MAX_FAIL_REASON_LENGTH
    assert entity.status == "failed"


def test_to_entity_normalizes_empty_fail_reason_for_failed_status():
    orm = PushHistoryORM(
        id=2,
        sub_id=1,
        user_id="u1",
        feed_id=1,
        content="seed",
        entry_title="title",
        entry_link="https://example.com/post",
        feed_title="feed",
        feed_link="https://example.com/feed",
        status="failed",
        retry_count=0,
        max_retries=3,
        fail_reason="   ",
    )

    entity = PushHistoryRepositoryImpl._to_entity(orm)

    assert entity.fail_reason is None


def test_to_entity_keeps_empty_fail_reason_empty_for_success_status():
    orm = PushHistoryORM(
        id=3,
        sub_id=1,
        user_id="u1",
        feed_id=1,
        content="seed",
        entry_title="title",
        entry_link="https://example.com/post",
        feed_title="feed",
        feed_link="https://example.com/feed",
        status="success",
        retry_count=0,
        max_retries=3,
        fail_reason="   ",
    )

    entity = PushHistoryRepositoryImpl._to_entity(orm)

    assert entity.fail_reason is None


def test_to_entity_hides_legacy_fail_reason_for_success_status():
    orm = PushHistoryORM(
        id=4,
        sub_id=1,
        user_id="u1",
        feed_id=1,
        content="seed",
        entry_title="title",
        entry_link="https://example.com/post",
        feed_title="feed",
        feed_link="https://example.com/feed",
        status="success",
        retry_count=0,
        max_retries=3,
        fail_reason="",
    )

    entity = PushHistoryRepositoryImpl._to_entity(orm)

    assert entity.fail_reason is None


def test_to_entity_preserves_agent_source_fields():
    now = datetime.now(timezone.utc)
    orm = PushHistoryORM(
        id=2,
        sub_id=None,
        user_id="user-2",
        feed_id=None,
        source_type="agent",
        source_key="daily:ai-news",
        content="content",
        raw_xml="<entry><p>Hello</p></entry>",
        entry_title="entry title",
        entry_link="https://example.com/entry",
        feed_title="feed title",
        feed_link="https://example.com/feed",
        status="success",
        retry_count=0,
        max_retries=3,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )

    entity = PushHistoryRepositoryImpl._to_entity(orm)

    assert entity.source_type == "agent"
    assert entity.source_key == "daily:ai-news"
    assert entity.sub_id is None
    assert entity.feed_id is None
    assert entity.raw_xml == "<entry><p>Hello</p></entry>"
