import io
import logging
import os
import zipfile
from typing import List, Callable, Type, Optional

from app.application.errors.exceptions import NotFoundError, ServerRequestsError
from app.domain.external.file_storage import FileStorage
from app.domain.external.sandbox import Sandbox
from app.domain.models.file import File
from app.domain.models.session import Session
from app.domain.repositories.uow import IUnitOfWork
from app.interfaces.schemas.session import FileReadResponse, ShellReadResponse
from core.config import get_settings

logger = logging.getLogger(__name__)


class SessionService:
    """会话服务"""

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            sandbox_cls: Type[Sandbox],
            file_storage: FileStorage,
    ) -> None:
        """构造函数，完成会话服务初始化"""
        self._uow_factory = uow_factory
        self._uow = uow_factory()
        self._sandbox_cls = sandbox_cls
        self._file_storage = file_storage

    async def _get_sandbox(self, sandbox_id: Optional[str]) -> Optional[Sandbox]:
        if not sandbox_id:
            return None
        try:
            return await self._sandbox_cls.get(sandbox_id)
        except Exception as e:
            logger.warning(f"获取会话沙箱失败[{sandbox_id}]，将回退到对象存储文件: {str(e)}")
            return None

    async def _read_session_file_bytes(self, sandbox: Optional[Sandbox], file: File) -> bytes:
        if sandbox and file.filepath:
            try:
                sandbox_stream = await sandbox.download_file(file.filepath)
                return sandbox_stream.read()
            except Exception as e:
                logger.warning(f"从沙箱读取文件失败[{file.filepath}]，回退到对象存储文件: {str(e)}")

        file_stream, _ = await self._file_storage.download_file(file.id)
        return file_stream.read()

    async def create_session(self) -> Session:
        """创建一个空白的新任务会话"""
        logger.info(f"创建一个空白新任务会话")
        session = Session(title="新对话")
        async with self._uow:
            await self._uow.session.save(session)
        logger.info(f"成功创建一个新任务会话: {session.id}")
        return session

    async def get_all_sessions(self) -> List[Session]:
        """获取项目所有任务会话列表"""
        async with self._uow:
            return await self._uow.session.get_all()

    async def clear_unread_message_count(self, session_id: str) -> None:
        """清空指定会话未读消息数"""
        logger.info(f"清除会话[{session_id}]未读消息数")
        async with self._uow:
            await self._uow.session.update_unread_message_count(session_id, 0)

    async def delete_session(self, session_id: str, admin_api_key: Optional[str] = None) -> None:
        """根据传递的会话id删除任务会话"""
        # 1.验证管理员权限
        settings = get_settings()
        if not settings.admin_auth_required and settings.admin_api_key and settings.admin_api_key != admin_api_key:
            logger.warning(f"删除会话[{session_id}]失败: 管理员密钥无效")
            raise ServerRequestsError("无权限删除会话")

        # 2.先检查会话是否存在
        logger.info(f"正在删除会话, 会话id: {session_id}")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            logger.error(f"会话[{session_id}]不存在, 删除失败")
            raise NotFoundError(f"会话[{session_id}]不存在, 删除失败")

        # 3.根据传递的会话id删除会话
        async with self._uow:
            await self._uow.session.delete_by_id(session_id)
        logger.info(f"删除会话[{session_id}]成功")

    async def get_session(self, session_id: str) -> Session:
        """获取指定会话详情信息"""
        async with self._uow:
            return await self._uow.session.get_by_id(session_id)

    async def get_session_files(self, session_id: str) -> List[File]:
        """根据传递的会话id获取指定会话的文件列表信息"""
        logger.info(f"获取指定会话[{session_id}]下的文件列表信息")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"当前会话不存在[{session_id}], 请核实后重试")
        return session.files

    async def download_directory(self, session_id: str, dirpath: str) -> tuple[io.BytesIO, str]:
        """根据会话已记录的文件清单打包下载目录压缩包"""
        logger.info(f"下载会话[{session_id}]中的目录压缩包, 目录路径: {dirpath}")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"当前会话不存在[{session_id}], 请核实后重试")

        normalized_dirpath = os.path.normpath(dirpath)
        dir_name = os.path.basename(normalized_dirpath) or "folder"
        dir_prefix = normalized_dirpath.rstrip(os.sep) + os.sep

        matched_files = [
            file for file in (session.files or [])
            if file.filepath and (file.filepath == normalized_dirpath or file.filepath.startswith(dir_prefix))
        ]
        if not matched_files:
            raise NotFoundError(f"当前会话目录下无可下载文件: {dirpath}")

        sandbox = await self._get_sandbox(session.sandbox_id)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file in sorted(matched_files, key=lambda item: item.filepath):
                relative_path = os.path.relpath(file.filepath, normalized_dirpath)
                if relative_path.startswith(".."):
                    continue
                file_bytes = await self._read_session_file_bytes(sandbox, file)
                arcname = os.path.join(dir_name, relative_path)
                zip_file.writestr(arcname, file_bytes)

        archive.seek(0)
        return archive, f"{dir_name}.zip"

    async def read_file(self, session_id: str, filepath: str) -> FileReadResponse:
        """根据传递的信息查看会话中指定文件的内容"""
        # 1.检查会话是否存在
        logger.info(f"获取会话[{session_id}]中的文件内容, 文件路径: {filepath}")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"当前会话不存在[{session_id}], 请核实后重试")

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        # 3.调用沙箱读取文件内容
        result = await sandbox.read_file(filepath)
        if result.success:
            return FileReadResponse(**result.data)

        raise ServerRequestsError(result.message)

    async def read_shell_output(self, session_id: str, shell_session_id: str) -> ShellReadResponse:
        """根据传递的任务会话id+Shell会话id获取Shell执行结果"""
        # 1.检查会话是否存在
        logger.info(f"获取会话[{session_id}]中的Shell内容输出, Shell标识符: {shell_session_id}")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"当前会话不存在[{session_id}], 请核实后重试")

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        # 3.调用沙箱查看shell内容
        result = await sandbox.read_shell_output(session_id=shell_session_id, console=True)
        if result.success:
            return ShellReadResponse(**result.data)

        raise ServerRequestsError(result.message)

    async def get_vnc_url(self, session_id: str) -> str:
        """获取指定会话的vnc链接"""
        # 1.检查会话是否存在
        logger.info(f"获取会话[{session_id}]的VNC链接")
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"当前会话不存在[{session_id}], 请核实后重试")

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        return sandbox.vnc_url
