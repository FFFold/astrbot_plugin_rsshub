---
name: rsshub-agent-tools
description: 使用 astrbot_plugin_rsshub 提供的 LLM tools 完成 RSS subscription、RSSHub route lookup、订阅配置、user/session defaults、handlers 管理、AI filter / AI transform、push history 排查、raw_xml / XML/HTML 直推，以及无 RSS 网页的 future_task 定时采集。只要用户提到订阅、RSSHub route、feed URL、handlers、raw_xml、push history、AI 内容过滤/总结、future_task、astr_kb_search，或希望 agent 帮忙实际完成配置与推送操作时，就应优先使用这个 skill，而不是只给文字建议。
---

# RSSHub Agent Tools

这个 skill 用来指导 agent 正确使用本插件暴露的 LLM tools，而不是凭空描述插件能力。

目标：

- 真正帮用户完成 RSS 订阅和配置动作
- 在“总结 / 过滤 / 改写内容”场景下，优先落到 handlers 配置，而不是一次性聊天回答
- 在修改配置前先确认当前状态，尽量减少误改
- 根据作用域选择正确工具：订阅级、用户级、会话级各不相同
- 在没有现成 RSS 源时，知道何时改用 AstrBot 知识库工具或未来任务工具，而不是硬套 `rss_subscribe`

## 何时使用

在这些场景必须优先考虑本 skill：

- 用户要订阅、取消订阅、批量订阅、查看订阅列表
- 用户要查 RSSHub 路由、找 route、拼订阅链接、确认某个站点有没有现成 RSSHub 路由
- 用户要修改某个订阅的行为，例如 `send_mode`、`display_media`、`length_limit`
- 用户要修改自己的默认配置，或修改当前会话的新订阅默认值
- 用户要启用 AI 内容过滤、AI 改写、XML 清洗
- 用户要查看 handlers schema、读取 handlers、写入 handlers
- 用户要查看当前会话的推送历史，尤其是排查 handler trace、失败原因、raw_xml
- 用户要把 XML/HTML 片段解析后直接推送到当前会话
- 用户要让 AI 帮忙长期采集一个没有 RSS 源的网页，并定时整理后推送

这些场景不要误用本 skill：

- 不要直接臆造 RSSHub 路由、参数名或 URI；涉及 route 查询时，应先走 AstrBot 知识库工具查询 RSSHub Routes 知识库
- 不要把 AI 过滤/总结需求只回答成“你可以这样配置”，如果用户是在要求代操作，就应直接调用 handlers 相关工具
- 不要把订阅级配置误写成会话默认配置，也不要把会话默认配置误写成用户默认配置
- 当用户要求“帮我改配置/帮我设置”但没有明确作用域时，先追问是订阅级、用户默认，还是会话默认，再决定调用哪个配置工具
- 当用户根本没提 RSS，只是说“订阅这个”“盯这个链接”“跟踪这个网页”，且给出的链接看起来不像 RSS/XML/feed URL 时，不要直接调用插件工具；先询问用户是否希望借助 RSS 插件能力，以及是否要帮忙查找可用的 RSSHub route / RSS 源

## 工具地图

### 先认清工具边界

下面这些工具经常会一起用，但职责不同，不要混用：

| 工具 | 来源 | 适合做什么 | 不适合做什么 | 典型产出 |
| --- | --- | --- | --- | --- |
| `astr_kb_search` | AstrBot 知识库工具 | 查询 RSSHub Routes 知识库，确认 route、URI、参数、示例 | 不负责真正订阅，不负责发送消息 | 路由文档、参数说明、可用 URI |
| `future_task` | 未来任务创建工具 | 为“没有 RSS 源的网页”创建定时采集/整理任务 | 不直接保存为插件订阅，不直接替代 `rss_subscribe` | 一个定时执行的采集任务 |
| `rss_subscribe` | 本插件 LLM tool | 订阅已有 RSS/RSSHub 路由 | 不负责抓普通网页，不负责猜 route | 新增订阅记录 |
| `rss_push_xml_entry` | 本插件 LLM tool | 把整理好的 RSS/XML/HTML 条目发到当前会话 | 不负责长期调度抓取网页 | 一次即时推送或 dry run 结果 |

