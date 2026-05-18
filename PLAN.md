# RSSHub 插件扩展化与 AI 编排重构计划

日期：2026-05-18

## Summary

插件定位收敛为 **RSS 状态、调度、去重、可靠发送基础设施 + 可扩展组件加工 runtime**。

RSS 抓取、订阅管理、去重、推送历史、多平台发送和失败重试继续由插件负责；翻译、总结、日报、深层 XML 解析、Feed 级格式化交给 AI 或外部扩展完成。插件核心只接收稳定的结构化组件结果，再按平台可靠发送。

实施顺序调整为：

1. 先完成旧计划收尾，删除会阻碍新架构的翻译管道、翻译缓存、RSSHub route stub 和旧内容过滤残留。
2. 集成 RSSHub Routes 知识库导入/同步，让 Agent 能通过 AstrBot KB 和 skill 查路由。
3. 再建立平台无关组件契约，把发送层输入从“最终文本 + 媒体 URL”升级为 `ComponentDocument`。
4. 最后实现独立 venv 子进程扩展 runtime、Registry、作者辅助 skill 和内置 AI formatter extension。

## Decisions

- **AI 边界**：日报、翻译、总结全部交给 AI 或扩展；插件只保留可靠发送、基础 fallback、推送历史和可观测性。
- **失败策略**：AI/扩展失败时有限重试；仍失败则放行原始 entry 或基础组件，避免断流。
- **发布策略**：AI 产物默认自动发布，不做人工审阅队列。
- **扩展信任模型**：允许任意 Python 代码，但运行在独立 venv 子进程中。
- **扩展来源**：通过中心化 Registry 发现和安装；Registry 可以记录任意远程 URL。
- **资源访问**：默认开放网络和文件访问，主要依赖 AstrBot 插件隔离机制与管理员信任。
- **扩展 API 边界**：扩展不直接拿主进程内部单例，只通过受控上下文、事件 payload 和 RPC 服务访问插件能力。
- **扩展生命周期**：长期安装包，可被多个 feed 复用。
- **扩展组合规则**：按显式配置顺序串行执行，上一个扩展的输出作为下一个扩展的输入。
- **组件契约**：扩展输出平台无关组件，由插件转换为 AstrBot MessageChain。
- **格式化优先级**：扩展返回组件时跳过内置文本格式化器；无组件结果时走基础格式化 fallback。
- **Feed 级格式化**：AI formatter 绑定 Feed 级配置，不做会话级临时格式化规则。
- **知识库边界**：插件只负责 RSSHub Routes KB 导入、同步、状态和 LLM 提示注入；检索与使用交给 AstrBot 内置 KB 工具和 route skill。

## Current Cleanup Before New Architecture

这些是实现新 runtime 前应先完成的收尾项。它们不属于扩展 runtime 本身，但会影响后续接口设计和测试稳定性。

- 删除传统翻译路径：
  - `_conf_schema.json` 不再暴露 `translation`。
  - `ApplicationSettings`、config adapter、pipeline config 不再包含 translation behavior 字段。
  - `TranslationFilter`、translator providers、translation cache repository/API/UI 从主代码移除。
  - Plugin Pages 删除翻译配置、翻译缓存 tab、translation cache API 调用。
  - 旧数据库列 `translate`、`translate_target_lang` 不再读写；如暂不迁移表结构，仅作为历史列保留。
- 删除 RSSHub route stub：
  - 移除 `rsshub_search_routes` 和 `rsshub_get_route_schema` 两个只返回迁移提示的 LLM tool。
  - 保留 `rsshub_build_subscribe_url`，它仍是 Agent 构建订阅 URL 的原子工具。
  - README 和测试同步删除 route stub 说明。
- 清理旧内容过滤残留：
  - `ContentFilterService` 只剩测试覆盖，已删除；去重行为直接归 `Feed` 与 `FeedPollingService` 所有。
  - 当前 `MediaFingerprintService` port/adapter 已存在，不再作为未完成项。
  - scheduler 已统一调用 `FeedPollingService`，不再作为未完成项。

验收：

```bash
python -m json.tool _conf_schema.json >/private/tmp/rsshub_conf_schema_check.json
pytest -q tests/unit/application/test_settings.py
pytest -q tests/unit/interfaces/test_web_api.py
pytest -q tests/unit/application/test_llmtools.py
pytest -q tests/unit/application/test_content_processing_service.py
```

