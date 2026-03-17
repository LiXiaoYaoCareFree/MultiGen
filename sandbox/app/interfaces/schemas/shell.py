from typing import Optional

from pydantic import BaseModel, Field


class ShellExecuteRequest(BaseModel):
    """执行命令请求结构体"""
    session_id: Optional[str] = Field(default=None, description="目标 Shell 会话的唯一标识符")
    exec_dir: Optional[str] = Field(default=None, description="执行命令的工作目录(必须使用绝对路径)")
    command: str = Field(..., description="要执行的 Shell 命令")


class ShellReadRequest(BaseModel):
    """查看Shell执行内容请求结构体"""
    session_id: str = Field(..., description="目标 Shell 会话的唯一标识符")
    console: Optional[bool] = Field(default=None, description="是否返回控制台记录列表")


class ShellWaitRequest(BaseModel):
    """等待Shell命令执行请求结构体"""
    session_id: str = Field(..., description="目标 Shell 会话的唯一标识符")
    seconds: Optional[int] = Field(default=None, description="等待时间, 单位为秒")


class ShellWriteRequest(BaseModel):
    """写入数据到子进程请求结构体"""
    session_id: str = Field(..., description="目标 Shell 会话的唯一标识符")
    input_text: str = Field(..., description="需要写入的内容文本")
    press_enter: bool = Field(default=True, description="是否按下回车键")


class ShellKillRequest(BaseModel):
    """关闭进程请求结构体"""
    session_id: str = Field(..., description="目标 Shell 会话的唯一标识符")