### 订阅与查询

- RSSHub route / 路由查询
  这类请求本 skill 只负责规定工作流，不直接替代知识库搜索能力。
  当用户问“这个站点怎么订阅”“有没有 RSSHub 路由”“帮我找某个 RSSHub route”“帮我拼订阅链接”时：
  1. 先使用 `astr_kb_search` 查询 RSSHub Routes 知识库，而不是猜 route
  2. 根据查到的文档整理 URI、参数说明、示例链接
  3. 用户明确要求实际订阅时，再调用 `rss_subscribe`
  4. 如果知识库没有查到，不要编造不存在的 route，应明确说明“当前知识库未命中”

- 无 RSS 源网页采集
  当用户问“这个网页没有 RSS，帮我长期盯着”“定时抓这个页面的更新”“帮我整理成 RSS/XML 再推送”时：
  1. 不要直接调用 `rss_subscribe`，因为目标并不是现成 RSS 源
  2. 优先判断是否已有 RSSHub route；有的话先走 `astr_kb_search`
  3. 如果确认没有现成 RSS/RSSHub 路由，再使用 `future_task` 创建定时任务
  4. 未来任务的目标应是：定时抓取网页 -> 提取更新 -> 整理为 RSS item / XML 兼容结构
  5. 采集结果需要即时发消息时，再调用 `rss_push_xml_entry`
  6. 如果未来要沉淀成真正订阅源，再考虑把采集结果接到独立 RSS 输出链路，而不是伪装成普通 `rss_subscribe`

- `rss_subscribe`
  适合新增订阅。优先传 `uri`，例如 `/twitter/user/BlueArchive_JP`；工具会自动拼接插件默认 RSSHub 基址。
  只有在用户明确给出完整 RSS URL 或非 RSSHub URL 时才传 `url`。

- `rss_unsubscribe`
  适合按订阅 ID 或 URL 取消订阅。支持空格分隔多个目标。

- `rss_unsubscribe_all`
  适合清空当前会话全部订阅。`scope=global` 只有在用户明确要求全局删除且具备权限时才使用。

- `rss_list_subscriptions`
  适合先查当前会话有哪些订阅，尤其在修改订阅前先拿到 `sub_id`。

### 配置修改

- `rss_set_subscription_option`
  修改单个订阅。适合“只改这一个订阅”的场景。

- `rss_set_user_default_option`
  修改用户默认配置。适合“我之后所有订阅默认都这样”的场景。

- `rss_set_session_default_option`
  修改当前会话默认配置。适合“这个群 / 这个会话里以后新建订阅默认这样”的场景。

- `rss_get_session_defaults`
  读取当前会话默认配置。修改会话级配置前优先先看一眼。

### 内容处理与 handlers

- `rss_list_handlers`
  列出内置 handler 及 schema。只要要写 handlers，最好先调一次，确认字段名和可选项。

- `rss_get_handlers`
  读取现有 handlers。`scope=user` 读用户默认 handlers，`scope=subscription` 读某个订阅的 handlers。

- `rss_set_subscription_handlers`
  写订阅级 handlers。适合对单个订阅开启 `xml_parse`、`ai_filter`、`ai_transform`。

- `rss_set_user_handlers`
  写用户默认 handlers。适合把某套内容处理链作为默认策略给所有继承订阅使用。

### 历史与直推

- `rss_list_push_history`
  查看当前会话推送历史。适合排查失败、确认 `handler_trace`、查看 `raw_xml`、确认 `skipped` 原因。

- `rss_push_xml_entry`
  将 XML/HTML 片段解析成消息组件并推送。适合 agent 代发结构化内容，支持 `dry_run` 先预览。

## 推荐工作流

### 1. 订阅类任务

先做一个入口判断：

