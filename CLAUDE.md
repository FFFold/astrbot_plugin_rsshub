# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`astrbot_plugin_rsshub` is an AstrBot RSS subscription plugin (AGPL, Python 3.10+). It fetches RSS/Atom feeds on a schedule, deduplicates entries, translates content, and pushes updates to users across multiple chat platforms (OneBot/Telegram/QQ Official/WeChat).

**Key features**: Multi-platform push, failure retry queue, multi-bot deduplication, LLM tool calls for AI-driven subscription management, and an optional WebUI.

## Dev Commands

Run from the AstrBot project root (plugin lives at `data/plugins/astrbot_plugin_rsshub/`):

```bash
# Format + lint (required before commit)
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub

# Run tests
cd data/plugins/astrbot_plugin_rsshub/tests
python run_tests.py -v              # all tests
python run_tests.py --category unit           # unit only
python run_tests.py --category integration    # integration only
python run_tests.py --quick                   # fast mode

# pytest also works
pytest tests/ -v
```

Pre-commit hooks (`.pre-commit-config.yaml`) run ruff automatically on commit.

## Architecture

The project uses **Domain-Driven Design (DDD)** with four layers:

```
src/
├── domain/           # Pure business logic — no framework imports
│   ├── entities/     # Feed, Subscription, User, PushHistory, ContentNode
│   ├── repositories/  # Protocol interfaces (abstractions, not implementations)
│   └── services/     # ContentFilterService (dedup), FeedDiscoveryService
├── application/      # Use case orchestration
│   ├── commands/     # CQRS write operations (SubscribeFeed, Unsubscribe, etc.)
│   ├── dto/          # Data transfer objects
│   └── services/     # FeedSyncService, NotificationDispatcher
├── infrastructure/   # Technical implementations of domain interfaces
│   ├── config/       # RsshubPluginConfig, sub-configs, global get_config()
│   ├── persistence/  # SQLModel/SQLAlchemy ORM models + repository implementations
│   ├── fetcher/     # RSS feed fetching (feedparser)
│   ├── messaging/   # Multi-platform senders (Telegram, OneBot, QQ, WeChat)
│   ├── schedule/     # RSSScheduler — periodic feed checking
│   ├── pipeline/    # Content processing chain (Formatter, Filters)
│   ├── translation/  # Google/Baidu translation
│   └── media/       # Media download and transcoding (ffmpeg)
└── interfaces/       # Adapters bridging domain to external systems
    ├── handlers/    # Chat command handlers with @filter.command() routing
    └── web_api.py    # REST endpoints via context.register_web_api()
```

## Plugin Entry Point

`main.py` — `Main` class extends AstrBot's `Star`. Initialization order:

1. `_init_config()` → `_init_database()` → `_init_repositories()`
2. `_init_scheduler()` → `_init_web_api()` → `_init_handlers()`

Handlers auto-register via `ScanableHandler.__init_subclass__` meta-programming. All dependencies are held in a `_deps: _Deps` TypedDict; handlers access them via `__getattr__` proxies (e.g. `self._subscribe_cmd` → `self._main._deps["subscribe_cmd"]`).

## Data Directory

Plugin data lives at `data/plugin_data/astrbot_plugin_rsshub/` (not `plugin_dir/data/`). Database is SQLite.

## Key Patterns

- **CQRS**: Writes go through Command classes, reads through Query classes (separate `src/application/commands/` vs `queries/`)
- **Repository pattern**: Domain defines `Protocol` interfaces; infrastructure provides concrete implementations via factory singletons (`get_feed_repository()`, etc.)
- **Platform senders**: Strategy pattern in `src/infrastructure/messaging/senders/`, factory via `get_sender_for_platform(platform_name)`
- **Value objects**: `FeedUrl`, `UpdateInterval` — immutable validated types in `src/domain/value_objects/`
- **Auto-registration**: `ScanableHandler` base class auto-registers all subclasses on import

## AstrBot Integration

**Decorators** (`from astrbot.api.event import filter`):
- `@filter.command(name, alias, priority)` — register chat commands
- `@filter.command_group(name)` — grouped commands via `@group.command("sub")`
- `@filter.event_message_type(...)` — filter by `ALL`, `PRIVATE_MESSAGE`, `GROUP_MESSAGE`
- `@filter.platform_adapter_type(...)` — `TELEGRAM`, `AIOCQHTTP`, `QQ_OFFICIAL`, `WECHAT_OC`
- `@filter.permission_type(...)` — `ADMIN` / `MEMBER`
- `@filter.regex(pattern)` — regex trigger
- `@filter.llm_tool(name)` — expose as LLM tool

**Message components** (`from astrbot.api import message_components as Comp`):
`Plain`, `At`, `Image.fromFileSystem` / `.fromURL`, `Record`, `Video`, `File`, `Reply`, `Node` / `Nodes`

**Core objects**:
- `event.message_str` — plain text input
- `event.message_obj.message` — full message chain
- `yield event.plain_result(text)` — reply to user
- `context.send_message(umo, chain)` — proactive send
- `context.register_web_api(path, handler, methods)` — Web API; route must prefix plugin name (`/{PLUGIN_NAME}/endpoint`)

**LLM Tool pattern** (v4.5.7+, preferred over `@filter.llm_tool`):

```python
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

@dataclass
class MyTool(FunctionTool[AstrAgentContext]):
    name: str = "my_tool"
    description: str = "..."
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "..."}},
        "required": ["query"],
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        return "result"
```

Register via `self.context.add_llm_tools(MyTool())`.

**Plugin Pages** (WebUI):
- Pages live in `pages/<page_name>/index.html`; backend API registered with `context.register_web_api(f"/{PLUGIN_NAME}/endpoint", handler, ["GET"])`
- Frontend uses `window.AstrBotPluginPage` bridge: `ready()`, `apiGet(endpoint)`, `apiPost(endpoint, body)`, `subscribeSSE(endpoint, handlers)`
- AstrBot auto-injects bridge SDK; use relative paths for all assets (`./app.js`, `./style.css`)

## Critical Files

| File | Role |
|------|------|
| `main.py` | Plugin lifecycle, wiring, entry point |
| `src/application/services/feed_sync_service.py` | Orchestrates fetch → parse → dedupe → dispatch pipeline |
| `src/infrastructure/persistence/database_manager.py` | SQLite/SQLModel setup and migrations |
| `src/infrastructure/messaging/senders/default.py` | Base sender with media caching, locking, transient error detection |
| `src/domain/services/content_filter_service.py` | Entry deduplication (v3 fingerprint) |

## Configuration

New config options must update both `src/infrastructure/config/` and `_conf_schema.json` (used by WebUI/platform). The `CONTRIBUTE.md` has a pre-change checklist for config modifications.

## Testing

- `tests/mocks/mock_data.py` — `MockFeedData`, `MockEntryData`, `MockAstrMessageEvent`, `MockContext`
- `tests/conftest.py` — fixtures: `sample_rss_feed`, `mock_feed_entity`, `mock_subscription_entity`
- `tests/fixtures/feeds/` — real RSS/Atom XML samples for parsing tests
- Add new tests to `run_tests.py` via `TEST_CATEGORIES` dict, or create `pytest` files in `unit/`/`integration/`

## After-Edit Quality Check

**After every code edit**, run format + lint before committing or testing:

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

Fix all violations before proceeding. Pre-commit hooks will also run these, but catching issues locally is faster.