# 项目文档

本目录用于说明插件是什么、为什么这样设计、当前做到什么程度，以及后续准备往哪里走。

## 目录

- [`overview.md`](./overview.md): 项目定位、能力边界、核心特性
- [`architecture.md`](./architecture.md): 架构全景、设计理由、核心模块关系
- [`polling.md`](./polling.md): Feed 轮询、去重、增量识别与 dispatch 输入构造
- [`dispatch.md`](./dispatch.md): 推送分发、history 语义、失败重试与 sender 入口
- [`commands.md`](./commands.md): 订阅命令链、测试推送与完整入口分支
- [`web_api.md`](./web_api.md): Dashboard 的 HTTP 数据面、筛选和管理接口
- [`repositories.md`](./repositories.md): 仓储层、ORM 适配和查询/幂等细节
- [`sender.md`](./sender.md): NotificationService、sender adapter 与媒体 fingerprint
- [`handlers.md`](./handlers.md): handler registry、继承、AI filter/transform 行为
- [`formatting.md`](./formatting.md): 文本格式化、媒体组件排序与平台兼容策略
- [`knowledge.md`](./knowledge.md): RSSHub Routes 知识库同步、manifest diff 与任务状态
- [`roadmap.md`](./roadmap.md): 当前版本状态与后续演进方向

## 适合谁看

- 第一次接手这个插件的维护者
- 需要了解当前实现边界的协作者
- 准备规划新功能或排查架构问题的人

## 推荐阅读顺序

1. [`overview.md`](./overview.md)
2. [`architecture.md`](./architecture.md)
3. 按需阅读各模块深挖文档
