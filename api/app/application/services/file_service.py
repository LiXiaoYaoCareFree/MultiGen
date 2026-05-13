from typing import Tuple, BinaryIO, Callable, Optional

from fastapi import UploadFile

from app.application.errors.exceptions import NotFoundError
from app.domain.external.file_storage import FileStorage
from app.domain.models.file import File
from app.domain.repositories.uow import IUnitOfWork


class FileService:
    """MultiGen文件系统服务"""

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            file_storage: FileStorage,
    ) -> None:
        """构造函数，完成文件服务的初始化"""
        self.file_storage = file_storage
        self._uow_factory = uow_factory
        self._uow = uow_factory()

    @staticmethod
    def _normalize_relative_path(relative_path: Optional[str], fallback_filename: str) -> str:
        if not relative_path:
            return fallback_filename
        normalized = relative_path.replace("\\", "/").strip()
        if normalized.startswith("/"):
            normalized = normalized[1:]
        parts = [part for part in normalized.split("/") if part not in {"", ".", ".."}]
        if not parts:
            return fallback_filename
        return "/".join(parts)

    async def upload_file(self, upload_file: UploadFile, relative_path: Optional[str] = None) -> File:
        """将传递的文件上传到腾讯云cos并记录上传数据"""
        upload_file.filename = self._normalize_relative_path(relative_path, upload_file.filename or "upload")
        return await self.file_storage.upload_file(upload_file=upload_file)

    async def get_file_info(self, file_id: str) -> File:
        """根据传递的文件id获取文件信息"""
        async with self._uow:
            file = await self._uow.file.get_by_id(file_id)
        if not file:
            raise NotFoundError(f"该文件[{file_id}]不存在")
        return file

    async def download_file(self, file_id: str) -> Tuple[BinaryIO, File]:
        """根据传递的文件id下载文件"""
        return await self.file_storage.download_file(file_id)