## Stage 1：RSSHub Routes 知识库集成

目标：将 RSSHub Routes 知识库导入 AstrBot，让 Agent 能查找路由、构建订阅 URL、再调用订阅工具。插件不提供 KB 搜索 LLM tool。

- 新增 Routes KB 同步服务：
  - 读取远端 `metadata.json`。
  - 读取本地 manifest，按 `path + sha256` 做增量 diff。
  - 只下载新增/变更文件，清理远端已删除文件。
  - 导入 `index/namespaces.md`、`index/*.md`、`docs/routes/**/*.md` 到 AstrBot KB。
  - 同名文档先删后上传，使用 path 作为稳定 doc name。
  - 后台任务同一时间只允许一个 running sync。
- 新增 source adapter：
  - `auto`：镜像优先，失败回退官方源。
  - `mirror`：只使用镜像源，失败报错。
  - `github`：只使用官方 GitHub/raw。
  - `local`：从本地目录导入，支持离线部署。
- 新增管理入口：
  - Plugin Pages 展示 KB 状态、同步进度、最近错误和手动同步按钮。
  - Chat command 保留最小集合：`/rsshub_kb_init`、`/rsshub_kb_sync`、`/rsshub_kb_status`、`/rsshub_kb_task`。
  - 不恢复 `rsshub_search_routes` 和 `rsshub_get_route_schema` LLM tool。
- LLM 注入与 skill：
  - `@filter.on_llm_request()` 识别 RSSHub route 查询意图时注入 KB name 和使用提示。
  - route skill 指导 Agent：先用 AstrBot KB 工具查 `RSSHub Routes`，再用 `rsshub_build_subscribe_url` 构建 URL，最后用 `rss_subscribe` 订阅。

验收：

```bash
pytest -q tests/unit/application/test_route_knowledge_service.py
pytest -q tests/integration/test_route_knowledge_sync.py
pytest -q tests/unit/interfaces/test_web_api.py
```

## Stage 2：组件契约与发送层收敛

目标：让插件内部形成稳定的“结构化组件 → 平台 MessageChain”边界，为 AI/扩展输出提供统一落点。

- 新增平台无关组件模型：
  - `ComponentDocument`
  - `TextComponent`
  - `ImageComponent`
  - `VideoComponent`
  - `AudioComponent`
  - `FileComponent`
  - `LinkComponent`
  - `MetadataComponent`
- 调整发送入口：
  - Feed/entry 默认格式化结果也转换成 `ComponentDocument`。
  - Notification dispatcher 和 message sender 先支持组件文档，再保留原文本 fallback。
  - 组件结果优先于 RSStT/flowerss 文本格式化；未返回组件时才走基础格式化 fallback。
- 保留发送兼容行为：
  - 媒体下载失败时追加原始链接。
  - Telegram caption 限制仍生效。
  - OneBot merged-forward node name 继续优先 feed title，fallback `RSSHub`。
  - 推送尾部仍保留 legacy `via <link> | <feed> (author: ...)` 风格，直到组件 formatter 明确替代。

验收：

```bash
pytest -q tests/unit/infrastructure/test_message_formatter.py
pytest -q tests/unit/application/test_notification_dispatcher.py
pytest -q tests/unit/application/test_feed_polling_service.py
pytest -q tests/integration/test_feed_push_simulation.py
```

## Stage 3：子进程 Extension Runtime

目标：把扩展从同进程 import 任意 Python，升级为独立环境、可观测、可重启的业务能力模块。

- 将现有同进程 `PluginManager` / event bus 标记为 legacy，或迁移成新 runtime 的兼容层。
- 定义扩展包 manifest：
  - name
  - version
  - entrypoint
  - dependencies
  - supported_hooks
  - description
- 每个扩展使用独立 venv，作为子进程运行。
- 主进程与扩展通过 JSON-RPC 交换数据：
  - `initialize`
  - `handle_hook`
  - `health_check`
  - `shutdown`
- 第一版支持 hook：
  - `fetch`
  - `parse`
  - `entry_process`
  - `dedup`
  - `format`
  - `before_send`
  - `after_send`
- 扩展可以取消、替换或完全接管结果。
- 多扩展按 feed 配置中的显式顺序串行执行，上一个扩展的输出作为下一个扩展的输入。
- 扩展异常、超时、非法组件输出、进程退出时记录错误，有限重试后 fallback 放行。

