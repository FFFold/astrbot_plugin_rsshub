from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_rsshub import bootstrap


class _FakeDB:
    def __init__(self):
        self.is_initialized = True
        self.close = AsyncMock()


class _FakeScheduler:
    def __init__(self):
        self.stop = AsyncMock()


class _FakeQueue:
    def __init__(self):
        self.stop_all = AsyncMock()


@pytest.mark.asyncio
async def test_create_runtime_does_not_start_scheduler_when_register_web_api_fails(
    monkeypatch,
):
    fake_db = _FakeDB()
    fake_queue = _FakeQueue()
    start_scheduler = AsyncMock(return_value=_FakeScheduler())

    monkeypatch.setattr(
        bootstrap,
        "_init_config",
        lambda _cfg: (
            MagicMock(),
            MagicMock(
                scheduler=MagicMock(default_interval=10, history_retention_days=30),
                sender_strategies=MagicMock(),
            ),
        ),
    )
    monkeypatch.setattr(bootstrap, "_init_database", AsyncMock())
    monkeypatch.setattr(
        bootstrap,
        "_build_dependencies",
        lambda **_kwargs: ({}, MagicMock()),
    )
    monkeypatch.setattr(
        bootstrap,
        "_start_scheduler",
        start_scheduler,
    )
    monkeypatch.setattr(
        bootstrap,
        "_register_web_api",
        MagicMock(side_effect=RuntimeError("register failed")),
    )
    monkeypatch.setattr(bootstrap, "get_database", lambda: fake_db)

    with pytest.raises(RuntimeError, match="register failed"):
        await bootstrap.create_plugin_runtime(
            context=MagicMock(),
            config={},
            push_job_queue=fake_queue,
        )

    start_scheduler.assert_not_awaited()
    fake_queue.stop_all.assert_awaited_once()
    fake_db.close.assert_awaited_once()
