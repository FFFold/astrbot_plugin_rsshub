# 项目结构

## 目录布局

```
astrbot_plugin_rsshub/
├── main.py                          # 接口层：Star 子类，@filter.command 注册
├── metadata.yaml                    # 插件元数据
├── _conf_schema.json                # AstrBot 配置面板 schema
├── requirements.txt                 # 依赖
│
├── src/
│   ├── __init__.py                  # PLUGIN_DIR 常量
│   │
│   ├── domain/                      # 领域层 - 纯业务规则
│   │   ├── entities/                # Feed, Subscription, User, PushHistory
│   │   ├── value_objects/           # FeedUrl 等
│   │   ├── repositories/            # 仓库接口 (Protocol)
│   │   ├── services/                # ContentFilterService, FeedDiscoveryService
│   │   ├── constants.py
│   │   └── exceptions.py
│   │
│   ├── application/                 # 应用层 - 用例编排
│   │   ├── commands/                # (CQRS 写) SubscribeFeedCommand 等 12 个
│   │   ├── queries/                 # (CQRS 读) GetFeedListQuery 等 4 个
│   │   ├── dto/                     # CommandResult, FeedDTO, ItemDTO 等
│   │   └── services/                # FeedSyncService, NotificationDispatcher
│   │
│   └── infrastructure/              # 基础设施层 - 技术实现
│       ├── fetcher/                 # 数据采集 (was rss/)
│       │   ├── http.py              # HttpFetcher: 通用 HTTP GET + session 管理
│       │   └── rss/                 # RSS 数据源子包
│       │       ├── __init__.py      # RSSFeedFetcher extends HttpFetcher
│       │       ├── parser.py        # EntryParsed / Enclosure / RSSParser
│       │       └── discoverer.py    # FeedDiscoverer (HTML→Feed URL)
│       │
│       ├── pipeline/                # 内容处理管线
│       │   ├── __init__.py
│       │   └── normalizer.py        # 文本/标识符/路径/配置值标准化
│       │
│       ├── persistence/             # SQLite + SQLModel
│       │   ├── database.py          # DatabaseManager
│       │   ├── models.py            # ORM 模型
│       │   ├── feed_repository_impl.py
│       │   ├── subscription_repository_impl.py
│       │   ├── user_repository_impl.py
│       │   ├── push_history_repository_impl.py
│       │   ├── deduplication_service.py
│       │   └── migrations/
│       │
│       ├── messaging/               # 消息推送
│       │   ├── event_bus.py         # 事件总线
│       │   ├── plugin_manager.py    # 扩展系统
│       │   ├── notification_service.py # 调度器→分发器桥接
│       │   ├── senders/             # 平台发送器策略
│       │   │   ├── base_sender.py
│       │   │   ├── factory.py
│       │   │   ├── onebot_sender.py
│       │   │   ├── telegram_sender.py
│       │   │   ├── qq_official_sender.py
│       │   │   ├── wechat_sender.py
│       │   │   └── types.py
│       │   └── formatters/          # 消息格式化器
│       │
│       ├── schedule/                # 调度器
│       │   └── rss_scheduler.py     # 基于订阅维度的定时抓取 + 去重 + 分发
│       │
│       ├── config/                  # 配置管理
│       │   └── config_manager.py    # RsshubPluginConfig (Pydantic)
│       │
│       ├── api/                     # 外部 API
│       │   └── rsshub_radar_api.py  # RSSHub Radar 路由发现
│       │
│       ├── translation/             # 翻译引擎
│       │   ├── providers/           # google_translate.py, baidu_translate.py
│       │   └── translation_service.py
│       │
│       ├── utils/                   # 通用工具
│       │   ├── logger.py
│       │   ├── caching.py
│       │   ├── lock.py
│       │   ├── media_downloader.py
│       │   ├── html_cleaner.py
│       │   ├── expression_parser.py
│       │   ├── ffmpeg_helper.py
│       │   ├── concurrent.py
│       │   └── subscription_io.py
│       │
│       └── web/                     # WebUI
│           └── webui.py
│
├── docs/llm/                        # 上下文文档（当前目录）
├── tests/                           # 测试
├── skill/                           # 开发技能文档
└── _ref/                            # 参考仓库克隆
```

## 运行流程

### 即时推送

```
用户 /sub url
  → main.py (SubscribeFeedCommand)
    → FeedRepository.save(feed)
    → SubscriptionRepository.save(subscription)
  → rss_scheduler 按 interval 轮询
    → RSSFeedFetcher.fetch(url)       # HttpFetcher + feedparser
    → RSSParser.parse_entry()
    → NotificationServiceImpl
      → NotificationDispatcher
        → get_sender_for_platform()
        → platform sender.send_to_user()
    → PushHistoryRepository.save()
```

## 与参考仓库 (rss_forwarder) 的关键差异

| 维度 | rsshub (我们) | rss_forwarder |
|------|---------------|---------------|
| 架构 | DDD 四层 | 扁平单文件 |
| 持久化 | SQLite | AstrBot KV + state.json |
| 调度粒度 | 按订阅 | 按任务(job) |
| 翻译 | Google/Baidu | LLM→Google→GitHub Models 回退链 |
| 数据源 | 仅 RSS | RSS + Twitter/Nitter |
| 日报 | 无 | built-in |
| 发送指纹 | 无 | dispatch fingerprint + image sha256 |
| 配置校验 | Pydantic | dataclass + 手动 validate() |
