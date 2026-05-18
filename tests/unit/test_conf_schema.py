"""Schema regression tests."""

from __future__ import annotations

import json
from pathlib import Path


def test_conf_schema_is_scoped_to_startup_credentials_and_sender_strategies():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))

    assert set(schema) == {
        "basic_config",
        "ffmpeg",
        "sender_strategies",
    }
    assert "global_config" not in schema
    assert "pipeline" not in schema
    assert "translation" not in schema
