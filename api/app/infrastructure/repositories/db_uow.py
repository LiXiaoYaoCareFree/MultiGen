import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.domain.repositories.uow import IUnitOfWork
from .db_file_repository import DBFileRepository
from .db_session_repository import DBSessionRepository

logger = logging.getLogger(__name__)


class DBUnitOfWork(IUnitOfWork):
    """基于Postgres数据库的UoW实例"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """构造函数，完成UoW类初始化"""
        self.session_factory = session_factory
        self.db_session: Optional[AsyncSession] = None

    async def commit(self):
        """提交数据库持久化"""
        await self.db_session.commit()

    async def rollback(self):
        """数据库回退操作"""
        await self.db_session.rollback()

    async def __aenter__(self) -> "DBUnitOfWork":
        """进入UoW操作上下文管理器的逻辑"""
        # 1.为每个上下文开启一个新的会话
        self.db_session = self.session_factory()

        # 2.初始化所有数据库仓库
        self.file = DBFileRepository(db_session=self.db_session)
        self.session = DBSessionRepository(db_session=self.db_session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时执行的逻辑，如果出现异常则回滚，否则提交

        当SSE客户端断开连接时，sse_starlette的cancel scope会取消所有await操作，
        包括此处的commit/rollback/close。如果不妥善处理CancelledError，
        会导致连接池中的连接处于异常状态，影响后续使用该池的其他任务。
        """
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        except asyncio.CancelledError:
            # SSE断连等场景下cancel scope取消了commit/rollback操作，
            # 记录警告但不让异常传播，避免后续close操作也被跳过
            logger.warning("UoW提交/回滚操作被取消(可能是客户端断开连接)")
        except Exception as e:
            logger.warning(f"UoW提交/回滚操作失败: {e}")
        finally:
            try:
                await self.db_session.close()
            except asyncio.CancelledError:
                logger.warning("UoW关闭数据库会话被取消(可能是客户端断开连接)")
            except Exception as e:
                logger.warning(f"UoW关闭数据库会话失败: {e}")
