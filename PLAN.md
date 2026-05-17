# RSSHub 插件重构与更新计划

日期：2026-05-16

## 背景

本计划用于替代 `docs/llm/` 中分散的历史文档。`docs/llm/` 里有价值的信息主要分为三类：

- 长期架构决策：DDD 保留但简化、SQLite 继续使用、发送器策略模式保留、Plugin Pages 替代旧 aiohttp WebUI。
- 已完成实现记录：WebUI 迁移、微信专用发送器删除、部分 v2.1.1 修复、utils 分层清理。
- 后续路线图：配置收敛、同步去重统一、过滤器链集成、翻译管线、cron/PollRecord、Digest 功能。

这些内容已收敛到本文档。`docs/llm/` 后续可以删除，但删除前建议确认 `operations.md` 中的线上路径和热重载命令是否需要迁移到 `README.md` 或 `docs/operations.md`。

当前 `src/` 已经采用 `domain / application / infrastructure / interfaces` 的 DDD 风格目录，但实际依赖方向还不够干净：

- `application` 仍有少量直接依赖 `infrastructure`，例如日志工具和部分过渡路径；全局 config 读取已开始收敛到 `ApplicationSettings`。
- `infrastructure/schedule/rss_scheduler.py` 承载了核心同步、去重、状态更新、通知分发逻辑，不只是调度 Adapter。
- Feed 同步和去重仍存在两条路径：手动刷新/Web API 已走 `FeedPollingService`，但 scheduler 仍保留内联多指纹同步逻辑。
- `config` 既是 AstrBot 配置 Adapter，又是跨层全局 service locator。
- `Subscription.feed` 这类运行时展示/导出字段开始污染领域实体。

本计划的目标不是大规模移动文件，而是逐步建立清晰的 Module、Interface 和 Adapter，让核心用例有更好的 Locality 和测试面。

## 从 `docs/llm` 保留的决策

以下决策继续有效，应作为后续重构约束：

- **保留 DDD 基调，但压缩浅 Module。** 不追求“纯 DDD”，优先让核心用例有清晰 Interface 和集中 Implementation。命令/查询/DTO 如果只是传递参数，应在后续合并或简化。
- **继续使用 SQLite + SQLModel。** 当前订阅、Feed、用户、推送历史有明确关系查询需求，暂不迁移到 AstrBot KV。只有当迁移、锁竞争或部署成本成为主要问题时再评估 KV + JSON。
- **保留发送器策略模式。** OneBot、Telegram、QQ Official 有实际平台差异；微信/WeChat 继续走 `DefaultMessageSender`，不恢复专用发送器，除非未来有可验证的平台特异需求。
- **保留独立 `@filter.command` 注册。** Telegram/QQ 等平台的命令发现依赖明确命令注册，不改成单一 `/rss ...` 路由。
- **调度仍以订阅维度为主。** 不引入全局 Job 模型；cron、执行统计和批次摘要应作为订阅调度的增强。
- **不做 LLM 翻译回退链。** Google/Baidu 继续承担传统翻译；AI 能力应作为内容处理 Processor，一次完成总结、翻译、改写，而不是接在翻译失败后兜底。
- **Digest 是独立功能。** 日报/定点推送不扩展现有 Subscription 模型，应建立 `Digest` 模块，从 `PushHistory` 或轮询结果按时间窗口取材。
- **WebUI 走 Plugin Pages。** 旧 `src/infrastructure/web/` 的 aiohttp WebUI 已被 `pages/` + `src/interfaces/web_api.py` 替代，后续只维护 Plugin Pages。

## 当前代码校验结论

本次对 `docs/llm/` 和当前代码交叉检查后，以下事项需要按当前代码状态理解：

