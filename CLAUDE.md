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
  infrastructure/           # Config, persistence, fetcher, messaging, schedule, knowledge, utils
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
- RSSHub Routes KB commands:
  - `/rsshub_kb_init`
  - `/rsshub_kb_sync`
  - `/rsshub_kb_status`
  - `/rsshub_kb_task`
- `/sub_test <ID|URL> [start] [end]` must be **real push**, not preview-only.
- `/sub_import` supports TOML file path and upload-waiting flow; no OPML fallback.
- `/sub_list` only lists current session; no `all` scope in chat command.
- `/sub` and `/unsub` both support batch arguments.

### Push formatting compatibility

- OneBot (`aiocqhttp`) merged-forward node name: use feed/channel title when available; fallback to `RSSHub`.
- Push content keeps legacy tail line style:
  - `via <entry_link> | <feed_title_or_link> (author: <author>)`
- Only failure-facing fallback text / failure history may append raw media URLs; successful pushes should not gain an extra `媒体原始链接` suffix.
- Keep sender error detail and `PushHistory.fail_reason` within the 512-character persistence/model limit, and truncate legacy oversized DB values on read.
- `send_mode` semantics are `-1=仅链接`、`0=自动`、`1=直接发送`; legacy `1=Telegraph` should normalize to `0`, and legacy `2=直接消息` should normalize to `1`.
- Telegraph is a sender auto-routing policy instead of an explicit `send_mode`; it should only trigger for supported platform senders when deduplicated normalized media count is greater than 1.

### Subscription profile schema

- `rsshub_sub` and `rsshub_user` do not use `use_sub_config` / `use_user_config`; do not reintroduce those columns or API fields.
- `-100` is the only inheritance marker for subscription/user profile options. Subscription options inherit from user profile; user profile options inherit from global defaults.
- `rsshub_sub.handlers` and `rsshub_user.handlers` store JSON handler chains. Do not reintroduce `ai_prompt`; legacy non-empty prompts migrate to `builtin.ai_transform`.
- Legacy translation columns (`translate`, `translate_target_lang`) must stay removed from `rsshub_sub` and `rsshub_user`.

### Layer boundaries

- `main.py`: lifecycle + decorators + delegation only.
- `bootstrap.py`: dependency graph and startup ownership.
- Business rules in `domain`/`application`; platform and IO details in `infrastructure`/`interfaces`.
- RSSHub Routes KB sync lives behind application ports; AstrBot KB APIs stay in `src/infrastructure/knowledge`.

### Runtime data paths

- Use `src/infrastructure/utils/paths.py` for plugin-owned data, cache, and export paths.
- Do not call `get_astrbot_plugin_data_path()` directly outside that helper.
- Local debugging from the plugin directory must not create or use `<plugin>/data`; the path helper redirects to the AstrBot project root data directory when available, otherwise to the system temp directory.

## AstrBot integration notes

- Use `@filter.command(...)` for commands.
- Management UI is via Plugin Pages + `WebApiHandler` routes.
- `_conf_schema.json` only exposes startup-level config, Routes KB provider/source settings, credentials, and platform strategies; subscription defaults belong in Plugin Pages.
- Fixed-choice `_conf_schema.json` fields should use `options`; bounded numeric fields should use `slider` instead of free-form numbers.
- `sender_strategies.enabled_platforms` is a list-style platform multi-select in `_conf_schema.json`; `sender_strategies.aiocqhttp` / `sender_strategies.telegram` are `template_list` platform strategy entries, and runtime currently reads only the first item for each platform. Keep runtime compatibility for old bool-map and object configs in infrastructure adapters.
- Plugin Pages may manage existing subscriptions, users, push history, subscription defaults, and Routes KB tasks, but must not provide new subscription creation or subscription TOML import/export entry points. Use chat commands or AI agent tools for those user-owned flows.
- Plugin Pages handler editors are schema-driven and shared between user/subscription forms; they should read `handlers/schema` when available, keep a frontend fallback, and preserve raw JSON editing for unknown extension handlers.
- Plugin Pages must not expose `link_preview` controls or state.
- Do not add or use a `webadmin` fallback user. Web API endpoints that mutate or export user-owned resources must receive an explicit real `user_id`.
- Do not restore legacy content-processing, translation, AI enrich pipeline settings, or `_conf_schema.json` content pipeline toggles. Current content processing belongs to the handlers chain.
- Formatter responsibilities are formatting parsed entries/media for senders only; do not put translation, enrichment, route lookup, or subscription command fallback behavior into formatter code. AI filtering belongs in `ContentHandlerRuntime`.
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
- Removed built-in content-processing pipeline:
  - `FeedPollingService` dispatches parsed/deduplicated entries without `ContentProcessingService`.
  - Plugin Pages exposes existing subscription management, user management, subscription defaults, refresh/test actions, push history, stats, and Routes KB entry points; it does not expose content pipeline settings or subscription import/export.
  - Traditional translation pipeline, translation cache model/UI/API, AI filter/enrich settings, RSSHub route stub LLM tools, and legacy `ContentFilterService` are removed. Future translation/summarization work belongs in AstrBot LLM or extension paths.
