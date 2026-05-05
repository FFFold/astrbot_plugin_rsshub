# 当前状态

## 版本

- 仓库版本：`v2.0.0`
- 插件元数据名称：`astrbot_plugin_rsshub`
- 架构：DDD 四层（domain / application / infrastructure / interface）

## 当前能力

- 多用户 RSS 订阅管理（/sub /unsub /list /refresh）
- 基于 SQLite 的持久化去重与 Feed 状态
- 平台发送器策略模式（OneBot / Telegram / QQOfficial / WeChat）
- 事件总线扩展系统（EventBus + Extension）
- 多引擎翻译（Google / Baidu）
- RSSHub Radar API 路由发现
- 基于订阅维度的 interval 调度

## 核心模块状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 领域层 | ✅ 稳定 | 实体、仓库接口、值对象 |
| 应用层 | ✅ 稳定 | Commands / Queries / Services |
| 基础设施 - 数据采集 | ✅ 已重构 | `fetcher/` + `fetcher/rss/` |
| 基础设施 - 管线 | ✅ 已创建 | `pipeline/normalizer.py` |
| 基础设施 - 持久化 | ✅ 稳定 | SQLite + SQLModel |
| 基础设施 - 消息发送 | ✅ 稳定 | `senders/` 策略模式 |
| 基础设施 - 调度 | ⚠️ 需优化 | `rss_scheduler.py` 耦合较重 |
| 基础设施 - 翻译 | ✅ 稳定 | Google / Baidu |
| 接口层 main.py | ✅ 稳定 | 12 个命令注册 |
| 上下文文档体系 | ✅ 新增 | `docs/llm/` |

## 关键配置

- 数据目录：`data/plugin_data/astrbot_plugin_rsshub/`
- 数据库文件：`{data_dir}/rsshub.db`
- 配置来源：`_conf_schema.json` / `config.json`

## 运维约束

- 只允许单插件热重载。
- 使用 AstrBot 仪表盘 `/api/plugin/reload`。
- 数据目录应始终指向 `plugin_data/` 而非插件安装目录。
