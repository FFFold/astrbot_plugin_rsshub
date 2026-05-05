# 路线图

## 近期（1-2 轮迭代）

### 翻译管线增强
- 参考 `rss_forwarder` 引入 LLM 翻译增强。
- 回退链：LLM → Google → GitHub Models。
- 翻译诊断命令 `/rss test`。
- 将 `translation/` 整合到 `pipeline/`。

### 去重策略优化
- 当前去重耦合在 `rss_scheduler.py` 中。
- 参考 `rss_forwarder`：
  - 内容去重键（guid / link / 内容哈希）。
  - 发送前指纹保护（dispatch fingerprint）。
  - 图片 sha256 指纹。
- 提取到 `pipeline/deduplicator.py`。

### 调度器按 job 维度重构
- 当前按订阅维度调度，与数据库耦合过深。
- 参考 `rss_forwarder` 的 job 模式：
  - 支持 cron / interval 两种触发。
  - pause / resume 单个 job。
  - 任务级去重时效 `dedup_ttl_seconds`。

## 中期（3-5 轮迭代）

### 新数据源适配
- 参考 `twitter_source.py` 模式。
- 每种源一个适配器文件，输出统一 item 结构。
- 候选：Twitter/Nitter、网页 RSS 发现、自定义 API。

### 日报能力
- 参考 `rss_forwarder` 的 `daily_digests[]`。
- LLM 摘要 + text/image 两种发送形式。
- 素材归档在 `storage.py` 中。

### 维护 `docs/llm/`
- 保持项目结构、线上环境和历史决策可追溯。
- 每次核心流程变化时同步更新。

## 长期

### 架构精简
- 评估 DDD 各层实际收益，考虑将 `application/commands/` 和 `application/queries/` 合并简化。
- 评估 SQLite → AstrBot KV 迁移成本。

### 运维可观测性
- feed 健康状态 / target 发送状态 / 近期开销和错误统计。
- 面板集成。

### 更细的分发策略
- 按来源、关键字、时间段做选择性发送。
