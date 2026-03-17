import asyncio
import glob
import logging
import os.path
import re
from typing import Optional

from fastapi import UploadFile

from app.interfaces.errors.exceptions import (
    NotFoundException,
    BadRequestException,
    AppException
)
from app.models.file import (
    FileReadResult,
    FileWriteResult,
    FileReplaceResult,
    FileSearchResult,
    FileFindResult,
    FileUploadResult,
    FileCheckResult,
    FileDeleteResult
)

logger = logging.getLogger(__name__)


class FileService:
    """文件沙箱服务"""

    def __init__(self) -> None:
        pass

    @classmethod
    async def read_file(
            cls,
            filepath: str,
            start_line: Optional[int] = None,
            end_line: Optional[int] = None,
            sudo: bool = False,
            max_length: Optional[int] = 10000,
    ) -> FileReadResult:
        """根据传递的文件路径+起始行号+权限+最大长度读取文件内容"""
        try:
            # 1.检测在当前权限下能否获取该文件
            if not os.path.exists(filepath) and not sudo:
                logger.error(f"要读取的文件不存在或无权限: {filepath}")
                raise NotFoundException(f"要读取的文件不存在或无权限: {filepath}")

            # 2.ubuntu系统下统一使用utf-8编码
            encoding = "utf-8"

            # 3.判断是否为sudo，如果是sudo系统则使用命令行的形式读取文件
            if sudo:
                # 4.使用sudo cat命令读取文件内容
                command = f"sudo cat '{filepath}'"
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # 5.读取子进程的输出，并等待子进程结束
                stdout, stderr = process.communicate()

                # 6.判断子进程的状态是否正常结束
                if process.returncode != 0:
                    raise BadRequestException(f"阅读文件失败: {stderr.decode()}")

                # 7.读取输出内容
                content = stdout.decode(encoding, errors="replace")
            else:
                # 8.创建一个内部读取函数
                def async_read_file() -> str:
                    try:
                        with open(filepath, "r", encoding=encoding) as f:
                            return f.read()
                    except Exception as async_read_file_exception:
                        raise AppException(msg=f"读取文件失败: {str(async_read_file_exception)}")

                # 9.使用asyncio创建线程读取文件
                content = await asyncio.to_thread(async_read_file)

            # 10.判断是否传递了读取范围
            if start_line is not None or end_line is not None:
                # 11.将内容切割成行，并且提取指定范围行号的数据
                lines = content.splitlines()
                start = start_line if start_line is not None else 0
                end = end_line if end_line is not None else len(lines)
                content = "\n".join(lines[start:end])

            # 12.裁切下数据长度
            if max_length is not None and 0 < max_length < len(content):
                content = content[:max_length] + "(truncated)"

            return FileReadResult(filepath=filepath, content=content)
        except Exception as e:
            # 13.判断异常类型执行不同操作
            if isinstance(e, BadRequestException) or isinstance(e, AppException):
                raise
            raise AppException(f"文件读取失败: {str(e)}")

    @classmethod
    async def write_file(
            cls,
            filepath: str,
            content: str,
            append: bool = False,
            leading_newline: bool = False,
            trailing_newline: bool = False,
            sudo: bool = False,
    ) -> FileWriteResult:
        """根据传递的文件路径+内容向指定文件写入内容"""
        try:
            # 1.组装实际写入的内容
            if leading_newline:
                content = "\n" + content
            if trailing_newline:
                content = content + "\n"

            # 2.判断是否是sudo权限，如果是则使用命令行的形式先写入一个缓存文件，然后将缓存文件覆盖原始文件
            if sudo:
                # 3.使用命令的方式先向临时文件写入数据，计算追加模式
                mode = ">>" if append else ">"

                # 4.创建一个临时文件
                temp_file = f"/tmp/file_write_{os.getpid()}.tmp"

                # 5.创建一个内部函数使用asyncio创建新线程写入数据
                def async_write_temp_file() -> int:
                    with open(temp_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    return len(content.encode("utf-8"))

                # 6.使用asyncio创建子线程并写入
                bytes_written = await asyncio.to_thread(async_write_temp_file)

                # 7.使用命令行将临时文件写入到目标哦文件中
                command = f"sudo bash -c \"cat {temp_file} {mode} {filepath}\""
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # 8.等待子进程执行完毕
                stdout, stderr = await process.communicate()

                # 9.检测子进程是否正常执行
                if process.returncode != 0:
                    raise BadRequestException(f"文件内容写入失败: {stderr.decode()}")

                # 10.清除下临时文件
                os.unlink(temp_file)
            else:
                # 11.非sudo使用Python方式写入，先确保文件路径存在
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

                # 12.创建一个异步写入的函数
                def async_write_file() -> int:
                    write_mode = "a" if append else "w"
                    with open(filepath, write_mode, encoding="utf-8") as f:
                        return f.write(content)

                # 13.使用asyncio创建一个子线程写入内容
                bytes_written = await asyncio.to_thread(async_write_file)

            return FileWriteResult(
                filepath=filepath,
                bytes_written=bytes_written,
            )
        except Exception as e:
            # 14.根据不同的错误执行不同的操作
            logger.error(f"文件内容写入失败: {str(e)}")
            if isinstance(e, BadRequestException):
                raise
            raise AppException(f"文件内容写入失败: {str(e)}")

    async def replace_in_file(
            self,
            filepath: str,
            old_str: str,
            new_str: str,
            sudo: bool = False,
    ) -> FileReplaceResult:
        """根据传递的数据替换文件内指定的内容"""
        # 1.调用服务获取对应的文件内容
        file_read_result = await self.read_file(filepath=filepath, sudo=sudo, max_length=None)
        content = file_read_result.content

        # 2.计算old_str出现的次数，只有出现次数>0才需要替换
        replaced_count = content.count(old_str)
        if replaced_count == 0:
            return FileReplaceResult(filepath=filepath, replaced_count=replaced_count)

        # 3.替换旧内容
        new_content = content.replace(old_str, new_str)

        # 4.将替换后的新内容写入到文件中
        await self.write_file(
            filepath=filepath,
            content=new_content,
            sudo=sudo,
        )

        return FileReplaceResult(filepath=filepath, replaced_count=replaced_count)

    async def search_in_file(
            self,
            filepath: str,
            regex: str,
            sudo: bool = False,
    ) -> FileSearchResult:
        """根据传递的文件路径+匹配规则查询文件内符合的内容"""
        # 1.调用服务获取对应的文件内容
        file_read_result = await self.read_file(filepath=filepath, sudo=sudo, max_length=None)
        content = file_read_result.content

        # 2.将读取的内容拆分成每一行
        lines = content.splitlines()
        matches = []
        line_numbers = []

        # 3.将外部传递的regex转换为正则
        try:
            pattern = re.compile(regex)
        except Exception as e:
            raise BadRequestException(f"传递正则表达式[{regex}]出错: {str(e)}")

        # 4.创建一个异步函数，使用子线程方式执行避免长时间io阻塞
        def async_matches():
            nonlocal matches, line_numbers
            for idx, line in enumerate(lines):
                if pattern.match(line):
                    matches.append(line)
                    line_numbers.append(idx)

        # 5.使用asyncio创建子线程并调用
        await asyncio.to_thread(async_matches)

        return FileSearchResult(
            filepath=filepath,
            matches=matches,
            line_numbers=line_numbers,
        )

    @classmethod
    async def find_files(cls, dir_path: str, glob_pattern: str) -> FileFindResult:
        """根据传递的文件夹路径+glob规则查询文件列表"""
        # 1.检测下传递进来的目录是否存在
        if not os.path.exists(dir_path):
            raise NotFoundException(f"当前文件夹不存在: {dir_path}")

        # 2.定义一个异步函数使用asyncio子线程运行避免IO阻塞
        def async_glob():
            search_pattern = os.path.join(dir_path, glob_pattern)
            return glob.glob(search_pattern, recursive=True)

        # 3.创建子线程完成任务
        files = await asyncio.to_thread(async_glob)

        return FileFindResult(dir_path=dir_path, files=files)

    @classmethod
    async def upload_file(cls, file: UploadFile, filepath: str) -> FileUploadResult:
        """根据传递的文件源+路径将文件上传至沙箱"""
        try:
            # 1.定义分块上传，每次只上传8k
            chunk_size = 1024 * 8
            file_size = 0

            # 2.确保上传文件所在的目录存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 3.定义一个异步函数用于上传文件避免阻塞进程
            def async_write_file():
                nonlocal file_size
                with open(filepath, "wb") as f:
                    while True:
                        chunk = file.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        file_size += len(chunk)

            # 4.使用asyncio子线程完成函数调用
            await asyncio.to_thread(async_write_file)

            return FileUploadResult(
                filepath=filepath,
                file_size=file_size,
                success=True,
            )
        except Exception as e:
            logger.error(f"上传文件到沙箱出错: {str(e)}")
            raise AppException(f"上传文件到沙箱出错: {str(e)}")

    @classmethod
    async def ensure_file(cls, filepath: str) -> None:
        """传递filepath用于确保当前文件存在"""
        if not os.path.exists(filepath):
            raise NotFoundException(f"该文件不存在: {filepath}")

    @classmethod
    async def check_file_exists(cls, filepath: str) -> FileCheckResult:
        """根据传递的路径判断文件是否存在"""
        return FileCheckResult(
            filepath=filepath,
            exists=os.path.exists(filepath),
        )

    async def delete_file(self, filepath: str) -> FileDeleteResult:
        """根据传递的路径+sudo删除指定文件"""
        # 1.判断文件是否存在
        await self.ensure_file(filepath)

        try:
            # 2.调用命令删除文件
            os.remove(filepath)
            return FileDeleteResult(filepath=filepath, deleted=True)
        except Exception as e:
            logger.error(f"删除文件{filepath}失败: {str(e)}")
            raise AppException(f"删除文件{filepath}失败: {str(e)}")
