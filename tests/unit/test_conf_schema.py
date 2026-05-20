"""Schema regression tests."""

from __future__ import annotations

import json
from pathlib import Path


def test_conf_schema_is_scoped_to_startup_credentials_and_sender_strategies():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))

    assert set(schema) == {
        "basic_config",
        "ffmpeg",
        "route_knowledge",
        "sender_strategies",
    }
    route_knowledge_items = schema["route_knowledge"]["items"]
    assert route_knowledge_items["kb_name"]["default"] == "RSSHub Routes"
    assert route_knowledge_items["embedding_provider_id"]["default"] == ""
    assert route_knowledge_items["embedding_provider_id"]["_special"] == "select_provider"
    assert route_knowledge_items["rerank_provider_id"]["default"] == ""
    assert route_knowledge_items["rerank_provider_id"]["_special"] == "select_provider"
    assert route_knowledge_items["source_mode"]["default"] == "mirror"
    assert route_knowledge_items["source_mode"]["options"] == [
        "mirror",
        "auto",
        "github",
        "local",
    ]
    source_options = [
        "https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/rsshub-routes-knowledgebase",
        "https://ghfast.top/https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/rsshub-routes-knowledgebase",
    ]
    assert (
        route_knowledge_items["source_base_url"]["default"]
        == source_options[0]
    )
    assert route_knowledge_items["source_base_url"]["options"] == source_options
    assert route_knowledge_items["fallback_base_url"]["options"] == source_options
    assert route_knowledge_items["timeout"]["slider"] == {
        "min": 1,
        "max": 300,
        "step": 1,
    }
    assert route_knowledge_items["batch_size"]["slider"] == {
        "min": 1,
        "max": 256,
        "step": 1,
    }
    assert route_knowledge_items["tasks_limit"]["slider"] == {
        "min": 1,
        "max": 32,
        "step": 1,
    }
    assert route_knowledge_items["max_retries"]["slider"] == {
        "min": 0,
        "max": 10,
        "step": 1,
    }
    assert "global_config" not in schema
    assert "pipeline" not in schema
    assert "translation" not in schema

    basic_config_items = schema["basic_config"]["items"]
    assert basic_config_items["timeout"]["slider"] == {
        "min": 1,
        "max": 300,
        "step": 1,
    }
    assert basic_config_items["minimal_interval"]["slider"] == {
        "min": 1,
        "max": 1440,
        "step": 1,
    }
    assert basic_config_items["hash_history_min"]["slider"] == {
        "min": 1,
        "max": 20000,
        "step": 50,
    }
    assert basic_config_items["failed_queue_capacity"]["slider"] == {
        "min": 0,
        "max": 1000,
        "step": 10,
    }
    assert basic_config_items["failed_queue_max_retries"]["slider"] == {
        "min": 0,
        "max": 10,
        "step": 1,
    }
    assert basic_config_items["download_media_timeout"]["slider"] == {
        "min": 1,
        "max": 300,
        "step": 1,
    }

    ffmpeg_items = schema["ffmpeg"]["items"]
    assert ffmpeg_items["video_transcode_timeout"]["slider"] == {
        "min": 10,
        "max": 1800,
        "step": 10,
    }
    assert ffmpeg_items["gif_transcode_timeout"]["slider"] == {
        "min": 10,
        "max": 1800,
        "step": 10,
    }

    sender_strategies = schema["sender_strategies"]
    sender_strategy_options = [
        "telegram",
        "aiocqhttp",
        "qq_official",
        "weixin_oc",
    ]
    assert sender_strategies["type"] == "object"
    enabled_platforms = sender_strategies["items"]["enabled_platforms"]
    assert enabled_platforms["type"] == "list"
    assert enabled_platforms["default"] == sender_strategy_options
    assert enabled_platforms["options"] == sender_strategy_options
    assert enabled_platforms["items"]["type"] == "string"
