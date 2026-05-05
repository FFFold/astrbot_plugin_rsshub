"""测试事件系统和扩展系统"""

from __future__ import annotations

import pytest


class TestEventBus:
    """测试事件总线"""

    @pytest.mark.asyncio
    async def test_basic_publish_subscribe(self):
        """测试基本事件发布/订阅"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            EventBus,
            FeedParseEvent,
            EntryParsed,
        )

        bus = EventBus()
        received = []

        @bus.on(FeedParseEvent)
        async def handler(event):
            received.append(event)

        event = FeedParseEvent(entries=[EntryParsed(title="Test")])
        await bus.emit(event)

        assert len(received) == 1
        assert received[0].entries[0].title == "Test"

    @pytest.mark.asyncio
    async def test_event_cancellation(self):
        """测试事件取消"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            EventBus,
            FeedParseEvent,
        )

        bus = EventBus()
        handler2_called = False

        @bus.on(FeedParseEvent)
        async def handler1(event):
            event.cancel()

        @bus.on(FeedParseEvent)
        async def handler2(event):
            nonlocal handler2_called
            handler2_called = True

        event = FeedParseEvent(entries=[])
        await bus.emit(event)

        assert not handler2_called

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """测试多个处理器"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            EventBus,
            FeedParseEvent,
        )

        bus = EventBus()
        calls = []

        @bus.on(FeedParseEvent)
        async def handler1(event):
            calls.append(1)

        @bus.on(FeedParseEvent)
        async def handler2(event):
            calls.append(2)

        @bus.on(FeedParseEvent)
        async def handler3(event):
            calls.append(3)

        event = FeedParseEvent(entries=[])
        await bus.emit(event)

        assert calls == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_handler_off(self):
        """测试取消订阅"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            EventBus,
            FeedParseEvent,
        )

        bus = EventBus()
        calls = []

        @bus.on(FeedParseEvent)
        async def handler(event):
            calls.append(1)

        event = FeedParseEvent(entries=[])
        await bus.emit(event)
        assert calls == [1]

        bus.off(FeedParseEvent, handler)
        await bus.emit(event)
        assert calls == [1]  # 不应该再增加

    @pytest.mark.asyncio
    async def test_event_metadata(self):
        """测试事件元数据"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import FeedParseEvent

        event = FeedParseEvent(entries=[])
        event.set_metadata("key", "value")

        assert event.get_metadata("key") == "value"
        assert event.get_metadata("nonexistent", "default") == "default"


class TestExtension:
    """测试扩展系统"""

    def test_extension_attributes(self):
        """测试扩展属性"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import Extension

        class TestExtension(Extension):
            name = "test_ext"
            version = "1.0.0"
            description = "Test extension"
            author = "Test Author"

        ext = TestExtension()
        assert ext.name == "test_ext"
        assert ext.version == "1.0.0"
        assert ext.description == "Test extension"
        assert ext.author == "Test Author"
        assert ext.is_enabled is True

    @pytest.mark.asyncio
    async def test_extension_event_handler(self):
        """测试扩展事件处理器"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            Extension,
            on_event,
            FeedParseEvent,
            get_event_bus,
            reset_event_bus,
        )

        reset_event_bus()
        received = []

        class TestExtension(Extension):
            name = "test_ext"

            @on_event(FeedParseEvent)
            async def on_parse(self, event):
                received.append(event)

        ext = TestExtension()
        ext.register()

        event = FeedParseEvent(entries=[])
        await get_event_bus().emit(event)

        assert len(received) == 1

        ext.unregister()

    @pytest.mark.asyncio
    async def test_extension_multiple_events(self):
        """测试扩展处理多个事件"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            Extension,
            on_event,
            FeedParseEvent,
            MessageFormatEvent,
            get_event_bus,
            reset_event_bus,
        )

        reset_event_bus()
        parse_calls = []
        format_calls = []

        class TestExtension(Extension):
            name = "multi_event_ext"

            @on_event(FeedParseEvent)
            async def on_parse(self, event):
                parse_calls.append(event)

            @on_event(MessageFormatEvent)
            async def on_format(self, event):
                format_calls.append(event)

        ext = TestExtension()
        ext.register()

        parse_event = FeedParseEvent(entries=[])
        format_event = MessageFormatEvent(content="test")

        await get_event_bus().emit(parse_event)
        await get_event_bus().emit(format_event)

        assert len(parse_calls) == 1
        assert len(format_calls) == 1

        ext.unregister()


class TestPluginManager:
    """测试扩展管理器"""

    def test_load_extension(self):
        """测试加载扩展"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            PluginManager,
            Extension,
        )

        manager = PluginManager()

        # 创建临时扩展文件
        ext_code = '''
from astrbot_plugin_rsshub.src.infrastructure.messaging import Extension

class TestExtension(Extension):
    name = "test_ext"
    version = "1.0.0"
'''

        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(ext_code)
            temp_path = f.name

        try:
            ext = manager.load_extension("test_ext", temp_path)
            assert ext is not None
            assert ext.name == "test_ext"
        finally:
            os.unlink(temp_path)

    def test_enable_disable_extension(self):
        """测试启用/禁用扩展"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            PluginManager,
            Extension,
        )

        manager = PluginManager()

        class TestExtension(Extension):
            name = "test_ext"

        ext = TestExtension()
        manager.register_extension(ext)

        assert manager.list_extensions()[0][2] is True  # 应该启用

        manager.disable_extension("test_ext")
        assert manager.list_extensions()[0][2] is False  # 应该禁用

        manager.enable_extension("test_ext")
        assert manager.list_extensions()[0][2] is True  # 应该启用

    def test_get_extension(self):
        """测试获取扩展"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            PluginManager,
            Extension,
        )

        manager = PluginManager()

        class TestExtension(Extension):
            name = "test_ext"

        ext = TestExtension()
        manager.register_extension(ext)

        found = manager.get_extension("test_ext")
        assert found is ext

        not_found = manager.get_extension("nonexistent")
        assert not_found is None

    def test_list_extensions(self):
        """测试列出扩展"""
        from astrbot_plugin_rsshub.src.infrastructure.messaging import (
            PluginManager,
            Extension,
        )

        manager = PluginManager()

        class Ext1(Extension):
            name = "ext1"

        class Ext2(Extension):
            name = "ext2"

        manager.register_extension(Ext1())
        manager.register_extension(Ext2())

        extensions = manager.list_extensions()
        assert len(extensions) == 2
        names = [name for name, _, _ in extensions]
        assert "ext1" in names
        assert "ext2" in names
