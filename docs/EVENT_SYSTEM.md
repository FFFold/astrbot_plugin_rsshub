# RSSHub 事件系统文档

## 概述

RSSHub 事件系统允许扩展和 AI 介入 RSS 处理的各个阶段，修改数据或添加自定义逻辑。

## 扩展优先级

扩展通过配置文件中的 `extensions` 列表定义加载顺序，**列表顺序即优先级顺序**：

```json
{
  "extensions": ["ai_rewrite", "ad_filter", "logger"]
}
```

**优先级规则**:
- 列表中越靠前的扩展优先级越高（越先执行）
- 靠前的扩展可以先拦截和修改数据
- 如果扩展调用了 `event.cancel()`，后续扩展不会执行
- 留空则自动加载 `plugins/` 目录下所有扩展（按文件名排序）

**典型优先级设计**:
```json
{
  "extensions": [
    "ai_rewrite",      // 优先级 1: AI 内容重写（最先处理）
    "content_filter",  // 优先级 2: 内容过滤（AI 处理后过滤）
    "logger",          // 优先级 3: 日志记录（最后记录最终结果）
    "metrics"          // 优先级 4: 指标统计（最后统计）
  ]
}
```

## 事件类型

### 1. FeedFetchEvent - RSS 抓取事件

**触发时机**: HTTP 请求获取 RSS 内容后

**用途**:
- 修改原始 XML 内容
- 记录抓取日志
- 添加自定义请求头

```python
from astrbot_plugin_rsshub.src.infrastructure import (
    FeedFetchEvent, Extension, on_event
)

class MyExtension(Extension):
    @on_event(FeedFetchEvent)
    async def on_fetch(self, event: FeedFetchEvent):
        # 修改 XML 内容
        event.content = event.content.replace("old", "new")
        # 记录日志
        print(f"Fetched {event.url}, status: {event.status_code}")
```

### 2. FeedParseEvent - RSS 解析事件

**触发时机**: XML 解析为条目后

**用途**:
- AI 重写条目内容
- 过滤不想要的条目
- 添加自定义元数据

```python
from astrbot_plugin_rsshub.src.infrastructure import FeedParseEvent

class MyExtension(Extension):
    @on_event(FeedParseEvent)
    async def on_parse(self, event: FeedParseEvent):
        # 重写标题
        for entry in event.entries:
            entry.title = await ai_rewrite(entry.title)

        # 过滤条目
        event.filter_entries(lambda e: "广告" not in e.title)

        # 取消后续处理（如果全部过滤掉）
        if not event.entries:
            event.cancel()
```

### 3. EntryProcessEvent - 条目处理事件

**触发时机**: 每个条目被处理时（格式化前）

**用途**:
- 修改单个条目内容
- 添加自定义标签
- AI 分析内容

```python
from astrbot_plugin_rsshub.src.infrastructure import EntryProcessEvent

class MyExtension(Extension):
    @on_event(EntryProcessEvent)
    async def on_entry(self, event: EntryProcessEvent):
        entry = event.entry
        # 添加 AI 标签
        tags = await ai_analyze(entry.content)
        entry.tags.extend(tags)
```

### 4. MessageFormatEvent - 消息格式化事件

**触发时机**: 消息内容格式化后，发送前

**用途**:
- 修改消息文案
- 添加签名/广告
- AI 优化文案

```python
from astrbot_plugin_rsshub.src.infrastructure import MessageFormatEvent

class MyExtension(Extension):
    @on_event(MessageFormatEvent)
    async def on_format(self, event: MessageFormatEvent):
        # 添加签名
        event.content += "\n\n[来自 RSSHub]"
        # AI 优化
        event.content = await ai_optimize(event.content)
```

### 5. MessageSendEvent - 消息发送事件

**触发时机**: 消息即将发送时

**用途**:
- 阻止发送（例如用户被封禁）
- 最后修改消息内容
- 添加水印

```python
from astrbot_plugin_rsshub.src.infrastructure import MessageSendEvent

class MyExtension(Extension):
    @on_event(MessageSendEvent)
    async def on_send(self, event: MessageSendEvent):
        # 检查是否应该发送
        if await is_user_blocked(event.session_id):
            event.cancel()
            return

        # 添加水印
        event.content += f"\n[发送给 {event.session_id}]"
```

### 6. MessageSentEvent - 消息发送完成事件

**触发时机**: 消息发送完成后（无论成功失败）