- Plugin Pages handler editing is schema-driven:
  - User and subscription editors share the same handler list editing model.
  - UI supports enable/disable, ordering, add built-in handler, delete, schema fields, and raw JSON advanced mode.
  - Frontend calls `/handlers/schema` when available and falls back to built-in XML/AI handler schema.
  - `link_preview` controls were removed from Plugin Pages.
- Simplified plugin user states to `用户` and `已封禁`; legacy non-negative states are treated as normal users and no plugin-owned admin/guest role should be reintroduced.
- Removed Plugin Pages `webadmin` fallback behavior; user-owned Web API writes now require explicit `user_id` and front-end actions pass the existing subscription owner.
- `sender_strategies.enabled_platforms` is rendered as a compact platform multi-select and saves inside the `sender_strategies` object while still reading legacy bool-map configs.
- `_conf_schema.json` uses dropdowns for Routes KB source mode/source URLs and sliders for bounded numeric settings; Route KB raw URL joining preserves proxy prefixes such as `https://ghfast.top/https://raw...`.
- Added RSSHub Routes KB sync:
  - manifest diff, sha256 validation, single running sync task, and local state under plugin cache
  - mirror/auto/github/local source adapters plus fallback document fetch in auto mode and AstrBot KB upload/delete adapter
  - `/rsshub_kb_init` can create an empty AstrBot KB using configured or default embedding/rerank providers
  - knowledgebase workflow consumes the independent `FlanChanXwO/rsshub-routes-knowledgebase` repository from `main`
  - chat commands, Web API, and Plugin Pages for init/sync/status/task
  - LLM request hook injects AstrBot KB usage hints only for RSSHub route lookup intent
  - RSSHub route search remains delegated to AstrBot KB configuration/tooling and direct URL reasoning; no custom route-search/build LLM tools
- Hardened media failure fallback and push-history retry semantics:
  - failed first sends persist `media_urls`, retries rebuild media send requests from history
  - OneBot text fallback now carries all original media URLs when merged-forward media send fails
  - sender exception details and push-history failure reasons are normalized to the 512-char limit, including legacy oversized values read from storage
- Rebuilt subscription/user profile schema:
  - `rsshub_sub` and `rsshub_user` now include `handlers`
  - legacy `use_sub_config`, `use_user_config`, `translate`, and `translate_target_lang` columns are removed by migration/self-heal
  - profile inheritance is represented only by `-100`; user profile options default to `-100` to inherit global defaults
  - TOML import/export and Plugin Pages preserve editable handler chains
- Added agent XML instant-push support:
  - `rss_push_xml_entry` validates XML/HTML payloads, rejects malformed / oversized / DOCTYPE input, and parses tags into message content plus media
  - agent pushes are tracked in `push_history` with `source_type=agent` and `source_key`, without requiring a public `sub_id`
  - agent deduplication is success-only and scoped by `(source_type, source_key, user_id, target_session, entry_guid)`; retries send directly from history target/media
  - `rss_list_push_history` returns current-session JSON history, and XML-origin history persists `raw_xml` for audit/debug

## Maintenance

**当代码发生重大变化时必须同步更新本文件。** Especially when changing:

- command surface/signatures
- push formatting behavior
- startup wiring or dependency graph
- Web API/Page behavior
- test/lint command flow
