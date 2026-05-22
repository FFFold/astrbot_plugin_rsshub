from __future__ import annotations

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
