# LLM 文档库

本目录用于保存后续开发、运维排查与版本演进所需的长期上下文，减少多轮对话时的信息遗漏。

## 目录索引

- [current-state.md](./current-state.md)：当前版本、架构状态与关键运行参数。
- [project-map.md](./project-map.md)：DDD 分层结构、核心模块职责与运行流程。
- [operations.md](./operations.md)：线上路径、配置位置、热重载命令。
- [decisions.md](./decisions.md)：重要问题、处理方式与当前选型依据。
- [roadmap.md](./roadmap.md)：后续开发事项与维护建议。

## 更新规则

出现以下变动时需要同步更新本目录内对应文档：

1. 新增或调整配置项。
2. 核心处理流程（调度、去重、发送、翻译）发生变化。
3. 线上路径、重载方式、发布方式发生变化。
4. 出现新的故障类型且已完成原因归纳。

## 使用顺序

首次接手时建议先读 `current-state.md` 与 `project-map.md`，再查看 `operations.md` 和 `decisions.md`。
