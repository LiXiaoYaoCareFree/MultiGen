import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.repositories.db_uow import DBUnitOfWork
from core.config import get_settings

logger = logging.getLogger(__name__)


class Postgres:
    """Postgres数据库基础类，用于完成数据库连接等配置操作"""

    def __init__(self):
        """构造函数，完成postgres数据库引擎、会话工厂的创建"""
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._settings = get_settings()

    async def init(self) -> None:
        """初始化postgres连接"""
        # 1.判断是否已经创建好引擎，如果连上了则中断程序
        if self._engine is not None:
            logger.warning(f"Postgres引擎已初始化，无需重复操作")
            return

        try:
            # 2.创建异步引擎
            logger.info("正在初始化Postgres连接...")
            self._engine = create_async_engine(
                self._settings.sqlalchemy_database_uri,
                echo=True if self._settings.env == "development" else False,
                pool_pre_ping=True,  # 每次从连接池获取连接前先检测连接是否有效，防止使用已关闭的连接
            )

            # 3.创建会话工厂
            self._session_factory = async_sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._engine,
            )
            logger.info("Postgres会话工厂创建完毕")

            # 4.连接Postgres并执行预操作
            async with self._engine.begin() as async_conn:
                # 5.检查是否安装了uuid扩展，如果没有的话则安装
                await async_conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                logger.info("成功连接Postgres并安装uuid-ossp扩展")
        except Exception as e:
            logger.error(f"连接Postgres失败: {str(e)}")
            raise

    async def shutdown(self) -> None:
        """关闭Postgres连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("成功关闭Postgres连接")

        # 2.清除缓存
        get_postgres.cache_clear()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """只读属性，返回已初始化的会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("Postgres未初始化，请先调用init()函数初始化")
        return self._session_factory


@lru_cache()
def get_postgres() -> Postgres:
    """获取Postgres实例"""
    return Postgres()


async def get_db_session() -> AsyncSession:
    """FastAPI依赖项，用于在每个请求中异步获取数据库会话实例，确保会话在正确使用后被关闭"""
    # 1.获取引擎和会话工厂
    db = get_postgres()
    session_factory = db.session_factory

    # 2.创建会话上下文，在上下文内完成数据提交
    async with session_factory() as session:
        try:
            yield session
        except Exception as _:
            await session.rollback()
            raise


def get_session_factory():
    """获取数据库会话工厂"""
    db = get_postgres()
    return db.session_factory


def get_uow() -> IUnitOfWork:
    return DBUnitOfWork(session_factory=get_session_factory())
