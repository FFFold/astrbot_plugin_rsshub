# AGENTS.md — astrbot_plugin_rsshub

Repository guide for agent work on this plugin.

## Project overview

- AstrBot RSSHub plugin with DDD layering.
- Entry split is strict: `main.py` (decorators/lifecycle) and `bootstrap.py` (composition/startup).
- Management features belong to Plugin Pages + Web API.

## Communication language

- 与用户沟通必须使用中文。

## Structure

- `src/domain/`: entities, value objects, repository protocols.
- `src/application/`: commands, queries, DTOs, orchestration services.
- `src/infrastructure/`: adapters for config/persistence/fetch/messaging/scheduling.
- `src/interfaces/`: command handlers and `web_api.py`.
- `pages/`: Plugin Pages frontend.
- `tests/`: unit/integration suites and fixtures.

## Command surface invariants

Keep these command signatures full-argument (`GreedyStr` compatible):

- `/sub`
- `/unsub`
- `/sub_list`
- `/sub_export`
- `/sub_import`
- `/sub_test`

Behavior invariants:

- `/sub_test <ID|URL> [start] [end]` = real push (not preview).
- `/unsub` supports ID/URL mixed batch semantics.
- `/sub` supports multi-URL batch semantics.
- `/sub_list` supports current-session pagination only (no `all` scope).
- `/sub_export [all]` scope behavior with admin guard.
- `/sub_import` supports TOML path and upload-waiting flow.
- `/sub_status` lists running/queued jobs for current session.
- `/sub_stop [job_id|feed_id|all]` supports precise/批量 stop; no arg stops current running job.
- `/rsshelp` sends pre-generated help image (`assets/help/rsshelp.png`).

## Push compatibility invariants

- OneBot merged-forward node name: prefer feed title; fallback `RSSHub`.
- Push tail formatting should include legacy `via <link> | <feed> (author: ...)` style.

## Do-not-regress rules

- Do not reintroduce `/rsshub_admin` or `handle_admin_panel`.
- Do not add `Main` alias.
- Do not move startup ownership out of `bootstrap.py`.
- Do not call `get_astrbot_plugin_data_path()` directly outside `src/infrastructure/utils/paths.py`.
- Local debugging from this plugin directory must not create/use `<plugin>/data` for runtime state; use `get_plugin_data_dir()`, `get_plugin_cache_dir()`, or `get_plugin_export_dir()`.
- `_conf_schema.json` only exposes startup-level config, credentials, and platform strategies; subscription defaults and pipeline behavior belong in Plugin Pages.
- Keep `src/application/settings.py` as application dataclasses only; AstrBot config parsing and legacy compatibility belong in `src/infrastructure/config/settings_adapter.py`.

## Dev and test commands

```bash
python tests/run_tests.py -v
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
pytest tests/ -v
```

From AstrBot root:

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

## Current progress snapshot

Recently completed regression fixes include:

- Restored command signatures/semantics for `/sub_test`, `/sub`, `/unsub`, `/sub_list`, `/sub_export`, `/sub_import`.
- Restored real push behavior and range routing for `/sub_test`.
- Restored compatibility formatting (`via ...`) and OneBot merged-forward naming path.
- Added regression tests for handlers/application behavior.
- Command surface slimming:
  - Removed chat command `/refresh`.
  - Removed chat command `/batch_unsub` (use `/unsub` batch).
  - Replaced `/sub_set` + `/sub_set_user` + `/sub_get_user` with command group `/sub_profile set|get`.
  - Session config commands switched to command group: `/sub_session set|get`.
- Push job control upgrades:
  - Added `/sub_status` for runtime queue visibility.
  - Upgraded `/sub_stop` to support no-arg/job_id/feed_id/all.
  - Cancelled push history now persists `status=stopped` (non-retry).
- Added `/rsshelp` image help command and generator pipeline:
  - `scripts/generate_rsshelp_image.py`
  - `assets/help/rsshelp_template.html`
  - `assets/help/rsshelp.png` (committed pre-generated image)
- Centralized runtime data/cache/export paths in `src/infrastructure/utils/paths.py` to avoid plugin-repo `data/` pollution during local debugging.
- Completed P1 content pipeline integration:
  - `FeedPollingService` now runs `ContentProcessingService` after dedup/HTML parsing and before dispatch.
  - Pipeline config supports keyword black/white lists, minimum content/media thresholds, and AI filter/enrich toggles.
  - Plugin Pages exposes subscription defaults, pipeline settings, TOML import/export, test URL, refresh, push history, and stats entry points.
- Traditional translation pipeline, translation cache UI/API, RSSHub route stub LLM tools, and legacy `ContentFilterService` have been removed. Future translation/summarization work belongs in AI/extension paths.

## Update policy

When architecture, command surface, push formatting, config paths, or test/lint workflow changes, update both `CLAUDE.md` and `AGENTS.md` in the same change.