验收：

```bash
pytest -q tests/unit/application tests/unit/infrastructure
pytest -q tests/integration/test_plugin_integration.py
```

## Stage 4：Registry、Plugin Pages、Skill 与内置 AI Formatter

目标：形成可被 AI 生成、安装、验证和长期复用的扩展生态雏形。

- Plugin Pages 增加扩展管理：
  - 安装
  - 启停
  - 排序
  - 版本
  - 依赖安装状态
  - 运行日志
  - 错误状态
- Registry 元数据至少包含：
  - 扩展名
  - 版本
  - 入口
  - 依赖
  - 远程 URL
  - 校验信息
  - 描述文档
- 支持从 Registry 安装扩展、更新扩展、锁定版本和校验下载结果。
- 第一版不做权限声明，也不做细粒度资源限制。
- 新增作者辅助 skill：
  - 生成扩展骨架。
  - 生成 hook 示例和组件输出示例。
  - 生成测试。
  - 生成扩展 manifest 和打包产物。
  - skill 只辅助开发/发布，不参与运行时推送链路。
- 内置 Feed 级 AI formatter extension：
  - 输入 feed、entry、raw XML 和当前 feed 配置。
  - 调用 AstrBot LLM。
  - 一次性完成深层 XML 解析、翻译、总结、改写和组件排版。
  - 输出 `ComponentDocument`。

验收：

```bash
pytest -q tests/unit/interfaces/test_web_api.py
pytest -q tests/unit/application tests/unit/infrastructure
pytest -q tests/integration
```

## Test Focus

- 翻译删除回归：
  - `_conf_schema.json` 不再包含 `translation` 分组。
  - Web API 不再返回或写入 translation behavior/cache。
  - Plugin Pages 不再显示翻译配置和翻译缓存。
  - FeedPollingService 不再调用传统 `TranslationFilter`。
  - 旧 `translate` 字段不影响订阅创建、导入导出和推送。
- 组件契约：
  - `text`、`image`、`video`、`audio`、`file`、`link` 组件能转换成当前平台 MessageChain。
  - 扩展组件优先，未返回组件时基础格式化 fallback。
  - 媒体下载失败、Telegram caption、OneBot merged-forward、legacy via 尾部不回归。
- 扩展 runtime：
  - venv 创建、依赖安装、子进程启动、RPC 调用、超时、退出和重启。
  - 多扩展显式顺序执行，输出可串接。
  - 扩展接管 `format` / `before_send` 时仍记录推送历史和失败队列。
  - 异常、超时、非法组件输出时有限重试，最终 fallback 放行。
- RSSHub Routes KB：
  - manifest diff 覆盖新增、更新、删除、无变化。
  - 镜像失败可 fallback；`mirror` 模式不回退官方。
  - sha256 校验失败拒绝导入。
  - 同名 doc 删除后重新上传。
  - 同一时间只允许一个同步任务。
  - route 查询意图才注入 KB 使用提示。
- AI formatter：
  - Feed 级配置启用后，entry 通过扩展产出组件。
  - LLM 返回非法 JSON、超时、异常时重试后放行。
  - raw XML 深层字段解析结果能进入组件输出。

## Non-goals

- 不再实现插件内置传统翻译管道。
- 不再实现插件内置日报/Digest 模块。
- 不再实现插件核心里的固定总结系统。
- 第一版不做扩展权限声明和细粒度沙箱。
- 第一版不做人工审阅队列。
- 第一版不把扩展输出直接绑定到 Telegram/OneBot 等平台私有消息结构。
- 不给插件新增 RSSHub route 搜索 LLM tool；检索走 AstrBot KB 工具。
- 不把已完成的旧架构阶段重新列入计划，例如 scheduler 统一、FeedPollingService、MediaFingerprintService port。

## Assumptions

- 接受破坏性删除传统翻译功能，不做旧翻译配置和缓存数据迁移。
- 接受任意远程扩展和默认开放资源访问带来的安全风险。
- AstrBot 插件隔离机制和管理员信任是第一版主要安全边界。
- 扩展 runtime 的稳定性优先于极致性能；子进程 RPC 的开销可以接受。
- AI/扩展失败不能阻断默认 RSS 推送。
- 发送可靠性、推送历史、去重、订阅管理仍是插件核心职责。
