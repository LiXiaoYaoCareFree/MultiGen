import asyncio
import logging
import uuid
from typing import Any, Tuple, Optional, AsyncGenerator

from app.domain.external.message_queue import MessageQueue
from app.infrastructure.storage.redis import get_redis

logger = logging.getLogger(__name__)


class RedisStreamMessageQueue(MessageQueue):
    """基于RedisStream的消息队列"""

    def __init__(self, stream_name: str) -> None:
        """构造函数，完成Redis-Stream的初始化，涵盖名字、锁的时间"""
        self._stream_name = stream_name
        self._redis = get_redis()
        self._lock_expire_seconds = 10

    async def _acquire_lock(self, lock_key: str, timeout_seconds: int = 5) -> Optional[str]:
        """根据传递的lock键构建一个分布式锁"""
        # 1.创建锁对应的值
        lock_value = str(uuid.uuid4())
        end_time = timeout_seconds

        # 2.使用end_time构建一个循环
        while end_time > 0:
            # 3.使用redis的set方法，将lock_key和lock_value存储到redis中，并且设置过期时间
            result = await self._redis.client.set(
                lock_key,
                lock_value,
                nx=True,  # 如果值存在则不设置，否则进行设置
                ex=self._lock_expire_seconds,
            )

            # 4.如果设置成功，则返回锁的值
            if result:
                return lock_value

            # 5.睡眠指定时间并且将end_time递减
            await asyncio.sleep(0.1)
            end_time -= 0.1

        return None

    async def _release_lock(self, lock_key: str, lock_value: str) -> bool:
        """根据传递的lock_key+lock_value释放分布式锁"""
        # 1.构建一段redis的脚本用于释放分布式锁
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        try:
            # 2.注册脚本
            script = self._redis.client.register_script(release_script)

            # 3.执行脚本并传递keys+args释放分布式锁
            result = await script(keys=[lock_key], args=[lock_value])

            return result == 1
        except Exception:
            return False

    async def put(self, message: Any) -> str:
        """往redis-stream中添加一条消息并返回id"""
        logger.debug(f"往消息队列[{self._stream_name}]中添加一条消息: {message}")

        return await self._redis.client.xadd(self._stream_name, {"data": message})

    async def get(self, start_id: str = None, block_ms: int = None) -> Tuple[str, Any]:
        """从redis-stream获取一条数据"""
        logger.debug(f"从消息队列[{self._stream_name}]中获取一条消息: {start_id}")

        # 1.判断start_id是否为None
        if start_id is None:
            start_id = '0'

        # 2.从redis流中获取一条数据
        messages = await self._redis.client.xread(
            {self._stream_name: start_id},
            count=1,
            block=block_ms,
        )

        # 3.检查messages是否存在
        if not messages:
            return None, None

        # 4.从消息列表中取出对应的消息数据
        stream_messages = messages[0][1]
        if not stream_messages:
            return None, None

        # 5.提取id和数据
        message_id, message_data = stream_messages[0]

        try:
            return message_id, message_data.get("data")
        except Exception as e:
            logger.error(f"从消息队列[{self._stream_name}]获取数据失败: {str(e)}")
            return None, None

    async def pop(self) -> Tuple[str, Any]:
        """从消息队列中获取第一条消息并删除"""
        # 1.记录日志
        logger.debug(f"从消息队列[{self._stream_name}]中弹出第一条消息")
        lock_key = f"lock:{self._stream_name}:pop"

        # 2.构建分布式锁，如果分布式锁创建失败则返回None
        lock_value = await self._acquire_lock(lock_key)
        if not lock_value:
            return None, None

        try:
            # 3.从redis流中获取第一条消息
            messages = await self._redis.client.xrange(self._stream_name, "-", "+", count=1)
            if not messages:
                return None, None

            # 4.取出消息id和消息
            message_id, message_data = messages[0]

            # 5.删除消息队列中的message数据
            await self._redis.client.xdel(self._stream_name, message_id)

            return message_id, message_data.get("data")
        except Exception as e:
            logger.error(f"解析消息队列[{self._stream_name}]出错: {str(e)}")
            return None
        finally:
            await self._release_lock(lock_key, lock_value)

    async def clear(self) -> None:
        """清除redis-stream中的所有消息"""
        await self._redis.client.xtrim(self._stream_name, 0)

    async def is_empty(self) -> bool:
        """检查redis-stream是否为空"""
        return await self.size() == 0

    async def size(self) -> int:
        """获取redis-stream的长度"""
        return await self._redis.client.xlen(self._stream_name)

    async def delete_message(self, message_id: str) -> bool:
        """根据传递的消息id从redis-stream删除数据"""
        try:
            await self._redis.client.xdel(self._stream_name, message_id)
            return True
        except Exception:
            return False

    async def get_range(
            self,
            start_id: str = "-",
            end_id: str = "+",
            count: int = 100,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """根据传递的起点、终点id、数量，获取异步迭代器得到消息数据"""
        # 1.获取所有的消息
        messages = await self._redis.client.xrange(self._stream_name, start_id, end_id, count=count)

        # 2.如果消息不存在则中断程序
        if not messages:
            return

        # 3.循环遍历所有的消息列表并取出消息id+消息数据
        for message_id, message_data in messages:
            try:
                yield message_id, message_data.get("data")
            except Exception:
                continue

    async def get_latest_id(self) -> str:
        """获取消息队列中最新的id"""
        # 1.取出倒序的消息列表，并且设置count=1
        messages = await self._redis.client.xrevrange(self._stream_name, "+", "-", count=1)
        if not messages:
            return "0"

        # 2.否则取出消息id并返回
        return messages[0][0]
