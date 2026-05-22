from __future__ import annotations

import time
from pathlib import Path

import pytest
from astrbot_plugin_rsshub.src.infrastructure.media.media_downloader import (
    MediaDownloader,
)


@pytest.mark.asyncio
async def test_media_downloader_caches_recent_download_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    MediaDownloader._failure_cache.clear()
    calls = 0

    async def fail_download(self, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("origin status=523")

    monkeypatch.setattr(MediaDownloader, "download_to_temp", fail_download)

    first = MediaDownloader(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="origin status=523"):
        await first.get_or_download(url="https://example.com/a.png")

    second = MediaDownloader(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="recent media download failure cached"):
        await second.get_or_download(url="https://example.com/a.png")

    assert calls == 1
    MediaDownloader._failure_cache.clear()


def test_media_downloader_failure_cache_prunes_expired_and_oldest_entries():
    MediaDownloader._failure_cache.clear()
    original_max_entries = MediaDownloader._FAILURE_CACHE_MAX_ENTRIES
    MediaDownloader._FAILURE_CACHE_MAX_ENTRIES = 2
    now = time.time()

    try:
        MediaDownloader._failure_cache.update(
            {
                "expired": (now - 1, "expired"),
                "oldest": (now + 10, "oldest"),
                "middle": (now + 20, "middle"),
                "newest": (now + 30, "newest"),
            }
        )

        MediaDownloader._prune_failure_cache()

        assert MediaDownloader._failure_cache == {
            "middle": (now + 20, "middle"),
            "newest": (now + 30, "newest"),
        }
    finally:
        MediaDownloader._FAILURE_CACHE_MAX_ENTRIES = original_max_entries
        MediaDownloader._failure_cache.clear()
