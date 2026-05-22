# RSSHub 文档索引

`astrbot_plugin_rsshub` 的补充文档按用途拆分为三个目录：

- [`project/`](./project/README.md): 项目定位、架构、现状与路线图
- [`dev/`](./dev/README.md): 开发环境、测试流程、贡献约定
- [`usage/`](./usage/README.md): 面向使用者的命令、配置、管理页说明

## 章节索引

### project

- [`project/overview.md`](./project/overview.md): 项目定位、边界、设计目标与核心取舍
- [`project/architecture.md`](./project/architecture.md): 架构全景、模块关系、运行主链路与配置职责
- [`project/polling.md`](./project/polling.md): Feed 轮询、条件抓取、去重窗口和 dispatch 输入构造
- [`project/dispatch.md`](./project/dispatch.md): 分发、push history 生命周期、失败分类与重试语义
- [`project/handlers.md`](./project/handlers.md): handler registry、继承、执行顺序、AI filter/transform 与 trace
- [`project/formatting.md`](./project/formatting.md): `EntryTextFormatter`、`MessageComponentSorter` 与平台兼容顺序
- [`project/knowledge.md`](./project/knowledge.md): RSSHub Routes 知识库同步、manifest diff、任务状态与 source adapter
- [`project/roadmap.md`](./project/roadmap.md): 当前状态与后续演进方向

### dev

- [`dev/setup.md`](./dev/setup.md): 环境准备、运行入口、目录约束
- [`dev/testing.md`](./dev/testing.md): lint、pytest、回归清单
- [`dev/contributing.md`](./dev/contributing.md): 贡献流程、改动边界、提交约定

### usage

- [`usage/README.md`](./usage/README.md): 使用文档索引与后续拆分计划

## 推荐阅读路径

### 我想快速理解这个插件

1. [`project/overview.md`](./project/overview.md)
2. [`project/architecture.md`](./project/architecture.md)
3. 按需继续阅读 `project/` 下的模块章节
4. [`README.md`](../README.md)

### 我要参与开发或维护

1. [`dev/setup.md`](./dev/setup.md)
2. [`dev/testing.md`](./dev/testing.md)
3. [`dev/contributing.md`](./dev/contributing.md)

### 我只想查命令和配置

目前仍以根目录 [`README.md`](../README.md) 为主，后续会逐步拆分到 [`usage/`](./usage/README.md)。

## 文档状态

- `project/`: 已升级为章节型架构文档，覆盖核心链路与主要模块
- `dev/`: 本轮已完成
- `usage/`: 已创建目录与索引，内容待继续拆分