- 用户明确提到 RSS、RSSHub、feed、route、XML、订阅源：可以直接进入本 skill 工作流
- 用户只说“订阅 xxx”“跟踪 xxx”“盯这个网页”，但没提 RSS，且链接不像 RSS/XML：
  1. 先不要直接 `rss_subscribe`
  2. 先询问用户是否希望使用 RSS 插件能力
  3. 如用户同意，再帮他检查是否存在 RSS 源或 RSSHub route
  4. 只有确认要走 RSS 能力后，才进入 `astr_kb_search` / `rss_subscribe` / `future_task` 流程

如果用户说“帮我找某个 RSSHub 路由并订阅”：

1. 先用 `astr_kb_search` 查询 RSSHub Routes 知识库
2. 只根据查到的 route 文档整理出 URI 或完整订阅链接
3. 用户确认或明确要求订阅后，再调用 `rss_subscribe`
4. 优先把 route 作为 `uri` 传给 `rss_subscribe`

如果用户说“帮我订阅这个 RSSHub 路由”：

1. 直接调用 `rss_subscribe`
2. 优先用 `uri`
3. 成功后，只有在用户继续要求配置时，再进入配置工具链

如果用户说“帮我退掉某个订阅，但我不知道 ID”：

1. 先调用 `rss_list_subscriptions`
2. 根据结果定位目标
3. 再调用 `rss_unsubscribe`

如果用户说“这个网页没有 RSS，但我想每天看更新并推送给我”：

1. 先判断是否可能存在 RSSHub route
2. 如有可能，先调用 `astr_kb_search`
3. 如果知识库确认没有合适 route，再使用 `future_task`
4. 在任务说明里明确采集频率、目标网页、提取字段、输出格式
5. 如果任务产出需要直接推送到当前会话，约定输出为 RSS item / XML 兼容文本，再交给 `rss_push_xml_entry`

### 2. 修改推送配置

先判断用户想改的是哪一层：

- “这个订阅单独这样” -> `rss_set_subscription_option`
- “我默认都这样” -> `rss_set_user_default_option`
- “这个群里以后默认这样” -> `rss_set_session_default_option`

如果用户没有说清楚作用域，不要替他猜。先问清楚：

- 是只修改某一个订阅
- 还是修改用户默认配置
- 还是修改当前会话里未来新订阅的默认配置

只有作用域明确后，才执行对应工具调用。

优先记这张表，不要凭感觉猜值：

| 配置项 | 可取值 | 语义 | 常用作用域 |
| --- | --- | --- | --- |
| `interval` | `1` 到 `60` | 监控间隔，单位分钟 | 订阅 / 用户 / 会话 |
| `notify` | `0` / `1` | `0=禁用推送`，`1=启用推送` | 订阅 / 用户 / 会话 |
| `send_mode` | `-1` / `0` / `1` | `-1=仅链接`，`0=自动`，`1=直接发送` | 订阅 / 用户 / 会话 |
| `length_limit` | `0` 到 `10000` | 正文长度限制，`0` 表示不限制 | 订阅 / 用户 / 会话 |
| `display_author` | `-1` / `0` / `1` | `-1=禁用`，`0=自动`，`1=强制显示` | 订阅 / 用户 / 会话 |
| `display_via` | `-2` / `-1` / `0` / `1` | `-2=完全禁用`，`-1=仅链接`，`0=自动`，`1=强制显示` | 订阅 / 用户 / 会话 |
| `display_title` | `-1` / `0` / `1` | `-1=禁用`，`0=自动`，`1=强制显示` | 订阅 / 用户 / 会话 |
| `display_entry_tags` | `-1` / `0` / `1` | `-1=禁用`，`0=自动/继承`，`1=启用` | 订阅 / 用户 / 会话 |
| `style` | `0` / `1` | `0=RSStT`，`1=flowerss` | 订阅 / 用户 / 会话 |
| `display_media` | `-1` / `0` / `1` | `-1=禁用`，`0=自动/继承`，`1=启用` | 订阅 / 用户 / 会话 |

这些值里，用户级和订阅级很多字段支持 `-100`，表示继承上层默认值。会话默认配置通常直接写实际值，不要优先写 `-100`。

额外注意：

| 配置项 | 说明 |
| --- | --- |
| `handlers` | 只能写 JSON 数组字符串，不是普通数字 |
| `handlers_mode` | 只支持 `inherit` / `override` / `disabled`，这是订阅级专用 |
| 已移除项 | 不要再写 `ai_prompt`、`translate`、`translate_target_lang`、`use_sub_config`、`use_user_config` |

