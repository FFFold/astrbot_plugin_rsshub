# 关键决策

## 架构选型：DDD vs 扁平

### 当前选择
DDD 四层分层（domain / application / infrastructure / main）。

### 理由
- 项目初期预期复杂度较高，需支撑多数据源。
- OOP + 类型安全约束有利于多人协作。
- Protocol 接口便于替换实现（如 SQLite → KV）。

### 实践反思
- 当前规模下 DDD 的抽象成本（12 个命令文件 + 5 个接口文件 + DTO）高于扁平架构。
- 参考项目 `rss_forwarder` 用 10 个文件覆盖相同能力，代码更直观。
- 建议在保留 DDD 分层基调的前提下，精简不必要的接口层和 DTO。

## 持久化：SQLite vs KV

### 当前选择
SQLite + SQLModel ORM。

### 理由
- 外键约束和关联查询对订阅管理友好（sub → feed → user）。
- SQLModel 与 Pydantic 共用类型系统，与 DTO 层天然一致。
- 迁移、回滚能力成熟。

### 替代方案
参考项目使用 AstrBot KV + `state.json` + 文件锁，显著降低依赖和启动复杂度。
若后续发现 SQLite 维护成本过高（迁移、锁竞争），可考虑迁移到 KV + JSON。

## 数据采集层重构：rss/ → fetcher/ + pipeline/

### 背景
原 `src/infrastructure/rss/` 包名过于 RSS 特定，限制向多数据源扩展能力。
`rss_parser.py` 混合了 RSS 条目解析和通用文本工具函数。

### 方案
- `fetcher/http.py`：`HttpFetcher` 通用 HTTP GET + session 管理。
- `fetcher/rss/`：`RSSFeedFetcher` 继承 HttpFetcher 添加 feedparser 解析。
- `pipeline/normalizer.py`：文本/标识符标准化工具函数独立。

### 参考
`rss_forwarder` 的 `twitter_source.py` 模式 —— 每种新数据源只需一个适配器文件。
后续添加新数据源（如 Twitter、Web 抓取）时，统一放到 `fetcher/` 下。

## 发送层：策略模式 vs 统一分发

### 当前选择
策略模式：每个平台有自己的 sender 实现，通过 `get_sender_for_platform()` 工厂获取。

### 对比
| 方面 | 策略模式（我们） | 统一分发（rss_forwarder） |
|------|-----------------|--------------------------|
| 平台差异处理 | 每个 sender 自包含 | 在 dispatcher 中用 if/else |
| 新增平台 | 新建 sender 文件 + 注册 | 修改 dispatcher |
| 测试性 | 可单平台 mock | 需 mock 整个分发链路 |

### 结论
策略模式更适合多平台场景，保留现有设计。

## 数据库目录位置

### 历史
最初数据库创建在 `plugin_dir/data/` 下，违反 AstrBot 规范。

### 修正
使用 `get_astrbot_plugin_data_path()` → `data/plugin_data/astrbot_plugin_rsshub/`。
参考 `rss_forwarder` 的 `storage.py:plugin_cache_dir()` 实现。