- `docs/llm/project-map.md` 已经过时，仍提到旧 `pipeline/normalizer.py`、`deduplication_service.py` 等路径；当前实际代码已有 `pipeline/filters/`、`pipeline/formatter.py`、`infrastructure/media/`、`interfaces/web_api.py`。
- `docs/llm/dedup.md` 和 `roadmap.md` 中“图片/视频指纹待实现”的描述不完全准确；当前 `RSSScheduler._hash_entry()` 已经尝试媒体 SHA256，但实现直接碰 `RSSFeedFetcher` 私有 session，应该抽成独立 Adapter 或在第一轮先限制为文本/URL 指纹。
- `FeedSyncService` 已降级为 `FeedPollingService` 的薄 wrapper；`RSSScheduler` 仍有重复同步路径，后续应让 scheduler 触发 `FeedPollingService`。
- `pipeline/filters/` 已有过滤器链 Interface 和默认过滤器，但尚未接入 scheduler 主路径，也缺少从插件配置到 `PipelineConfig` 的完整映射。
- `NotificationDispatcher` 已改为通过 `MessageSenderProvider` 注入发送器；后续仍需减少 application 层对 infrastructure utils 的轻量依赖。
- `MediaDownloader` 已移动到 `infrastructure/media/`，但仍保留较复杂的自定义缓存、锁和 GC。`docs/llm` 里的激进删除方案不建议直接做，后续只做低风险并发/缓存收敛。

## 目标形态

```text
main.py
  -> 读取 AstrBot config
  -> 构造 application settings
  -> 构造 infrastructure adapters
  -> 注入 application use cases

interfaces/
  -> 只处理 AstrBot 命令、Web API、输入输出适配

application/
  -> 编排用例
  -> 依赖 ports/settings，不直接 import infrastructure

domain/
  -> Feed、Subscription、去重策略等纯领域规则
  -> 不读取 config，不依赖 ORM，不依赖 AstrBot

infrastructure/
  -> DB、HTTP、RSS parser、sender、AstrBot config adapter、scheduler adapter
```

## 当前执行状态

更新日期：2026-05-16

标记说明：

- `[x]` 已完成并通过当前测试。
- `[~]` 已部分完成，仍有明确剩余工作。
- `[ ]` 未开始。

架构重构阶段：

- `[x]` 阶段 1：收敛 Config。`ApplicationSettings` 已建立，主要命令和服务已从 `main.py` 注入 settings/adapter；全局 config 遗留读取点放到阶段 6 清理。
- `[x]` 阶段 2：建立 Application Ports。`FeedFetcher`、`FeedParser`、`MessageSenderProvider`、`Clock` port 已建立，发送器已通过 provider 注入。
- `[x]` 阶段 3：统一 Feed 同步用例。`FeedPollingService` 已落地，手动 `/refresh`、Web API refresh、scheduler 和 `test_sub` 已统一到同一抓取解析入口。
- `[x]` 阶段 4：把 Scheduler 降级为 Adapter。`RSSScheduler` 现只负责到期订阅查询、分组触发和下次检查时间回写。
- `[x]` 阶段 5：整理 Domain 和 DTO。`SubscriptionExportRecord` 和导出查询已落地，导出不再往 `Subscription` 挂运行时 `feed`。
- `[ ]` 阶段 6：清理聚合导出和全局状态。

插件更新计划：

- `[~]` P0：稳定性和行为一致性。RSS 解析、Feed 去重、TOML 导入导出测试已固化；会话级推送队列和 `/rss_stop` 已实现；scheduler refresh 统一和重试路径细测仍未完成。
- `[ ]` P1：核心体验增强。过滤器链、翻译管线、内容处理服务尚未接入主流程。
- `[ ]` P2：调度与可观测性。cron、PollRecord、轮询健康状态尚未开始。
- `[ ]` P3：新功能。RSSHub Routes 知识库、Digest、AI 内容处理尚未开始。
- `[ ]` P4：代码瘦身。legacy 同步路径、全局状态和 eager exports 尚未清理。

最近一次验证：

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests -q
# 164 passed

UV_CACHE_DIR=.uv-cache uv run python tests/run_tests.py -v
# 20 passed, 0 failed