### 3. AI 内容过滤 / 总结 / 改写

如果用户说：

- “帮我过滤掉广告、抽奖”
- “帮我把正文总结一下再发”
- “帮我把 HTML/XML 清洗一下”

不要把这理解成一次性回答任务。优先把它落成 handlers 配置。

推荐顺序：

1. 调用 `rss_list_handlers`
2. 调用 `rss_get_handlers` 看当前已有配置
3. 根据场景生成新的 handlers JSON
4. 写入 `rss_set_subscription_handlers` 或 `rss_set_user_handlers`

推荐默认链：

```json
[
  {
    "id": "builtin.xml_parse.default",
    "type": "builtin",
    "name": "xml_parse",
    "status": 1,
    "config": {}
  },
  {
    "id": "builtin.ai_filter.default",
    "type": "builtin",
    "name": "ai_filter",
    "status": 1,
    "config": {
      "prompt": "过滤掉广告、抽奖、无信息量转发",
      "input_scope": "both",
      "reason_max_length": 120
    }
  },
  {
    "id": "builtin.ai_transform.default",
    "type": "builtin",
    "name": "ai_transform",
    "status": 1,
    "config": {
      "prompt": "总结正文，保留关键信息，不要编造"
    }
  }
]
```

handlers 作用域选择：

- 用户想“以后默认都这样” -> `rss_set_user_handlers`
- 用户想“只有这个订阅这样” -> `rss_set_subscription_handlers`

订阅级 `mode` 选择：

- `override`：用订阅自己的 handlers 覆盖用户默认链
- `inherit`：让该订阅回退到用户默认 handlers
- `disabled`：该订阅完全禁用 handlers

### 4. 排查推送异常

如果用户说“为什么这条没发出来”“为什么被过滤了”“看一下 XML/处理结果”：

1. 调用 `rss_list_push_history`
2. 关注这些字段：
   - `status`
   - `fail_reason`
   - `handler_trace`
   - `raw_xml`
   - `media_urls`
3. 如果和 handlers 有关，再调用 `rss_get_handlers`

### 5. XML/HTML 直推

如果用户提供了一段 XML/HTML，希望直接解析并发到当前会话：

1. 优先调用 `rss_push_xml_entry`
2. 如果内容复杂或用户先要确认效果，先用 `dry_run=true`
3. dry run 没问题后，再正式发送

## RSS 2.0 / XML 构造约束

当 agent 需要为 `rss_push_xml_entry` 准备 XML，或需要为 `future_task` 约束“产出可被 RSS 插件消费的内容”时，默认遵守 RSS 2.0 / RSS item 兼容结构，不要随意臆造字段。

### 最小可用结构

- 最推荐：提供单个 `<item>...</item>` 或 `<entry>...</entry>` 片段，作为一次消息条目
- 如果要描述完整 RSS 2.0 文档，应使用 `<rss version="2.0"><channel>...</channel></rss>`
- 对本插件即时推送而言，`rss_push_xml_entry` 最终消费的是“单条 entry/item 的正文片段”，不是必须塞完整 feed 文档

### 字段优先级

构造内容时优先保证这些字段真实、可解析：

| 字段 | 建议位置 | 用途 | 要求 |
| --- | --- | --- | --- |
| 标题 | tool 参数 `title` | 推送标题 | 必填，优先放在 tool 参数，不要只藏在 XML 里 |
| 正文 | XML body / `<description>` / `<content:encoded>` / `<content>` | 推送正文 | 应为真实正文，不要只放占位文本 |
| 链接 | tool 参数 `link` 或 XML 内 `<link>` | `via` 尾巴 / 跳转链接 | 应为完整 `http(s)` URL |
| 作者 | tool 参数 `author` 或 XML 内 `<author>` | 尾巴作者信息 | 可选，缺失时不要编造 |
| 来源标题 | tool 参数 `feed_title` 或 channel title | `via` 来源名 | 可选，缺失时不要编造 |
| GUID | tool 参数 `entry_guid` 或 `<guid>` | 去重 / 幂等 | 建议稳定，能唯一标识该条目 |
| 时间 | `<pubDate>` / `<updated>` | 审计与排序辅助 | 可选，但有就用真实时间 |

