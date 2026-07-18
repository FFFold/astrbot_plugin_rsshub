from __future__ import annotations

from astrbot_plugin_rsshub.src.shared.constants import (
    MESSAGE_FORMAT_MERGED_FORWARD,
    MESSAGE_FORMAT_DIRECT,
    MESSAGE_FORMAT_IMAGE,
)
from astrbot_plugin_rsshub.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)


class FakeDefaults:
    message_format: str = "合并转发"


def test_resolve_message_format_default():
    dispatcher = NotificationDispatcher.__new__(NotificationDispatcher)
    dispatcher._default_message_format = MESSAGE_FORMAT_MERGED_FORWARD
    result = dispatcher._resolve_message_format(subscription=None, user=None)
    assert result == MESSAGE_FORMAT_MERGED_FORWARD


def test_resolve_message_format_from_subscription():
    dispatcher = NotificationDispatcher.__new__(NotificationDispatcher)
    dispatcher._default_message_format = MESSAGE_FORMAT_MERGED_FORWARD
    sub = type("Sub", (), {"message_format": 1})()
    result = dispatcher._resolve_message_format(subscription=sub)
    assert result == MESSAGE_FORMAT_DIRECT


def test_resolve_message_format_from_user():
    dispatcher = NotificationDispatcher.__new__(NotificationDispatcher)
    dispatcher._default_message_format = MESSAGE_FORMAT_MERGED_FORWARD
    user = type("User", (), {"message_format": 2})()
    result = dispatcher._resolve_message_format(subscription=None, user=user)
    assert result == MESSAGE_FORMAT_IMAGE


def test_resolve_message_format_subscription_overrides_user():
    dispatcher = NotificationDispatcher.__new__(NotificationDispatcher)
    dispatcher._default_message_format = MESSAGE_FORMAT_MERGED_FORWARD
    sub = type("Sub", (), {"message_format": 1})()
    user = type("User", (), {"message_format": 2})()
    result = dispatcher._resolve_message_format(subscription=sub, user=user)
    assert result == MESSAGE_FORMAT_DIRECT
