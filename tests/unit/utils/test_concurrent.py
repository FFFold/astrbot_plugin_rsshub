"""测试异步并发工具"""

from __future__ import annotations

import asyncio

import pytest

from astrbot_plugin_rsshub.src.infrastructure.utils import (
    AsyncTool,
    retry,
    semaphore,
    timeout,
)


class TestAsyncTool:
    """测试 AsyncTool 类"""

    @pytest.mark.asyncio
    async def test_async_map_concurrent(self):
        """测试异步并发映射"""

        async def double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        results = await AsyncTool.async_map(double, [1, 2, 3, 4, 5])
        assert sorted(results) == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_async_map_empty_list(self):
        """测试空列表映射"""

        async def dummy(x: int) -> int:
            return x

        results = await AsyncTool.async_map(dummy, [])
        assert results == []

    @pytest.mark.asyncio
    async def test_async_filter(self):
        """测试异步过滤"""

        async def is_even(x: int) -> bool:
            await asyncio.sleep(0.01)
            return x % 2 == 0

        results = await AsyncTool.async_filter(is_even, [1, 2, 3, 4, 5])
        assert results == [2, 4]

    @pytest.mark.asyncio
    async def test_gather_with_concurrency(self):
        """测试带并发限制的 gather"""
        call_times = []

        async def task(n: int) -> int:
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)
            return n

        tasks = [task(i) for i in range(6)]
        results = await AsyncTool.gather_with_concurrency(tasks, limit=2)

        assert sorted(results) == [0, 1, 2, 3, 4, 5]
        # 并发限制为2，应该分批执行

    @pytest.mark.asyncio
    async def test_gather_with_concurrency_empty(self):
        """测试空任务列表"""
        results = await AsyncTool.gather_with_concurrency([], limit=2)
        assert results == []

    @pytest.mark.asyncio
    async def test_run_with_timeout_success(self):
        """测试超时成功"""

        async def quick_task() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await AsyncTool.run_with_timeout(quick_task(), timeout=0.5)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_run_with_timeout_expires(self):
        """测试超时过期"""

        async def slow_task() -> str:
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await AsyncTool.run_with_timeout(slow_task(), timeout=0.05)


class TestRetryDecorator:
    """测试 retry 装饰器"""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """测试首次成功不重试"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self):
        """测试重试最终成功"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        async def sometimes_fail() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = await sometimes_fail()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """测试重试耗尽抛出异常"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count}")

        with pytest.raises(ValueError, match="Attempt 3"):
            await always_fail()

        assert call_count == 3


class TestSemaphoreDecorator:
    """测试 semaphore 装饰器"""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """测试信号量限制并发"""
        max_concurrent = 0
        current_concurrent = 0

        @semaphore(2)
        async def task(n: int) -> int:
            nonlocal max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            current_concurrent -= 1
            return n

        await asyncio.gather(*[task(i) for i in range(5)])
        assert max_concurrent <= 2


class TestTimeoutDecorator:
    """测试 timeout 装饰器"""

    @pytest.mark.asyncio
    async def test_timeout_success(self):
        """测试超时成功"""

        @timeout(0.5)
        async def quick_task() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await quick_task()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_expires(self):
        """测试超时过期"""

        @timeout(0.05)
        async def slow_task() -> str:
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await slow_task()
