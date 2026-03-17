import os

from fastapi import APIRouter, Depends

from app.interfaces.errors.exceptions import BadRequestException
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.shell import ShellExecuteRequest, ShellReadRequest, ShellWaitRequest, ShellWriteRequest, \
    ShellKillRequest
from app.interfaces.service_dependencies import get_shell_service
from app.models.shell import (
    ShellWaitResult,
    ShellWriteResult,
    ShellKillResult, ShellExecuteResult, ShellReadResult,
)
from app.services.shell import ShellService

router = APIRouter(prefix="/shell", tags=["Shell模块"])


@router.post(
    path="/exec-command",
    response_model=Response[ShellExecuteResult],
)
async def exec_command(
        request: ShellExecuteRequest,
        shell_service: ShellService = Depends(get_shell_service),
) -> Response[ShellExecuteResult]:
    """在指定的Shell会话中运行命令"""
    # 1.判断下是否传递了session_id，如果不存在则新建一个session_id
    if not request.session_id or request.session_id == "":
        request.session_id = shell_service.create_session_id()

    # 2.判断下是否传递了执行目录，如果未传递则使用根目录作为执行路径
    if not request.exec_dir or request.exec_dir == "":
        request.exec_dir = os.path.expanduser("~")

    # 3.调用服务执行命令获取结果
    result = await shell_service.exec_command(
        session_id=request.session_id,
        exec_dir=request.exec_dir,
        command=request.command,
    )

    return Response.success(data=result)


@router.post(
    path="/read-shell-output",
    response_model=Response[ShellReadResult]
)
async def read_shell_output(
        request: ShellReadRequest,
        shell_service: ShellService = Depends(get_shell_service),
) -> Response[ShellReadResult]:
    """根据传递的会话id+是否返回控制台标识获取Shell命令执行结果"""
    # 1.判断下Shell会话id是否存在
    if not request.session_id or request.session_id == "":
        raise BadRequestException("Shell会话ID为空, 请核实后重试")

    # 2.调用服务获取命令执行结果
    result = await shell_service.read_shell_output(request.session_id, request.console)

    return Response.success(data=result)


@router.post(
    path="/wait-process",
    response_model=Response[ShellWaitResult],
)
async def wait_process(
        request: ShellWaitRequest,
        shell_service: ShellService = Depends(get_shell_service),
) -> Response[ShellWaitResult]:
    """传递会话id+描述执行等待并获取等待结果"""
    # 1.判断下Shell会话id是否存在
    if not request.session_id or request.session_id == "":
        raise BadRequestException("Shell会话ID为空, 请核实后重试")

    # 2.调用服务等待子进程
    result = await shell_service.wait_process(request.session_id, request.seconds)

    return Response.success(
        msg=f"进程结束, 返回状态码(returncode): {result.returncode}",
        data=result,
    )


@router.post(
    path="/write-shell-input",
    response_model=Response[ShellWriteResult],
)
async def write_shell_input(
        request: ShellWriteRequest,
        shell_service: ShellService = Depends(get_shell_service),
) -> Response[ShellWriteResult]:
    """根据传递的会话+写入内容+按下回车标识向指定子进程写入数据"""
    # 1.判断下Shell会话id是否存在
    if not request.session_id or request.session_id == "":
        raise BadRequestException("Shell会话ID为空, 请核实后重试")

    # 2.调用服务向子进程写入数据
    result = await shell_service.write_shell_input(
        session_id=request.session_id,
        input_text=request.input_text,
        press_enter=request.press_enter,
    )

    return Response.success(
        msg="向进程写入数据成功",
        data=result,
    )


@router.post(
    path="/kill-process",
    response_model=Response[ShellKillResult],
)
async def kill_process(
        request: ShellKillRequest,
        shell_service: ShellService = Depends(get_shell_service),
) -> Response[ShellKillResult]:
    """传递Shell会话id关闭指定会话"""
    # 1.判断下Shell会话id是否存在
    if not request.session_id or request.session_id == "":
        raise BadRequestException("Shell会话ID为空, 请核实后重试")

    # 2.调用服务关闭Shell会话
    result = await shell_service.kill_process(request.session_id)

    return Response.success(
        msg="进程终止" if result.status == "terminated" else "进程已结束",
        data=result,
    )