RUFF_CACHE_DIR=.ruff_cache UV_CACHE_DIR=.uv-cache uv run ruff check <本阶段触达文件>
# All checks passed
```

注意：`ruff check .` 当前仍会暴露一批既有 lint 问题，集中在未触达旧模块，例如 `pipeline/filters/base.py`、部分聚合 `__init__.py` 和旧 handler 文件。这些归入阶段 6/P4，不在阶段 3 的变更范围内。

## 分阶段实施

### 阶段 1：收敛 Config

状态：`[x]` 已完成基础落地；遗留清理并入阶段 6。

目标：去掉 application 层对 `get_config_manager()` 的直接调用。

新增：

- `src/application/settings.py`
  - `FeedFetchSettings`
  - `SchedulerSettings`
  - `SubscriptionDefaults`
  - `TranslationSettings`
  - `SenderStrategySettings`

保留：

- `src/infrastructure/config/config_manager.py` 继续负责 AstrBot config 解析、迁移和保存。

调整：

- `main.py` 将 `RsshubPluginConfig` 转成 application settings，再注入 commands/services。
- `SubscribeFeedCommand` 不再读取 `get_config_manager()`，改为接收 `FeedFetcher` 或 `FeedFetchSettings`。
- `TranslationService` 不再读取不一致字段名。
- 修复字段不一致：
  - `TranslationConfig.display_original_content` vs `translation_service.display_original`
  - `TranslationConfig.cache_translations` vs `translation_service.cache_enabled`
  - `BaiduTranslator` 读取 `config.baidu_translate`，但 `RsshubPluginConfig` 当前没有该字段。

验证：

- `[x]` 新增 config/settings 单测。
- `[x]` `SubscribeFeedCommand` 单测不依赖全局 config。
- `[x]` 现有导入导出、订阅命令测试通过。
- `[ ]` 清理少数过渡路径中的全局 config 读取点，放到阶段 6。

### 阶段 2：建立 Application Ports

状态：`[x]` 已完成基础落地；轻量 import 清理并入阶段 6。

目标：application 只依赖 Interface，infrastructure 提供 Adapter。

新增：

```text
src/application/ports/
  feed_fetcher.py
  feed_parser.py
  message_sender.py
  clock.py
