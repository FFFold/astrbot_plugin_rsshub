# CLAUDE.md — astrbot_plugin_rsshub

AstrBot plugin for RSS/Atom subscription, polling, and multi-platform push delivery.

## Project overview

- **Language**: Python 3.10+
- **Framework**: AstrBot plugin system
- **Architecture**: DDD layering (`src/domain`, `src/application`, `src/infrastructure`, `src/interfaces`)
- **License**: AGPL

## Communication language

**必须使用中文与用户交流。** When interacting with the user, always respond in Chinese.

## Skills

**Prefer using the `astrbot-dev-skill` when writing or modifying this plugin.** It helps with AstrBot command decorators, Plugin Pages bridge, unified session IDs, and platform adapter behavior.

If the skill is not available in the current session, ask the user whether they want to install it:

> 当前未加载 astrbot-dev-skill，建议安装以提升 AstrBot 插件开发效率。是否安装？
> - 项目本地安装：`npx skills add xunxiing/AstrBot-Skill`
> - 全局安装（所有项目可用）：`npx skills add -g xunxiing/AstrBot-Skill`
> - 或手动下载：https://github.com/xunxiing/AstrBot-Skill/tree/v4

## Directory structure

```text
main.py                     # Plugin entry: lifecycle + command decorators only
bootstrap.py                # Startup wiring: deps, scheduler, Web API
metadata.yaml               # Plugin metadata
requirements.txt            # Dependencies

src/
  domain/                   # Entities, value objects, repository protocols
  application/              # Commands, queries, DTOs, app services
  infrastructure/           # Config, persistence, fetcher, messaging, schedule, utils
  interfaces/               # Command handlers + web_api adapter

pages/                      # Plugin Pages frontend
tests/                      # unit/integration tests, fixtures, mocks
```

## Key conventions

### Command behavior regression guards

- Keep these commands on full-argument signatures (`GreedyStr` compatible):
  - `/sub`
  - `/unsub`
  - `/sub_list`
  - `/sub_export`
  - `/sub_import`
  - `/sub_test`
- Runtime control commands:
  - `/sub_status`
  - `/sub_stop [job_id|feed_id|all]`
- Help command:
  - `/rsshelp` (send image help panel)
- `/sub_test <ID|URL> [start] [end]` must be **real push**, not preview-only.
- `/sub_import` supports TOML file path and upload-waiting flow; no OPML fallback.
- `/sub_list` only lists current session; no `all` scope in chat command.
- `/sub` and `/unsub` both support batch arguments.

### Push formatting compatibility

- OneBot (`aiocqhttp`) merged-forward node name: use feed/channel title when available; fallback to `RSSHub`.
- Push content keeps legacy tail line style:
  - `via <entry_link> | <feed_title_or_link> (author: <author>)`

### Layer boundaries

- `main.py`: lifecycle + decorators + delegation only.
- `bootstrap.py`: dependency graph and startup ownership.
- Business rules in `domain`/`application`; platform and IO details in `infrastructure`/`interfaces`.

### Runtime data paths

- Use `src/infrastructure/utils/paths.py` for plugin-owned data, cache, and export paths.
- Do not call `get_astrbot_plugin_data_path()` directly outside that helper.
- Local debugging from the plugin directory must not create or use `<plugin>/data`; the path helper redirects to the AstrBot project root data directory when available, otherwise to the system temp directory.

## AstrBot integration notes

- Use `@filter.command(...)` for commands.
- Management UI is via Plugin Pages + `WebApiHandler` routes.
- `_conf_schema.json` only exposes startup-level config, credentials, and platform strategies; subscription defaults and pipeline behavior belong in Plugin Pages.
- Keep `src/application/settings.py` as application-layer dataclasses only; AstrBot config parsing and legacy compatibility belong in `src/infrastructure/config/settings_adapter.py`.
- Do not reintroduce removed admin chat entry (`/rsshub_admin`, `handle_admin_panel`).

## Dev commands

Run from plugin directory:

```bash
python tests/run_tests.py -v
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
pytest tests/ -v
```

From AstrBot project root:

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

## Current progress snapshot

Recent regression recovery completed:

- Restored command semantics for `/sub_test`, `/sub`, `/unsub`, `/sub_list`, `/sub_export`, `/sub_import`.
- Restored `/sub_test` real push path for ID/URL and 1-based range.
- Restored OneBot merged-forward compatibility behavior and legacy `via ...` tail format.
- Added/updated handler + application regression tests for command routing and formatting.
- Command surface cleanup:
  - Removed `/refresh` and `/batch_unsub` chat commands.
  - Replaced `/sub_set` + `/sub_set_user` + `/sub_get_user` with command group `/sub_profile set|get`.
  - Replaced `/sub_set_session` + `/sub_get_session` with command group `/sub_session set|get`.
- Queue control + audit semantics:
  - Added `/sub_status` and expanded `/sub_stop` (no-arg/job_id/feed_id/all).
  - Stopped jobs are persisted as `push_history.status = stopped` and are not retried.
- Added `/rsshelp` and pre-generated image help flow:
  - command sends `assets/help/rsshelp.png`
  - generator script: `scripts/generate_rsshelp_image.py`
- Added centralized runtime path helper to prevent local debugging from writing plugin runtime data under the repository `data/` directory.
- Completed P1 content pipeline integration:
  - `FeedPollingService` now runs `ContentProcessingService` after dedup/HTML parsing and before dispatch.
  - Pipeline config supports keyword black/white lists, minimum content/media thresholds, and AI filter/enrich toggles.
  - Plugin Pages exposes subscription defaults, pipeline settings, TOML import/export, test URL, refresh, push history, and stats entry points.
- Traditional translation pipeline, translation cache UI/API, RSSHub route stub LLM tools, and legacy `ContentFilterService` have been removed. Future translation/summarization work belongs in AI/extension paths.

## Maintenance

**当代码发生重大变化时必须同步更新本文件。** Especially when changing:

- command surface/signatures
- push formatting behavior
- startup wiring or dependency graph
- Web API/Page behavior
- test/lint command flow