### RSS 2.0 规范要点

- RSS 2.0 日期优先使用 RFC 822 / RFC 2822 风格，例如 `Thu, 22 May 2026 12:34:56 GMT`
- `<guid>` 应稳定；若不是永久链接，不要假设 `isPermaLink=true`
- `<description>` 允许 HTML，但应是“条目真实正文”，不要把调试说明、工具参数说明混进去
- 媒体资源应使用真实 URL，可放在 HTML 的 `<img>` / `<video>` / `<audio>`，或 enclosure 类字段；不要伪造本地路径
- 如果正文没有作者、来源、链接，就保持缺失；不要为了“看起来完整”编造占位值

### agent 构造时的硬约束

- 不要输出不闭合标签、半截 XML、混乱命名空间
- 不要把“整个网页原始 HTML”直接塞进去当 RSS 正文，除非用户明确要求原样推送
- 不要构造假的 `guid`、假的发布时间、假的作者名
- 不要把参数说明文本、思考过程、JSON 解释混进 XML 正文
- 如果用户给的是普通网页采集任务，应在 `future_task` 里明确要求产出“RSS 2.0 item-compatible XML”，至少包含标题、正文、链接三要素

### 推荐模板

单条 item 兼容片段：

```xml
<item>
  <title>条目标题</title>
  <link>https://example.com/post/123</link>
  <guid isPermaLink="false">example-post-123</guid>
  <pubDate>Thu, 22 May 2026 12:34:56 GMT</pubDate>
  <author>作者名</author>
  <description><![CDATA[
    正文文本<br />
    <img src="https://example.com/image.jpg" />
  ]]></description>
</item>
```

完整 RSS 2.0 文档模板：

```xml
<rss version="2.0">
  <channel>
    <title>Feed Title</title>
    <link>https://example.com</link>
    <description>Feed description</description>
    <item>
      <title>条目标题</title>
      <link>https://example.com/post/123</link>
      <guid isPermaLink="false">example-post-123</guid>
      <pubDate>Thu, 22 May 2026 12:34:56 GMT</pubDate>
      <description><![CDATA[正文]]></description>
    </item>
  </channel>
</rss>
```

### 6. 无 RSS 源网页的长期采集

当用户的真实需求不是“订阅一个现成 feed”，而是“盯一个普通网页并持续推送”，按下面顺序：

1. 先问自己：这是 route 查询问题，还是网页采集问题
2. 能走 RSSHub route 的，优先 `astr_kb_search` -> `rss_subscribe`
3. 不能走 RSSHub route 的，使用 `future_task`
4. `future_task` 的任务描述应至少写清：
   - 目标网页 URL
   - 抓取频率
   - 需要提取的字段，例如标题、正文、发布时间、图片、视频链接
   - 输出约束：整理成 RSS item / XML 兼容结构
   - 推送方式：必要时调用 `rss_push_xml_entry`
5. 不要把“未来任务”误说成插件订阅本身；它是外部调度与采集能力，插件负责解析、处理和发送

## handlers 写入规则

写 handlers 时遵循这些规则：

- `handlers_json` 必须是 JSON 数组字符串
- 第一版实际执行的只有 `builtin`
- 未知或 `external` handler 可以保存，但运行时会跳过

不要随意编造 handler 名称或字段。先用 `rss_list_handlers` 获取 schema，再生成 JSON。

每个 handler 项目的结构：

| 字段 | 类型 | 可取值 / 规则 |
| --- | --- | --- |
| `id` | string | 唯一标识，例如 `builtin.ai_filter.default` |
| `type` | string | 当前推荐只用 `builtin`；`external` 可保存但不会执行 |
| `name` | string | `xml_parse` / `ai_filter` / `ai_transform` |
| `status` | int | `1=启用`，`0=禁用`，`-100=跟随该 handler 默认状态` |
| `config` | object | handler 私有配置 |