```

建议 Interface：

- `FeedFetcher.fetch(url, headers=None) -> WebFeed`
- `FeedParser.parse(content) -> tuple[list[EntryParsed], str | None]`
- `MessageSenderProvider.get(platform_name) -> MessageSender`
- `Clock.now() -> datetime`

调整：

- `RSSFeedFetcher` 成为 `FeedFetcher` Adapter。
- `RSSParser` 成为 `FeedParser` Adapter。
- sender factory 不再被 `NotificationDispatcher` 直接 import，改由 `MessageSenderProvider` 注入。
- `main.py` 负责组装具体 Adapter。

验证：

- `[x]` application tests 使用 fake port，不 mock infrastructure。
- `[x]` `NotificationDispatcher` 测试不需要 AstrBot sender mock。
- `[ ]` 减少 application 层对 infrastructure utils/logger 的直接 import，放到阶段 6。

### 阶段 3：统一 Feed 同步用例

状态：`[~]` 部分完成；核心 use case 已落地，scheduler 迁移未完成。

目标：让手动刷新、定时轮询、测试推送走同一套同步和去重逻辑。

新增 Module：

- `src/application/services/feed_polling_service.py`

职责：

- 获取 Feed。
- 抓取 RSS。
- 解析 entries。
- 计算新增条目。
- 更新 Feed 去重状态。
- 调用通知分发。

从 `rss_scheduler.py` 迁移：

- `_migrate_hashes`
- `_calculate_update`
- `_hash_entry`
- `_merge_hash_history`
- `_resolve_hash_history_limit`
- `_resolve_entry_link`
- `_legacy_crc32`

媒体指纹逻辑单独决定：

- 若保留媒体内容 hash，抽成 `MediaFingerprintService` port。
- infrastructure adapter 负责下载媒体和计算 hash。
- application 不直接碰 aiohttp session。

调整：

- `[x]` `FeedSyncService` 已降级为薄 wrapper。
- `[x]` `/refresh` 和 Web API refresh 已调用 `FeedPollingService`。
- `[x]` `FeedPollingService` 已迁移文本/URL 多指纹去重、旧 hash 格式迁移、hash history 合并、bootstrap skip。
- `[x]` `Feed.entry_hashes` 已兼容旧版扁平列表并规范化为 `list[list[str]]`。
- `[ ]` scheduler 尚未调用 `FeedPollingService`。
- `[ ]` `test_sub` 尚未迁移到统一 polling/test path。
- `[ ]` 媒体内容指纹尚未抽成 `MediaFingerprintService` port；当前 application use case 不直接下载媒体。
- `[ ]` `ContentFilterService` 的后续定位尚未清理。

验证：

- `[x]` 使用 `tests/fixtures/feeds/twitter_rss.xml` 验证 RSS 解析和三轮去重。
- `[x]` 验证首次 bootstrap skip 行为。
- `[x]` 验证同一 entry 的稳定身份去重。
- `[x]` 验证旧 flat hash history 兼容。
- `[ ]` 验证手动 refresh 和定时 scheduler 结果一致，需阶段 4 完成后补。

### 阶段 4：把 Scheduler 降级为 Adapter

状态：`[x]` 已完成。

目标：`RSSScheduler` 只负责时间触发和订阅到期查询，不承载业务用例。

调整前：

- scheduler 直接依赖 ORM、DB session、HTTP fetcher、去重、notification dispatcher。

调整后：

```python
await feed_polling_service.poll_feed_group(feed_id, subscription_ids)
```

或：

```python
await feed_polling_service.poll_feed(feed_id)
```

保留在 scheduler 的职责：

- 找到 due subscriptions。
- 按 feed/interval 分组。
- 更新时间触发字段。
- 控制定时循环。

移出 scheduler 的职责：

- 抓取 RSS。
- 解析条目。
- 判断新增。
- 合并 hash history。
- 发送通知。

验证：

- `[x]` scheduler 单测只测“到期订阅分组和触发调用”。
- `[x]` Feed 同步行为只测 `FeedPollingService`。

### 阶段 5：整理 Domain 和 DTO

状态：`[ ]` 未开始。

目标：领域实体不承担展示/导出 read model 职责。

调整：

- 移除或弱化 `Subscription.feed` 这种运行时关联字段。
- 新增导出 read model：

```text
src/application/dto/subscription_export_record.py
```

或：

```text
src/application/queries/get_subscription_exports_query.py
```

建议模型：

```python
SubscriptionExportRecord(
    link: str,
    feed_title: str | None,
    options: dict[str, int | str],
)
```

调整：

- `ExportSubscriptionsCommand` 不再往 `Subscription` 挂 `feed`。
- repository/query 提供导出所需 read model。

验证：

- `[x]` TOML roundtrip 测试继续通过。
- `[x]` `Subscription.model_dump()` 不包含展示关联。

### 阶段 6：清理聚合导出和全局状态

状态：`[ ]` 未开始。

目标：减少浅 Module 和 import 副作用。

调整：

- 减少 `src/infrastructure/__init__.py` 的 eager import。
- 调用方改为从具体子包导入。
- `get_config_manager()` 标记为 legacy，只允许在 config Adapter 或少数过渡路径使用。
- 删除重复或废弃同步路径。

验证：

- `[ ]` pytest collection 不需要大量 AstrBot mock 才能导入纯模块。
- `[ ]` `ruff check .` 不出现 import 副作用、未使用导入和隐藏依赖。

## 插件更新计划

插件更新计划按用户可见价值和风险排序，和上面的架构重构交错推进。

### P0：稳定性和行为一致性

状态：`[~]` 部分完成；刷新和推送关键路径已加固，scheduler 统一仍未完成。

目标：先保证现有订阅、刷新、推送、导入导出行为一致。

- `[x]` 固化 RSS 解析、三轮 Feed 去重、TOML 导入导出的测试。已新增的 `twitter_rss.xml` 场景应作为回归测试保留。
- `[x]` 修正配置字段不一致，尤其是 translation、Baidu 凭据、sender strategy、media download、history limit 等运行时读取路径。
- `[~]` 统一手动 refresh、WebUI refresh、scheduler refresh 的同步逻辑；手动和 WebUI 已完成，scheduler 待阶段 4。
- `[x]` 修复 dispatch guard，使用明确的 `already_sent` 判断跳过已成功推送过的条目。
- `[~]` 给推送路径补单测；会话队列和 dispatcher 基础测试已补，重试细分场景仍待补。
- `[x]` 为每个会话推送任务建立 job id，支持 `/rss_stop` 停止当前会话正在运行的任务；同一会话串行执行，后续任务排队。

验收：

```bash
pytest tests/unit/application tests/unit/domain -q
pytest tests/integration/test_feed_push_simulation.py -q
pytest tests/unit/application/test_import_export.py -q
```

### P1：核心体验增强

状态：`[ ]` 未开始。

目标：把已有的半成品能力接入主流程。

- `[ ]` 接入 `pipeline/filters/`：去重之后、格式化/分发之前执行 `FilterChain.run()`。
- `[ ]` 将插件配置映射为 `PipelineConfig`，至少支持关键词黑白名单、最小长度、最少媒体数、传统翻译开关。
- `[ ]` 新增 `pipeline/processor.py` 或 application 层 `ContentProcessingService`，统一 AI 处理、传统翻译和透传 fallback。
- `[ ]` 建立翻译管线：主引擎 → 回退引擎 → 原文，并保留错误标记用于调试。
- `[ ]` WebUI 增加或完善过滤器/翻译配置、测试 URL、刷新、导入导出、统计信息入口。

验收：

```bash
pytest tests/unit/application -q
pytest tests/integration -q
```

### P2：调度与可观测性

状态：`[ ]` 未开始。

目标：让插件更容易运维和解释。

- `[ ]` `Subscription` 增加可选 `cron_expression`，优先 cron，失败回退 interval。
- `[ ]` 新增 `PollRecord` 或等价 read model，记录每次轮询的 feed、订阅数、抓取条目数、新条目数、推送成功/失败、耗时、错误摘要。
- `[ ]` WebUI 展示 Feed 健康状态、最近轮询、最近错误、推送统计。
- `[ ]` 调整 `RSSScheduler` 为调度 Adapter，只保留 due 查询、分组、触发和下次时间计算。

验收：

```bash
pytest tests/integration -q
python tests/run_tests.py --category unit
```

### P3：新功能

状态：`[ ]` 未开始。

目标：在核心同步路径稳定后再扩展能力。

- `[ ]` Digest/日报：新增独立 `Digest` 实体、命令和调度 loop，从 `PushHistory` 或轮询记录按时间窗口取材，支持 text/image 输出。
- `[ ]` RSSHub Routes 知识库：导入 `https://github.com/FlanChanXwO/rsshub-routes-knowledgebase`，提供路线检索、订阅辅助和 LLM 上下文注入。
- `[ ]` AI 内容处理：接入 AstrBot `context.llm_generate`，但默认关闭；AI 筛选失败时放行，避免误杀。
- `[ ]` 新数据源 Adapter：继续以 RSS 为核心，新增 Twitter/Nitter、网页发现、自定义 API 时统一输出 Entry-like 结构。
- `[ ]` 消息模板系统：把当前 formatter 变成可配置模板，但先保持默认模板兼容。