**用途**:
- 记录发送日志
- 统计成功率
- 发送失败时通知管理员

```python
from astrbot_plugin_rsshub.src.infrastructure import MessageSentEvent

class MyExtension(Extension):
    @on_event(MessageSentEvent)
    async def on_sent(self, event: MessageSentEvent):
        if event.success:
            print(f"消息发送成功: {event.session_id}")
        else:
            print(f"消息发送失败: {event.error}")
            await notify_admin(f"发送失败: {event.error}")
```

### 7. DeduplicationEvent - 去重检查事件

**触发时机**: 条目去重检查时

**用途**:
- 自定义去重逻辑
- AI 判断内容相似度
- 调整重复置信度

```python
from astrbot_plugin_rsshub.src.infrastructure import DeduplicationEvent

class MyExtension(Extension):
    @on_event(DeduplicationEvent)
    async def on_dedup(self, event: DeduplicationEvent):
        # 使用 AI 判断内容相似度
        similarity = await ai_similarity_check(
            event.entry,
            event.existing_hashes
        )

        if similarity > 0.9:
            event.is_duplicate = True
            event.confidence = similarity
```

## 创建扩展

### 基础扩展结构

```python
from astrbot_plugin_rsshub.src.infrastructure import (
    Extension, on_event, FeedParseEvent
)

class MyExtension(Extension):
    name = "my_extension"
    version = "1.0.0"
    description = "我的第一个扩展"
    author = "Your Name"

    @on_event(FeedParseEvent)
    async def on_parse(self, event: FeedParseEvent):
        # 你的逻辑
        pass

# 创建实例
extension_instance = MyExtension()
```

### 扩展生命周期

1. **加载**: 扩展文件被导入，创建实例
2. **注册**: `register()` 方法被调用，事件处理器被注册到事件总线
3. **运行**: 事件触发时调用对应处理器（按优先级顺序）
4. **注销**: `unregister()` 被调用，清理资源

### 扩展配置

扩展可以通过 `is_enabled` 属性控制是否启用:

```python
class MyExtension(Extension):
    @property
    def is_enabled(self) -> bool:
        # 从配置读取
        return get_config().get("my_extension.enabled", True)
```

### 从配置加载扩展

扩展管理器按配置顺序加载扩展：

```python
from astrbot_plugin_rsshub.src.infrastructure import get_plugin_manager

manager = get_plugin_manager()

# 按配置顺序加载扩展（顺序即优先级）
extension_names = ["ai_rewrite", "ad_filter", "logger"]
loaded = await manager.load_extensions_from_config(
    extension_names,
    plugins_dir=Path("/path/to/plugins")
)

# 按优先级顺序注册
manager.register_extensions()

# 查看扩展优先级
for name, ext, enabled, priority in manager.list_extensions():
    print(f"{name}: 优先级={priority}, 启用={enabled}")
```

## 高级用法

### 事件取消

在事件处理器中调用 `event.cancel()` 可以阻止后续处理:

```python
@on_event(FeedParseEvent)
async def filter_all(self, event: FeedParseEvent):
    if some_condition:
        event.cancel()  # 后续处理器不会执行
```

### 元数据传递

使用 `set_metadata` 和 `get_metadata` 在事件间传递数据:

```python
@on_event(FeedParseEvent)
async def step1(self, event: FeedParseEvent):
    event.set_metadata("processed_by_ai", True)

@on_event(MessageFormatEvent)
async def step2(self, event: MessageFormatEvent):
    # 注意: 不同事件类型间的元数据不共享
    # 这个示例仅作演示
    pass
```

### 异步处理

所有事件处理器都支持异步:

```python
@on_event(FeedParseEvent)
async def async_handler(self, event: FeedParseEvent):
    result = await some_async_operation()
    event.entries[0].title = result
```

## 完整示例: AI 优化扩展

参见 `plugins/ai_rewrite.py` 完整示例。

## 调试技巧

1. **日志输出**: 使用 `print()` 或日志记录器
2. **异常处理**: 异常会被捕获并记录，不会中断主流程
3. **性能监控**: 在处理器开始和结束时记录时间戳

```python
import time

@on_event(FeedParseEvent)
async def monitored_handler(self, event: FeedParseEvent):
    start = time.time()
    # 处理逻辑
    await process_entries(event.entries)
    elapsed = time.time() - start
    print(f"处理 {len(event.entries)} 个条目耗时 {elapsed:.2f}s")
```