内置 handler 一览：

| `name` | 作用 | `config` 字段 | 可取值 |
| --- | --- | --- | --- |
| `xml_parse` | 清洗 XML/HTML，提取纯文本 | 无 | `{}` |
| `ai_filter` | 用 AI 判断是否允许推送 | `prompt`、`input_scope`、`reason_max_length` | `prompt` 为非空文本；`input_scope` 只能是 `text` / `raw_xml` / `both`；`reason_max_length` 为正整数，常用 `120` |
| `ai_transform` | 用 AI 改写标题/摘要/正文 | `prompt` | 非空文本 |

推荐让 agent 生成 handlers 时遵循：

| 场景 | 推荐链 |
| --- | --- |
| HTML/XML 内容比较脏 | `xml_parse` |
| 先过滤再发送 | `xml_parse -> ai_filter` |
| 清洗后再总结/改写 | `xml_parse -> ai_transform` |
| 先过滤再改写 | `xml_parse -> ai_filter -> ai_transform` |

## 谨慎事项

- 不要在没有 `sub_id` 的情况下盲目修改订阅；先查列表
- 不要为了回答 route 问题就即时注入 system prompt；route 查询要求应由本 skill 显式约束
- 不要绕过 `astr_kb_search` 直接猜 RSSHub route；route、参数、路径段都必须基于知识库结果或用户给定链接
- 不要在作用域不明确时直接改配置；先确认是 subscription / user default / session default
- 不要在用户没提 RSS 且链接明显不是 feed/RSS/XML 时擅自启用本插件能力；先确认是否需要帮他查 RSS 源或 RSSHub route
- 不要把普通网页采集误当成 `rss_subscribe`；没有现成 RSS 源时，应优先考虑 `future_task`
- 不要把“帮我总结这类内容”只做成一次性回答，除非用户明确说只是临时分析
- 不要直接假设用户要改用户默认配置；很多场景其实是订阅级配置
- 不要把 `handlers_mode=disabled` 和 `handlers=[]` 混为一谈
- 不要把 `uri` 和完整 URL 混用到错误字段；RSSHub 路由优先放 `uri`
- 不要恢复已移除配置项，例如 `ai_prompt`、`translate`、`use_sub_config`

## 操作模板

### 帮用户订阅 RSSHub 路由

1. 如 route 未确认，先 `astr_kb_search`
2. 调用 `rss_subscribe(uri="/twitter/user/BlueArchive_JP")`
3. 向用户汇报订阅结果

### 帮用户处理没有 RSS 的网页

1. 先确认该网页没有现成 RSS / RSSHub route
2. 如需确认 route，先 `astr_kb_search`
3. 使用 `future_task` 创建周期采集任务
4. 在任务说明中要求产出 RSS item / XML 兼容内容
5. 需要即时发送时，再配合 `rss_push_xml_entry`

### 把采集结果直接发到当前会话

1. 准备符合 RSS item / XML 兼容结构的内容
2. 先 `rss_push_xml_entry(..., dry_run=true)`
3. 确认无误后正式发送

### 给某个订阅加 AI 过滤

1. `rss_list_handlers`
2. `rss_get_handlers(scope="subscription", sub_id="<ID>")`
3. 生成 handlers JSON
4. `rss_set_subscription_handlers(sub_id="<ID>", handlers_json="...", mode="override")`

### 把“以后默认总结”设成用户级

1. `rss_list_handlers`
2. `rss_get_handlers(scope="user")`
3. 生成带 `ai_transform` 的 handlers JSON
4. `rss_set_user_handlers(handlers_json="...")`

### 查看某个会话最近推送记录

1. `rss_list_push_history(page="1", page_size="20")`
2. 读取 `status` / `fail_reason` / `handler_trace` / `raw_xml`

## 对用户的输出风格

调用完工具后，向用户汇报时应：

- 直接说结果，不复读整段 JSON
- 如果做了配置修改，明确说明是订阅级、用户级还是会话级
- 如果写了 handlers，说明启用了哪些 handler、它们大致做什么
- 如果失败，优先转述具体错误，而不是笼统说“未知错误”