#### RSSHub Routes 知识库具体实现

目标：让用户能在插件内查询 RSSHub 支持哪些路由、路由参数怎么填，并在订阅 URL 构建、测试订阅和 LLM 对话时自动参考知识库。

参考实现：

- 用户给出的 `YunMo-yanyu/astrbot-/main.py` 使用 `KBHelper`/`context.kb_manager` 创建知识库、加载已有文档、后台同步任务、状态查询、搜索命令、会话绑定和 `@filter.on_llm_request()` 注入检索结果。
- 本插件不需要照搬网页爬取逻辑；RSSHub 知识库仓库已经生成了稳定 Markdown 和 `metadata.json`，应该直接做 manifest 增量同步。

知识库源格式：

- 仓库：`FlanChanXwO/rsshub-routes-knowledgebase`
- 入口文件：`metadata.json`
- 当前结构：
  - `metadata.json`：`version/source/stats/files`
  - `files[]`：`{"path": "...", "sha256": "..."}`
  - `index/namespaces.md`：命名空间目录
  - `index/<namespace>.md`：命名空间下路由目录
  - `docs/routes/<namespace>/*.md`：单条路由完整文档
- 当前规模约：`files=4794`、`documents=3207`、`namespaces=1586`。同步必须增量、后台执行、可恢复。

建议模块划分：

```text
src/application/services/route_knowledge_service.py
  -> use case: init/sync/status/search/bind/inject

src/application/dto/route_knowledge_dto.py
  -> KnowledgeSyncTask, KnowledgeSyncStatus, KnowledgeFileRecord

src/infrastructure/knowledge/
  github_source.py
  mirror_source.py
  manifest_store.py
  kb_importer.py

src/interfaces/route_knowledge_handlers.py
  -> chat commands

pages/rsshub/
  -> 知识库状态、同步按钮、搜索入口
```

数据落点：

