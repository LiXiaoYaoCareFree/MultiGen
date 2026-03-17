import asyncio.subprocess
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class ConsoleRecord(BaseModel):
    """Shell命令行控制台记录"""
    ps1: str = Field(..., description="ps1")
    command: str = Field(..., description="执行命令")
    output: str = Field(default="", description="输出内容")


class Shell(BaseModel):
    """Shell会话模型"""
    process: asyncio.subprocess.Process = Field(..., description="会话中的子进程")
    exec_dir: str = Field(..., description="会话执行目录")
    output: str = Field(..., description="会话输出")
    console_records: List[ConsoleRecord] = Field(default_factory=list, description="Shell会话中的控制记录列表")

    # pydantic v2提供的写法，如果是v1可以通过创建一个内部类，名字为Config来解决
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # 允许Python原生对象或者自定义的对象作为字段类型
    )


class ShellWaitResult(BaseModel):
    """会话等待结果模型"""
    returncode: int = Field(..., description="子进程返回代码")


class ShellReadResult(BaseModel):
    """Shell命令结果模型"""
    session_id: str = Field(..., description="Shell会话id")
    output: str = Field(..., description="Shell会话输出内容")
    console_records: List[ConsoleRecord] = Field(default_factory=list, description="控制台记录")


class ShellExecuteResult(BaseModel):
    """Shell命令执行结果"""
    session_id: str = Field(..., description="Shell会话id")
    command: str = Field(..., description="执行命令")
    status: str = Field(..., description="命令执行状态")
    returncode: Optional[int] = Field(default=None, description="进程返回代码，只有进程结束时才有值")
    output: Optional[str] = Field(default=None, description="进程执行结果，只有进程结束时才有值")


class ShellWriteResult(BaseModel):
    """Shell命令写入结果模型"""
    status: str = Field(..., description="写入状态")


class ShellKillResult(BaseModel):
    """Shell命令关闭结果"""
    status: str = Field(..., description="进程状态")
    returncode: int = Field(..., description="进程返回状态")
