from typing import Optional

from app.domain.external.sandbox import Sandbox
from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool


class FileTool(BaseTool):
    """文件工具箱"""
    name: str = "file"

    def __init__(self, sandbox: Sandbox) -> None:
        """构造函数，完成文件工具箱初始化"""
        super().__init__()
        self.sandbox = sandbox

    @tool(
        name="file_read",
        description="读取文件内容。用于检查文件内容、分析日志或读取配置文件。",
        parameters={
            "filepath": {
                "type": "string",
                "description": "要读取文件的绝对路径"
            },
            "start_line": {
                "type": "integer",
                "description": "(可选)读取的起始行, 索引从 0 开始",
            },
            "end_line": {
                "type": "integer",
                "description": "(可选)结束行号, 不包含该行",
            },
            "sudo": {
                "type": "boolean",
                "description": "(可选)是否使用 sudo 权限",
            },
            "max_length": {
                "type": "integer",
                "description": "(可选)读取文件内容的最大长度, 默认为10000"
            }
        },
        required=["filepath"],
    )
    async def file_read(
            self,
            filepath: str,
            start_line: Optional[int] = None,
            end_line: Optional[int] = None,
            sudo: Optional[bool] = False,
            max_length: int = 10000,
    ) -> ToolResult:
        """传递文件路径读取沙箱中的文件内容"""
        return await self.sandbox.file_read(
            filepath=filepath,
            start_line=start_line,
            end_line=end_line,
            sudo=sudo,
            max_length=max_length,
        )

    @tool(
        name="file_write",
        description="对文件进行覆盖或追加写入。用于创建新文件、追加内容或修改现有文件。",
        parameters={
            "filepath": {
                "type": "string",
                "description": "要写入文件的绝对路径"
            },
            "content": {
                "type": "string",
                "description": "要写入的文本内容"
            },
            "append": {
                "type": "boolean",
                "description": "(可选)是否使用追加模式"
            },
            "leading_newline": {
                "type": "boolean",
                "description": "(可选)是否添加前置换行符, 在内容开头"
            },
            "trailing_newline": {
                "type": "boolean",
                "description": "(可选)是否添加后置换行符, 在内容结尾"
            },
            "sudo": {
                "type": "boolean",
                "description": "(可选)是否使用 sudo 权限"
            }
        },
        required=["filepath", "content"]
    )
    async def file_write(
            self,
            filepath: str,
            content: str,
            append: Optional[bool] = False,
            leading_newline: Optional[bool] = False,
            trailing_newline: Optional[bool] = False,
            sudo: Optional[bool] = False
    ) -> ToolResult:
        return await self.sandbox.file_write(
            filepath=filepath,
            content=content,
            append=append,
            leading_newline=leading_newline,
            trailing_newline=trailing_newline,
            sudo=sudo,
        )

    @tool(
        name="file_str_replace",
        description="在文件中替换指定的字符串。用于更新文件中的特定内容或修复代码中的错误。",
        parameters={
            "filepath": {
                "type": "string",
                "description": "要执行替换操作的文件的绝对路径"
            },
            "old_str": {
                "type": "string",
                "description": "要被替换的原始字符串"
            },
            "new_str": {
                "type": "string",
                "description": "用于替换的新字符串"
            },
            "sudo": {
                "type": "boolean",
                "description": "(可选)是否使用 sudo 权限"
            }
        },
        required=["filepath", "old_str", "new_str"]
    )
    async def file_str_replace(
            self,
            filepath: str,
            old_str: str,
            new_str: str,
            sudo: Optional[bool] = False
    ) -> ToolResult:
        return await self.sandbox.file_replace(
            filepath=filepath,
            old_str=old_str,
            new_str=new_str,
            sudo=sudo,
        )

    @tool(
        name="file_find_in_content",
        description="在文件内容中搜索匹配的文本。用于查找文件中的特定内容或模式。",
        parameters={
            "filepath": {
                "type": "string",
                "description": "要进行搜索的文件的绝对路径"
            },
            "regex": {
                "type": "string",
                "description": "用于匹配的正则表达式模式"
            },
            "sudo": {
                "type": "boolean",
                "description": "(可选)是否使用 sudo 权限"
            }
        },
        required=["filepath", "regex"]
    )
    async def file_find_in_content(
            self,
            filepath: str,
            regex: str,
            sudo: Optional[bool] = False
    ) -> ToolResult:
        return await self.sandbox.file_search(
            filepath=filepath,
            regex=regex,
            sudo=sudo,
        )

    @tool(
        name="file_find_by_name",
        description="在指定目录中根据名称模式查找文件。用于定位具有特定命名模式的文件。",
        parameters={
            "dir_path": {
                "type": "string",
                "description": "要搜索的目录的绝对路径"
            },
            "glob_pattern": {
                "type": "string",
                "description": "使用 glob 语法通配符的文件名模式"
            }
        },
        required=["dir_path", "glob_pattern"]
    )
    async def file_find_by_name(
            self,
            dir_path: str,
            glob_pattern: str
    ) -> ToolResult:
        return await self.sandbox.file_find(
            dir_path=dir_path,
            glob_pattern=glob_pattern,
        )

    @tool(
        name="file_list",
        description="列出指定目录下的文件列表信息",
        parameters={
            "dir_path": {
                "type": "string",
                "description": "要列出文件列表的目录的绝对路径"
            },
        },
        required=["dir_path"]
    )
    async def file_list(self, dir_path: str) -> ToolResult:
        return await self.sandbox.file_list(dir_path)