- 远端文件缓存：`data/plugin_data/astrbot_plugin_rsshub/knowledge/rsshub-routes/`
- 本地 manifest：`data/plugin_data/astrbot_plugin_rsshub/knowledge/rsshub-routes/manifest.json`
- 同步状态：优先用 JSON state，后续需要查询统计时再入 SQLite。
- AstrBot 知识库名称默认：`RSSHub Routes`

同步算法：

1. 读取远端 `metadata.json`。
2. 读取本地 `manifest.json`，按 `path + sha256` 比较。
3. 只下载新增或变更文件，删除远端已不存在的本地文件。
4. 只导入以下文件到 AstrBot KB：
   - `index/namespaces.md`
   - `index/*.md`
   - `docs/routes/**/*.md`
5. 每个文件以 `path` 作为稳定 `doc_name`，导入前若已存在同名文档则删除再上传。
6. 上传使用 `KBHelper.upload_document(file_type="txt", pre_chunked_text=chunks)`，chunking 由本插件预切分，避免大文件一次性入库。
7. 任务后台运行，同一时间只允许一个同步任务；保留 task_id、当前文件、downloaded/imported/updated/deleted/failed、最近错误。

国内加速镜像要求：

- 必须支持可配置 `knowledge_source_mode`：
  - `auto`：默认，按镜像列表依次尝试，失败回退 GitHub 官方地址。
  - `mirror`：只使用国内/加速镜像，全部失败则报错。
  - `github`：只使用官方 GitHub。
  - `local`：从本地目录导入，适合离线部署。
- 默认候选 base URL：
  - 官方：`https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main/`
  - GitHub API fallback：`https://api.github.com/repos/FlanChanXwO/rsshub-routes-knowledgebase/contents/{path}?ref=main`
  - 加速镜像模板必须可配置，例如：
    - `https://ghfast.top/https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main/`
    - `https://gh-proxy.com/https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main/`
    - `https://gh.llkk.cc/https://raw.githubusercontent.com/FlanChanXwO/rsshub-routes-knowledgebase/main/`
    - 用户自建镜像：`{base}/{path}`
- 镜像健康检查：
  - 先请求 `metadata.json`。
  - 校验 JSON 可解析、`version` 存在、`files` 非空。
  - 下载文件后校验 sha256，不匹配则换下一个镜像重试。
- 不把某个公共镜像写死为唯一来源。公共代理稳定性不可控，插件必须允许用户替换为自建 mirror、GitHub Pages、Gitee、Cloudflare Worker、企业内网静态文件服务。

配置项：

```text
knowledge.enabled: bool = false
knowledge.kb_name: str = "RSSHub Routes"
knowledge.source_mode: "auto" | "mirror" | "github" | "local" = "auto"
knowledge.branch: str = "main"
knowledge.official_base_url: str
knowledge.mirror_base_urls: list[str]
knowledge.local_dir: str
knowledge.sync_on_startup: bool = false
knowledge.sync_interval_hours: int = 24
knowledge.max_files_per_sync: int = 0
knowledge.download_concurrency: int = 4
knowledge.upload_batch_size: int = 4
knowledge.upload_tasks_limit: int = 1
knowledge.chunk_max_chars: int = 1200
knowledge.chunk_overlap: int = 120
knowledge.inject_on_llm_request: bool = true
knowledge.inject_top_k: int = 5
```

命令入口：

- `/rsshub_kb_init [embedding_provider_id]`：创建或复用 AstrBot 知识库。
- `/rsshub_kb_sync [limit]`：后台增量同步知识库。
- `/rsshub_kb_status`：显示 KB id、文档数、chunk 数、source revision、最近任务。
- `/rsshub_kb_task [task_id]`：显示同步进度和最近错误。
- `/rsshub_kb_search <query>`：检索 route 文档，返回 doc name、score、摘要。
- `/rsshub_kb_bind [top_k]` / `/rsshub_kb_unbind`：将当前会话绑定/解绑知识库。

LLM 注入：

- 在 `@filter.on_llm_request()` 中识别 RSSHub route 查询意图，例如“某网站有没有 RSSHub 路由”“怎么订阅 B站/知乎/Telegram”“RSSHub 参数怎么填”。
- 命中时调用 `context.kb_manager.retrieve(query=..., kb_names=[kb_name])`，把结果以短上下文注入 system prompt。
- 不移除其它工具；只追加知识库提示，避免影响现有 RSS 订阅命令。

订阅辅助：

