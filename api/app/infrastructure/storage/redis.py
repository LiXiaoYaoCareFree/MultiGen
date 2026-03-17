import logging
from functools import lru_cache

from redis.asyncio import Redis

from core.config import get_settings, Settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端，用于完成redis缓存连接&使用"""

    def __init__(self):
        """构造函数，完成redis客户端的创建"""
        self._client: Redis | None = None
        self._settings: Settings = get_settings()

    async def init(self) -> None:
        """完成redis客户端的初始化"""
        # 1.判断客户端是否存在，如果存在则表示已连接上，无需重复连接
        if self._client:
            logger.warning("Redis客户端已初始化，无需重复操作")
            return

        try:
            # 2.创建Redis客户端并连接
            self._client = Redis(
                host=self._settings.redis_host,
                port=self._settings.redis_port,
                db=self._settings.redis_db,
                password=self._settings.redis_password,
                decode_responses=True,
            )

            # 3.测试连接redis缓存
            await self._client.ping()
            logger.info("Redis客户端初始化成功")
        except Exception as e:
            logger.error(f"初始化Redis客户端失败: {str(e)}")
            raise

    async def shutdown(self) -> None:
        """关闭Redis时执行的操作"""
        # 1.客户端存在则关闭客户端并提示
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis客户端成功关闭")

        # 2.清除缓存
        get_redis.cache_clear()

    @property
    def client(self) -> Redis:
        """只读属性，返回redis客户端"""
        if self._client is None:
            raise RuntimeError("Redis客户端未初始化，获取客户端失败")
        return self._client


@lru_cache()
def get_redis() -> RedisClient:
    """获取redis实例"""
    return RedisClient()
