from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.file import File
from app.domain.repositories.file_repository import FileRepository
from app.infrastructure.models import FileModel


class DBFileRepository(FileRepository):
    """基于数据库的文件数据仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        """构造函数，完成数据仓库初始化"""
        self.db_session = db_session

    async def save(self, file: File) -> None:
        """根据传递的文件模型存储or更新数据"""
        # 1.根据id查询记录是否存在
        stmt = select(FileModel).where(FileModel.id == file.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.判断如果文件不存在则新建文件
        if not record:
            record = FileModel.from_domain(file)
            self.db_session.add(record)
            return

        # 3.文件存在则直接更新文件
        record.update_from_domain(file)

    async def get_by_id(self, file_id: str) -> Optional[File]:
        """根据传递的文件id获取文件信息"""
        # 1.根据id查询记录是否存在
        stmt = select(FileModel).where(FileModel.id == file_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.判断文件记录是否存在返回不同的值
        return record.to_domain() if record is not None else None