- `SubscribeFeedCommand` 不直接依赖 KB。
- 新增 route lookup use case，供 WebUI 和命令调用：
  - 输入站点名/URL/namespace。
  - 检索 `index/namespaces.md` 和对应 `index/<namespace>.md`。
  - 返回候选 route、示例路径、参数说明。
- WebUI 的“添加订阅”流程增加“查找 RSSHub 路由”面板，用户选择 route 后再拼接 RSSHub URL 并调用现有测试 URL。

验收：

```bash
pytest tests/unit/application/test_route_knowledge_service.py -q
pytest tests/integration/test_route_knowledge_sync.py -q
```

测试覆盖：

- manifest diff：新增、更新、删除、无变化。
- source fallback：镜像失败后换源；`mirror` 模式不回退官方。
- sha256 校验失败时拒绝导入。
- KB importer：同名 doc 删除后重新上传。
- 后台任务：同一时间只允许一个 running task。
- LLM 注入：只有 RSSHub route 意图才注入。

### P4：代码瘦身

状态：`[ ]` 未开始。

目标：删除已经被新路径替代的旧模块。

- `[x]` 降级 `FeedSyncService` 的旧 GUID 同步路径为 `FeedPollingService` wrapper。
- `[ ]` 删除 legacy config 全局读取点，`get_config_manager()` 只保留在 infrastructure config Adapter 和过渡层。
- `[ ]` 减少 `src/infrastructure/__init__.py`、`src/application/services/__init__.py` 的 eager exports。
- `[ ]` 根据真实调用情况清理旧兼容别名和未使用 DTO。

## `docs/llm` 删除建议

可以删除，但建议按以下顺序处理：

1. 保留本文档作为主计划，替代 `docs/llm/roadmap.md`、`decisions.md`、`current-state.md`、`architecture-refactor.md`。
2. 将 `docs/llm/operations.md` 的热重载、数据目录、发布步骤迁移到 `README.md` 或新建 `docs/operations.md`。
3. 删除已过时或已完成的历史记录：`status-report.md`、`optimization-summary.md`、`todo-fixes.md`、`v2.1.1-fixes.md`、WeChat 相关分析文档。
4. 删除后运行一次 `rg "docs/llm|llm/"`，确认 README 或脚本没有失效引用。

## 推荐 PR 顺序

1. `docs(plan): preserve llm docs decisions before cleanup`
2. `fix(config): align translation and baidu config fields`
3. `test(feed): lock rss parsing dedup and toml roundtrip behavior`
4. `refactor(config): introduce application settings and inject fetch settings`
5. `refactor(application): add feed fetcher/parser/sender ports`
6. `refactor(sync): introduce feed polling service`
7. `refactor(schedule): make scheduler trigger feed polling use case`
8. `feat(pipeline): connect filter chain to feed polling`
9. `refactor(export): use export read model instead of Subscription.feed`
10. `feat(schedule): add poll records and optional cron`
11. `feat(knowledge): import and sync RSSHub routes knowledgebase`
12. `chore(infrastructure): reduce package-level eager exports`

## 每阶段通用验收

每个 PR 至少运行：

```bash
pytest tests/unit/application tests/unit/domain -q
pytest tests/unit/application/test_feed_parsing.py tests/integration/test_feed_push_simulation.py tests/unit/application/test_import_export.py -q
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

涉及 scheduler、DB、通知发送时额外运行：

```bash
pytest tests/integration -q
python tests/run_tests.py --category unit
```

## 非目标

以下事项不要在第一轮重构中做：

- 不要一次性重命名所有目录。
- 不要一次性移动所有 infrastructure 文件。
- 不要把所有东西都抽象成 port，只抽 application 正在直接依赖的 infrastructure。
- 不要同时改 scheduler、config、notification、export 的行为。
- 不要为了“DDD 纯度”删除现有兼容入口，先标记 legacy，再迁移调用方。

## 第一刀建议

从 config 开始：

1. 修正 translation 和 baidu 配置字段不一致。
2. 新增 `application/settings.py`。
3. 让 `SubscribeFeedCommand` 停止读取全局 config。
4. 在 `main.py` 注入 settings 或 fetcher Adapter。

这一步风险低，能立刻减少 application 对 infrastructure config 的依赖，并为后续 ports 和 feed polling 重构铺路。
