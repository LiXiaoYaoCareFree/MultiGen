import logging
import os.path
import uuid
from datetime import datetime
from typing import Tuple, BinaryIO, Callable

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.domain.external.file_storage import FileStorage
from app.domain.models.file import File
from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.storage.cos import Cos

logger = logging.getLogger(__name__)


class CosFileStorage(FileStorage):
    """基于COS的文件存储扩展"""

    def __init__(
            self,
            bucket: str,
            cos: Cos,
            uow_factory: Callable[[], IUnitOfWork],
    ) -> None:
        """构造函数，完成cos文件存储桶扩展初始化"""
        self.bucket = bucket
        self.cos = cos
        self._uow_factory = uow_factory
        self._uow = uow_factory()

    async def upload_file(self, upload_file: UploadFile) -> File:
        """根据传递的文件源将文件上传到腾讯云cos"""
        try:
            # 1.生成随机的uuid作为文件id并获取文件扩展名
            file_id = str(uuid.uuid4())
            _, file_extension = os.path.splitext(upload_file.filename)
            if not file_extension:
                file_extension = ""

            # 2.生成日期路径并拼接最终key
            date_path = datetime.now().strftime("%Y/%m/%d")
            cos_key = f"{date_path}/{file_id}{file_extension}"

            # 3.使用fastapi的线程池来上传文件
            await run_in_threadpool(
                self.cos.client.put_object,
                Bucket=self.bucket,
                Body=upload_file.file,
                Key=cos_key,
            )
            logger.info(f"文件上传成功: {upload_file.filename} (ID: {file_id})")

            # 4.构建file模型并将数据存储到数据库中
            file = File(
                id=file_id,
                filename=upload_file.filename,
                key=cos_key,
                extension=file_extension,
                mime_type=upload_file.content_type or "",
                size=upload_file.size,
            )
            async with self._uow:
                await self._uow.file.save(file)

            return file
        except Exception as e:
            logger.error(f"上传文件[{upload_file.filename}]失败: {str(e)}")
            raise

    async def download_file(self, file_id: str) -> Tuple[BinaryIO, File]:
        """根据文件id查询数据并下载文件"""
        try:
            # 1.查询对应的文件记录是否存在
            async with self._uow:
                file = await self._uow.file.get_by_id(file_id)
            if not file:
                raise ValueError(f"该文件不存在, 文件id: {file_id}")

            # 2.使用线程池来下载文件
            response = await run_in_threadpool(
                self.cos.client.get_object,
                Bucket=self.bucket,
                Key=file.key,
            )

            # 3.返回文件流+文件信息
            return response["Body"], file
        except Exception as e:
            logger.error(f"下载文件[{file_id}]失败: {str(e)}")
            raise
