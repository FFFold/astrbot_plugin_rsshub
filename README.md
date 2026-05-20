# RSSHub for AstrBot

<div align="center">

<img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/logo.png" width="400" alt="rsshub"/>

<br/>

<img src="https://count.getloli.com/@astrbot_plugin_rsshub?name=astrbot_plugin_rsshub&theme=rule34&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="Moe Counter">

**AstrBot RSS 订阅插件。**

[![License: AGPL](https://img.shields.io/badge/License-AGPL-blue.svg)](https://opensource.org/licenses/agpl-3.0)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.10.4-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)

</div>

> 新开发者请先阅读贡献指南：[`CONTRIBUTE.md`](./CONTRIBUTE.md)
>
> **⚠️ 本项目正在升级到 v2.0.0，项目结构与数据库 schema 可能发生重大变化，请留意版本更新日志。**

---

## 📸 预览

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/manual_sub.png" width="400" alt="手动订阅"/>
        <br/>
        <sub>手动订阅</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/ai_sub.png" width="400" alt="AI订阅"/>
        <br/>
        <sub>AI订阅</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/ai_sub_and_query.png" width="400" alt="AI订阅 + AI查询订阅列表"/>
        <br/>
        <sub>AI订阅 + AI查询订阅列表</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/sub_export.png" width="400" alt="导出订阅"/>
        <br/>
        <sub>导出订阅</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/sub_import.png" width="400" alt="导入订阅"/>
        <br/>
        <sub>导入订阅</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/twitter_push.png" width="400" alt="推特推送"/>
        <br/>
        <sub>推特推送</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/master/assets/pixiv_push.png" width="400" alt="pixiv推送"/>
        <br/>
        <sub>pixiv推送</sub>
      </td>
    </tr>
  </table>
</div>

## ✨ 功能特性

- 📡 **RSS/Atom 订阅** - 支持订阅各类 RSS 源，实时推送更新
- 🔔 **智能推送** - 按订阅级/会话级 interval 调度，同一 feed 在不同会话可使用不同检查间隔
- 🎨 **富媒体支持** - 基于 HTML 结构解析内容（链接、图片、音频、视频、文件、At 组件等）
- ⚙️ **灵活配置** - 订阅级与用户默认级的消息格式选项，会话级默认配置（KV）
- 🤖 **LLM 工具调用** - 支持 AI 订阅、查询、管理等操作
- 🌐 **管理面板** - 基于 AstrBot Plugin Pages 的可视化管理界面，支持订阅、用户、Feed、推送历史、默认订阅设置和 Routes 知识库管理
- 📦 **数据导入导出** - 支持 TOML 格式备份和恢复订阅数据
- 🔄 **失败队列** - 平台连接失败时自动进入队列，恢复后重试推送
- 🤝 **多 BOT 支持** - 单会话多 BOT 去重
- 🔍 **RSSHub 集成** - 支持将 RSSHub Routes 文档同步到 AstrBot 知识库辅助路由检索

---

## 📦 安装

### 方式一：通过 AstrBot 插件市场安装（推荐）

在 AstrBot 管理面板中搜索 `RSSHub` 并安装。

### 方式二：手动安装

1. 克隆本仓库到 AstrBot 的插件目录：
   ```bash
   cd AstrBot/data/plugins
   git clone https://github.com/FlanChanXwO/astrbot_plugin_rsshub.git
   ```

2. 重启 AstrBot 或重载插件

---

## 免费 RSS 源实例（公共可用）

> 以下实例为公共服务，稳定性和可用性会随时间变化，建议优先自建或准备备用地址。

| 名称 | 地址 | 类型 | 说明 |
|------|------|------|------|
| RSSHub 官方 | `https://rsshub.app` | RSSHub 实例 | 默认推荐，覆盖路由广 |
| Feedly | `https://feedly.com/i/subscription/feed%2F<URL 编码后的 RSS 链接>` | 在线阅读器 | 免费版可用于管理订阅 |
| Inoreader | `https://www.inoreader.com` | 在线阅读器 | 免费版可聚合多源 |
| Follow | `https://app.follow.is` | 在线阅读器 | 新一代 RSS 聚合器，支持多端 |

> 提示：在本插件中通常将 `rsshub_base_url` 默认设置为可用的 RSSHub 实例地址（如 `https://rsshub.app`）。

---

## 🛠️ 配置项

> **注意**：AstrBot 配置页仅保留启动级基础设施配置、Routes 知识库和平台发送策略；订阅默认值请前往 AstrBot 面板的 Plugin Pages 管理。

在 AstrBot 管理面板的「配置」页面，找到 `RSSHub` 插件配置：

### 基础设施配置 (`basic_config`)

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `proxy` | 字符串 | HTTP/SOCKS 代理地址，留空则不使用代理。例如 `http://127.0.0.1:7890` | `""` |
| `rsshub_base_url` | 字符串 | 默认 RSSHub 域名，用于路由检索与订阅链接拼接 | `https://rsshub.app` |
| `timeout` | 整数 | 请求超时（秒），获取 RSS 源时的 HTTP 请求超时时间 | `30` |
| `minimal_interval` | 整数 | 最小监控间隔（分钟），限制命令/Plugin Pages 设置的最小值 | `1` |
| `hash_history_min` | 整数 | 去重历史最小保留数量，避免历史回流重复推送 | `500` |
| `hash_history_multiplier` | 整数 | 去重历史增长倍数，动态扩展历史窗口 | `2` |
| `hash_history_hard_limit` | 整数 | 去重历史硬上限，限制数据库体积与监控开销 | `5000` |
| `tracking_query_params` | 列表 | 链接去重时忽略的查询参数（如 utm_source） | 见配置说明 |
| `failed_queue_capacity` | 整数 | 失败队列容量，0=禁用失败队列 | `50` |
| `failed_queue_max_retries` | 整数 | 失败队列最大重试次数 | `3` |
| `deduplicate_multi_bot` | 布尔值 | 单会话多 BOT 去重，避免重复推送 | `true` |
| `bootstrap_skip_history` | 布尔值 | 首轮是否跳过历史条目，开启后首次仅建立去重历史不推送旧消息 | `true` |
| `debug_payload` | 布尔值 | 调试模式，在消息末尾显示条目详细信息 | `false` |
| `history_entry_limit` | 整数 | 历史条目推送限制，0=不限制 | `0` |
| `download_media_before_send` | 布尔值 | 先下载媒体后发送，Docker 环境下需共享数据卷 | `false` |
| `download_media_timeout` | 整数 | 媒体下载超时（秒），m3u8/HLS 建议 60-180 秒 | `30` |

### RSSHub Routes 知识库 (`route_knowledge`)

用于将 RSSHub Routes Markdown 文档同步到 AstrBot 知识库。`/rsshub_kb_init` 可按 `kb_name` 自动创建空知识库，也可复用已有知识库；向量模型和重排序模型留空时使用当前第一个可用 Provider。

AstrBot 配置页中，`source_mode`、`source_base_url` 和 `fallback_base_url` 使用下拉选项，避免手动输入不兼容的 raw 镜像格式；有限范围的超时、并发和批量参数使用滑块。当前内置来源包括 GitHub Raw 和 `ghfast.top` raw 代理格式，知识库文件来自独立仓库 `FlanChanXwO/rsshub-routes-knowledgebase`。

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `route_knowledge.kb_name` | 字符串 | 同步目标知识库名称 | `RSSHub Routes` |
| `route_knowledge.embedding_provider_id` | 字符串 | 自动创建知识库时使用的向量模型 Provider ID；留空使用第一个可用 Embedding Provider | `""` |
| `route_knowledge.rerank_provider_id` | 字符串 | 自动创建或补齐知识库时使用的重排序模型 Provider ID；留空使用第一个可用 Rerank Provider，无可用 Provider 时关闭重排序 | `""` |
| `route_knowledge.source_mode` | 下拉 | 同步来源模式：`mirror` 使用主地址，`auto` 失败后尝试备用地址，`github` 使用内置 GitHub Raw，`local` 使用本地目录 | `mirror` |
| `route_knowledge.source_base_url` | 下拉 | 包含 `metadata.json`、`index/` 和 `docs/` 的 raw 文件根地址 | GitHub Raw |
| `route_knowledge.fallback_base_url` | 下拉 | `source_mode=auto` 时的备用 raw 文件根地址 | GitHub Raw |
| `route_knowledge.local_source_dir` | 字符串 | `source_mode=local` 时的本地同步目录 | `""` |
| `route_knowledge.timeout` | 滑块整数 | 下载 metadata 和 Markdown 文件的超时时间（秒） | `30` |
| `route_knowledge.batch_size` | 滑块整数 | 传给 AstrBot 知识库上传接口的 batch_size | `32` |
| `route_knowledge.tasks_limit` | 滑块整数 | 传给 AstrBot 知识库上传接口的并发任务数 | `3` |
| `route_knowledge.max_retries` | 滑块整数 | 传给 AstrBot 知识库上传接口的重试次数 | `3` |

### 订阅默认配置（Plugin Pages）

订阅全局默认值不再在 AstrBot 配置页暴露，请在 Plugin Pages 中维护。包括默认监控间隔、通知、发送模式、内容长度、展示策略和媒体展示等。

> 旧配置中的 `global_config` 仍可被运行时读取，避免升级后丢失已有设置。

### FFmpeg 配置 (`ffmpeg`)

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `ffmpeg.video_transcode` | 布尔值 | 视频发送前自动转码为兼容 H264/AAC MP4 | `false` |
| `ffmpeg.video_transcode_timeout` | 整数 | 视频转码超时时间（秒） | `120` |
| `ffmpeg.gif_transcode` | 布尔值 | 无声视频自动转 GIF | `false` |
| `ffmpeg.gif_transcode_timeout` | 整数 | GIF 转码超时时间（秒） | `60` |

### 发送策略配置 (`sender_strategies`)

`sender_strategies.enabled_platforms` 现在是平台多选列表，默认启用 `telegram`、`aiocqhttp`、`qq_official`、`weixin_oc`。未选中的平台会回退到默认发送器。

> 兼容说明：旧版 `sender_strategies.telegram = true` 这类布尔对象配置仍可读取；保存后会写回 `sender_strategies.enabled_platforms`，保留 `sender_strategies` 容器以便后续扩展平台专属配置。

## 📝 使用方法

### 基础命令

所有命令均支持中英文别名，例如 `/sub` 和 `/订阅` 等价：

| 命令                                     | 中文别名 | 说明 |
|----------------------------------------|---------|------|
| `/sub <RSS 链接> [链接2...]`               | `/订阅` | 新增订阅，支持批量订阅多个 RSS 源 |
| `/sub_state <ID> on/off`               | `/订阅状态` | 快速启停订阅推送 |
| `/unsub <ID/URL...>`                   | `/取消订阅` | 取消订阅，支持批量（ID 或 URL） |
| `/unsub_all [global]`                  | `/取消全部订阅` | 删除订阅；默认仅清除当前会话，`global` 清除所有会话（需管理员） |
| `/sub_list [page] [page_size]` | `/订阅列表` | 查看当前会话订阅列表（分页） |
| `/sub_export [all]`                    | `/导出订阅` | 导出订阅到 TOML 文件，默认当前会话，`all`=所有订阅（管理员） |
| `/sub_import [文件路径]`                   | `/导入订阅` | 从 TOML 文件导入订阅；也可直接上传 TOML 文件进行导入 |
| `/activate_subs`                       | `/enable_subs`, `/启用全部订阅` | 启用当前会话所有订阅 |
| `/deactivate_subs`                     | `/disable_subs`, `/禁用全部订阅` | 禁用当前会话所有订阅 |
| `/sub_status`                          | `/推送状态`, `/任务状态` | 查看当前会话推送任务（running + queued，含 job_id/feed 信息） |
| `/sub_stop [job_id/feed_id/all]`       | `/停止RSS`, `/停止推送` | 停止推送任务：不带参数停止当前 running 任务；可按 job_id/feed_id 精确停止；`all` 停止当前会话全部任务 |
| `/rsshub_kb_init`                      | - | 管理员初始化 RSSHub Routes 知识库 |
| `/rsshub_kb_sync`                      | - | 管理员启动 RSSHub Routes 知识库同步任务 |
| `/rsshub_kb_status`                    | - | 查看 RSSHub Routes 知识库状态 |
| `/rsshub_kb_task`                      | - | 查看最近一次 Routes KB 同步任务进度 |

**布尔值格式支持**：所有命令中的布尔值参数支持以下格式：`true`/`false`, `yes`/`no`, `y`/`n`, `1`/`0`, `on`/`off`, `enable`/`disable`

### 订阅设置

| 命令 | 中文别名 | 说明 |
|------|---------|------|
| `/sub_profile set sub <订阅 ID> <选项> <值>` | `/订阅配置 设置 sub ...` | 设置订阅级选项 |
| `/sub_profile set user <选项> <值>` | `/订阅配置 设置 user ...` | 设置用户默认选项 |
| `/sub_profile get user [选项]` | `/订阅配置 获取 user ...` | 查看用户配置（无参数显示所有） |
| `/sub_session set [key] [value]` | `/会话设置 设置` | 设置会话级默认项 |
| `/sub_session get [key]` | `/会话设置 获取` | 查看会话默认项（无参数显示所有） |

### 配置继承架构

订阅设置采用三层配置继承体系：

1. **订阅级配置** (`/sub_profile set sub ...`): 字段值为 `-100` 时继承用户级配置，其他值直接作为订阅配置生效
2. **用户级配置** (`/sub_profile set user ...`): 字段值为 `-100` 时继承全局配置，其他值作为用户默认配置生效
3. **全局配置**: AstrBot JSON 配置（默认），新用户开箱即用

`rsshub_sub` 与 `rsshub_user` 不再使用 `use_sub_config` / `use_user_config` 开关列；继承完全由具体配置项的 `-100` 值表达。旧翻译字段也已从这两张表中移除。

**示例**：
```bash
# 让订阅继承用户/全局发送模式
/sub_profile set sub 1 send_mode -100

# 让用户发送模式继承全局配置
/sub_profile set user send_mode -100

# 为订阅设置 AI 内容处理提示词
/sub_profile set sub 1 ai_prompt 请总结为三条要点

# 查看配置来源
/sub_profile get user  # 查看用户配置
/sub_session get       # 查看会话默认
```

### 管理命令

| 命令 | 中文别名 | 说明 |
|------|---------|------|
| `/sub_test <目标> [起始] [结束]` | `/测试订阅` | 管理员测试推送。目标可以是订阅 ID 或 RSS URL；条目编号从 1 开始（1=最新） |
| `/rsshelp` | `/RSS 帮助` | 查看帮助图片 |

> `rsshelp` 图片由 `scripts/generate_rsshelp_image.py` 根据 `main.py` 命令注释自动生成（HTML 模板：`assets/help/rsshelp_template.html`）。
>
> 当命令变更后可手动刷新帮助图：
> ```bash
> python scripts/generate_rsshelp_image.py
> ```

**`/sub_test` 命令示例：**

| 命令 | 说明 |
|------|------|
| `/sub_test 5` | 测试订阅ID=5，推送条目1（最新） |
| `/sub_test 5 1 3` | 测试订阅ID=5，推送条目1、2、3 |
| `/sub_test https://example.com/rss.xml 2` | 测试URL，只推送条目2 |
| `/sub_test https://example.com/rss.xml 1 5` | 测试URL，推送条目1-5 |

> **说明：** 使用URL测试时，将使用全局配置进行推送。

### 订阅选项说明

**订阅级选项（通过 `/sub_profile set sub ...` 设置）：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `state` | 0/1 | 推送状态：0=禁用, 1=启用 |
| `notify` | 0/1 | 是否通知 |
| `send_mode` | -1/0/2 | -1(仅链接)/0(自动)/2(直接消息) |
| `ai_prompt` | 字符串 | AI 内容处理提示词 |
| `length_limit` | 正整数 | 0 表示不限制 |
| `link_preview` | 0/1 | 链接预览 |
| `display_author` | -1~1 | 显示作者 |
| `display_via` | -2~-1/0/1 | 显示来源 |
| `display_title` | -1~1 | 显示标题 |
| `display_entry_tags` | -1~1 | 显示标签 |
| `style` | 0/1 | 样式 (RSStT/flowerss) |
| `display_media` | -1/0 | 显示媒体 |
| `interval` | 正整数 | 监控间隔（分钟，默认 5） |
| `title` | 字符串 | 订阅标题 |
| `tags` | 字符串 | 标签 |

---

## 🤖 LLM 工具

本插件为 AI 提供以下工具函数：

- `rss_subscribe` - 订阅 RSS 源
- `rss_unsubscribe` - 取消订阅
- `rss_unsubscribe_all` - 取消所有订阅
- `rss_list_subscriptions` - 列出订阅
- `rss_set_subscription_option` - 设置订阅选项
- `rss_set_user_default_option` - 设置用户默认选项
- `rss_set_session_default_option` - 设置会话默认选项
- `rss_get_session_defaults` - 获取会话默认配置
- `rss_list_push_history` - 查询当前会话推送历史（JSON）
- `rss_push_xml_entry` - 解析 XML/HTML 标签内容并推送到当前会话

在 AstrBot 的 LLM 配置中开启工具调用即可使用。

> RSSHub 路由检索后续走 AstrBot 知识库和 route skill；插件不再提供 route 搜索 LLM tool。
>
> `rss_push_xml_entry` 是面向 AI agent 的即时推送工具，不使用订阅 `sub_id`，也不读取订阅默认配置。它会：
> - 对输入 XML 做格式校验，拒绝坏格式、DOCTYPE/ENTITY 和超大输入
> - 将标签内容解析为正文 + 媒体组件
> - 使用 `source_key + user_id + target_session + entry_guid` 做成功态幂等去重
> - 写入推送历史并复用现有失败重试链路
> - 在媒体发送失败时，把原始媒体链接保留到失败历史和回退文本中
> - 为 XML 即时推送历史额外保存 `raw_xml` 以便审计和后续排障

---

## 🏗️ 项目架构 (v2.0.0+)

本项目采用 **领域驱动设计 (DDD)** 分层架构，代码组织清晰、可维护性强。

### 架构分层

```
src/
├── domain/           # 领域层 - 核心业务逻辑
│   ├── entities/     # 领域实体 (Feed, Subscription, User)
│   ├── value_objects/# 值对象 (Entry, Settings)
│   └── repositories/ # 仓库接口定义
├── application/      # 应用层 - 用例编排
│   ├── commands/     # 命令处理 (CQRS)
│   ├── dto/          # 数据传输对象
│   └── services/     # 应用服务
├── infrastructure/   # 基础设施层 - 技术实现
│   ├── config/       # 配置管理
│   ├── messaging/    # 消息发送
│   ├── persistence/  # 数据持久化
│   ├── fetcher/      # RSS 拉取与解析
│   ├── pipeline/     # 消息链格式化
│   ├── schedule/     # 调度服务
│   ├── utils/        # 工具函数
└── __init__.py       # 统一导出
```

### 关键设计原则

1. **依赖倒置**: 领域层不依赖其他层，基础设施层实现领域层定义的接口
2. **命令模式**: 每个业务用例封装为独立的命令类，便于测试和扩展
3. **仓库模式**: 数据访问抽象，支持灵活的存储实现
4. **单例管理**: 关键服务（数据库、配置、调度）采用单例模式
5. **类型安全**: 全面使用 Python 类型注解，增强代码健壮性

---

## 🌐 管理界面

本项目管理界面使用 **AstrBot Plugin Pages**（`pages/dashboard`），通过 AstrBot 面板访问。  
后端接口由 `WebApiHandler` 注册到 `/{plugin_name}/...` 路径下（当前为 `/astrbot_plugin_rsshub/...`）。

管理页包含已有订阅管理、用户/Feed 列表、推送历史、默认订阅设置和 RSSHub Routes 知识库同步。WebUI 不创建新订阅，也不提供订阅导入/导出入口；新增、导入和导出订阅请使用聊天命令或 AI agent。用户状态仅保留「用户」和「已封禁」两种；窄屏下订阅表格会切换为卡片式布局，推送历史筛选、分页和知识库状态区域会自动换行，避免按钮或长文本重叠。
订阅列表采用前端分页，分页控件放在列表上方；页面滚动被限制在列表/配置容器内部，避免切换标签页时整页布局抖动。默认订阅设置统一使用底部保存按钮，不再使用遮挡表单的悬浮按钮。

## 🧩 解析与推送兼容性

- RSS 解析优先读取 `content` 结构化正文，并兼容 `content:encoded` / `content_encoded` 字段，适配 Juya AI Daily 等完整正文位于 `content:encoded` 的源。
- HTML `<video>`、`<audio>` 会作为结构化媒体传入发送器，正文中不会残留 `[视频]` / `[音频]` 占位；RSSHub 常见的 `?url=<encoded media>` 包装链接也会参与媒体类型推断。
- OneBot / NapCat 合并转发若因本地媒体文件失败而降级为纯文本，回退文本会附带本次消息的全部原始媒体链接；失败记录写入推送历史后，WebUI 和失败重试也能继续看到这些链接。
- 推送历史中的失败原因会按 512 字符上限统一截断；旧数据库里遗留的超长失败原因也会在读取时自动清洗，避免 `/push-history` 接口和定时重试任务因脏数据崩溃。

---

## 📄 开源协议

本项目基于 [AGPL](LICENSE) 协议开源。

## 致谢

- [RSS-to-Telegram-Bot：关心你的阅读体验的 Telegram RSS 机器人](https://github.com/Rongronggg9/RSS-to-Telegram-Bot)
- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [feedparser：](https://github.com/kurtmckee/feedparser)
