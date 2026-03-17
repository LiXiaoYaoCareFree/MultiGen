import asyncio
import codecs
import getpass
import logging
import os.path
import re
import socket
import uuid
from typing import Dict, Optional, List

from app.interfaces.errors.exceptions import (
    BadRequestException,
    AppException,
    NotFoundException,
)
from app.models.shell import (
    Shell,
    ConsoleRecord,
    ShellWaitResult,
    ShellWriteResult,
    ShellKillResult, ShellReadResult, ShellExecuteResult,
)

logger = logging.getLogger(__name__)


class ShellService:
    """Shell命令服务"""
    active_shells: Dict[str, Shell]

    def __init__(self) -> None:
        self.active_shells = {}

    @classmethod
    def _get_display_path(cls, path: str) -> str:
        """获取显示路径，将~替换成用户主目录"""
        # 1.使用程序获取跨平台下用户的主目录
        home_dir = os.path.expanduser("~")
        logger.debug(f"主目录: {home_dir}, 路径: {path}")

        # 2.判断传递进来的路径是否是主路径，如果是则替换成~
        if path.startswith(home_dir):
            return path.replace(home_dir, "~", 1)
        return path

    def _format_ps1(self, exec_dir: str) -> str:
        """格式化命令结构提示，增强交互体验，例如: root@myserver:/var/log $"""
        username = getpass.getuser()
        hostname = socket.gethostname()
        display_dir = self._get_display_path(exec_dir)
        return f"{username}@{hostname}:{display_dir} $"

    @classmethod
    async def _create_process(cls, exec_dir: str, command: str) -> asyncio.subprocess.Process:
        """根据传递的执行目录+命令创建一个asyncio管理的子进程"""
        # 1.ubuntu系统统一使用/bin/bash这个解释器
        logger.debug(f"在目录 {exec_dir} 下使用命令 {command} 创建一个子进程")
        shell_exec = "/bin/bash"

        # 3.创建一个系统级的子进程用来执行shell命令
        return await asyncio.create_subprocess_shell(
            command,  # 要执行的命令
            executable=shell_exec,  # 执行解释器
            cwd=exec_dir,
            stdout=asyncio.subprocess.PIPE,  # 创建管道以捕获标准输出
            stderr=asyncio.subprocess.STDOUT,  # 将标准错误重定向到标准输出流
            stdin=asyncio.subprocess.PIPE,  # 创建管道以允许标准输入
            limit=1024 * 1024,  # 设置缓冲区大小并限制为1MB
        )

    async def _start_output_reader(self, session_id: str, process: asyncio.subprocess.Process) -> None:
        """启动协程以连续读取进程输出并将其存储到会话中"""
        # 1.ubuntu系统统一使用utf-8编码
        logger.debug(f"正在启用会话输出读取器: {session_id}")
        encoding = "utf-8"

        # 2.创建增量编码器（解决字符被切断的问题）
        decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        shell = self.active_shells.get(session_id)

        while True:
            # 3.判断子进程是否有标准输出管道
            if process.stdout:
                try:
                    # 4.读取缓存区的数据，假设一次读取4096
                    buffer = await process.stdout.read(4096)
                    if not buffer:
                        break

                    # 5.使用编码器进行编码，同时设置final=False标识未结束
                    output = decoder.decode(buffer, final=False)

                    # 6.判断会话是否存在
                    if shell:
                        # 7.更新会话输出和控制台记录
                        shell.output += output
                        if shell.console_records:
                            shell.console_records[-1].output += output
                except Exception as e:
                    logger.error(f"读取进程输出时错误: {str(e)}")
                    break
            else:
                break

        logger.debug(f"会话 {session_id} 的输出读取器已完成")

    @classmethod
    def _remove_ansi_escape_codes(cls, text: str) -> str:
        """从文本中删除ANSI转义字符"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub("", text)

    @classmethod
    def create_session_id(cls) -> str:
        """创建会话id，使用uuid4生成唯一值"""
        session_id = str(uuid.uuid4())
        logger.info(f"创建一个新的Shell会话ID: {session_id}")
        return session_id

    def get_console_records(self, session_id: str) -> List[ConsoleRecord]:
        """从指定会话中获取控制台记录"""
        # 1.判断下传递的会话是否存在
        logger.debug(f"正在获取Shell会话的控制台记录: {session_id}")
        if session_id not in self.active_shells:
            logger.error(f"Shell会话不存在: {session_id}")
            raise NotFoundException(f"Shell会话不存在: {session_id}")

        # 2.获取原始的控制台记录列表
        console_records = self.active_shells[session_id].console_records
        clean_console_records = []

        # 3.执行循环处理所有记录输出
        for console_record in console_records:
            clean_console_records.append(ConsoleRecord(
                ps1=console_record.ps1,
                command=console_record.command,
                output=self._remove_ansi_escape_codes(console_record.output),
            ))

        return clean_console_records

    async def wait_process(self, session_id: str, seconds: Optional[int] = None) -> ShellWaitResult:
        """传递会话id+时间，等待子进程结束"""
        # 1.判断下传递的会话是否存在
        logger.debug(f"正在Shell会话中等待进程: {session_id}, 超时: {seconds}s")
        if session_id not in self.active_shells:
            logger.error(f"Shell会话不存在: {session_id}")
            raise NotFoundException(f"Shell会话不存在: {session_id}")

        # 2.获取会话和子进程
        shell = self.active_shells[session_id]
        process = shell.process

        try:
            # 3.判断是否设置seconds
            seconds = 60 if seconds is None or seconds <= 0 else seconds
            await asyncio.wait_for(process.wait(), timeout=seconds)

            # 4.记录日志并返回等待结果
            logger.info(f"进程已完成, 返回代码为: {process.returncode}")
            return ShellWaitResult(returncode=process.returncode)
        except asyncio.TimeoutError:
            # 记录日志并抛出BadRequest异常
            logger.warning(f"Shell会话进程等待超时: {seconds}s")
            raise BadRequestException(f"Shell会话进程等待超时: {seconds}s")
        except Exception as e:
            # 记录日志并抛出AppException
            logger.error(f"Shell会话进程等待过程出错: {str(e)}")
            raise AppException(f"Shell会话进程等待过程出错: {str(e)}")

    async def read_shell_output(self, session_id: str, console: bool = False) -> ShellReadResult:
        """根据传递的会话id+是否输出控制台记录获取Shell命令结果"""
        # 1.判断下传递的会话是否存在
        logger.debug(f"查看Shell会话内容: {session_id}")
        if session_id not in self.active_shells:
            logger.error(f"Shell会话不存在: {session_id}")
            raise NotFoundException(f"Shell会话不存在: {session_id}")

        # 2.获取会话
        shell = self.active_shells[session_id]

        # 3.获取原生输出并移除额外字符
        raw_output = shell.output
        clean_output = self._remove_ansi_escape_codes(raw_output)

        # 4.判断是否获取控制台记录
        if console:
            console_records = self.get_console_records(session_id)
        else:
            console_records = []

        return ShellReadResult(
            session_id=session_id,
            output=clean_output,
            console_records=console_records,
        )

    async def exec_command(
            self,
            session_id: str,
            exec_dir: Optional[str],
            command: str,
    ) -> ShellExecuteResult:
        """传递会话id+执行目录+命令在沙箱中执行后返回"""
        # 1.记录日志并判断执行目录是否存在
        logger.info(f"正在会话 {session_id} 中执行命令: {command}")
        if not exec_dir or exec_dir == "":
            exec_dir = os.path.expanduser("~")
        if not os.path.exists(exec_dir):
            logger.error(f"当前目录不存在: {exec_dir}")
            raise BadRequestException(f"当前目录不存在: {exec_dir}")

        try:
            # 2.格式化生成ps1格式
            ps1 = self._format_ps1(exec_dir)

            # 3.判断当前Shell会话是否存在
            if session_id not in self.active_shells:
                # 4.创建一个新的进程
                logger.debug(f"创建一个新的Shell会话: {session_id}")
                process = await self._create_process(exec_dir, command)
                self.active_shells[session_id] = Shell(
                    process=process,
                    exec_dir=exec_dir,
                    output="",
                    console_records=[ConsoleRecord(ps1=ps1, command=command, output="")],
                )

                # 5.创建后台任务来运行输出读取器
                await asyncio.create_task(self._start_output_reader(session_id, process))
            else:
                # 6.该会话已存在则读取数据
                logger.debug(f"使用现有的Shell会话: {session_id}")
                shell = self.active_shells[session_id]
                old_process = shell.process

                # 7.判断旧进程是否还在运行，如果是则先停止旧进程在执行新命令
                if old_process.returncode is None:
                    logger.debug(f"正在终止会话中的上一个进程: {session_id}")
                    try:
                        # 8.结束旧进程并优雅等待1s
                        old_process.terminate()
                        await asyncio.wait_for(old_process.wait(), timeout=1)
                    except Exception as e:
                        # 9.结束旧进程出现错误并记录日志调用kill强制关闭进程
                        logger.warning(f"强制终止Shell会话中的进程 {session_id} 失败: {str(e)}")
                        old_process.kill()

                # 10.关闭之后创建一个新的进程
                process = await self._create_process(exec_dir, command)

                # 11.更新会话信息
                shell.process = process
                shell.exec_dir = exec_dir
                shell.output = ""
                shell.console_records.append(ConsoleRecord(ps1=ps1, command=command, output=""))

                # 12.创建后台任务来运行输出读取器
                await asyncio.create_task(self._start_output_reader(session_id, process))

            try:

                # 13.尝试等待子进程执行(最多等待5s)
                logger.debug(f"正在等待会话中的进程完成: {session_id}")
                wait_result = await self.wait_process(session_id, seconds=5)

                # 14.判断返回代码是否非空(已结束)则同步返回执行结果
                if wait_result.returncode is not None:
                    # 15.记录日志并查看结果
                    logger.debug(f"Shell会话进程已结束, 代码: {wait_result.returncode}")
                    view_result = await self.read_shell_output(session_id)

                    return ShellExecuteResult(
                        session_id=session_id,
                        command=command,
                        status="completed",
                        returncode=wait_result.returncode,
                        output=view_result.output,
                    )
            except BadRequestException as _:
                # 16.等待超时，记录日志不做额外处理让命令在后台继续运行
                logger.warning(f"进程在会话超时后仍在运行: {session_id}")
                pass
            except Exception as e:
                # 17.其他异常忽略并让程序继续进行
                logger.warning(f"等待进程时出现异常: {str(e)}")
                pass

            # 18.返回正在等待Shell执行结果
            return ShellExecuteResult(
                session_id=session_id,
                command=command,
                status="running",
            )
        except Exception as e:
            # 19.执行过程中出现异常并记录日志后返回自定义异常
            logger.error(f"命令执行失败: {str(e)}", exc_info=True)
            raise AppException(
                msg=f"命令执行失败: {str(e)}",
                data={"session_id": session_id, "command": command}
            )

    async def write_shell_input(
            self,
            session_id: str,
            input_text: str,
            press_enter: bool
    ) -> ShellWriteResult:
        """根据传递的数据向指定子进程写入数据"""
        # 1.判断下传递的会话是否存在
        logger.debug(f"写入Shell会话中的子进程: {session_id}, 是否按下回车键: {press_enter}")
        if session_id not in self.active_shells:
            logger.error(f"Shell会话不存在: {session_id}")
            raise NotFoundException(f"Shell会话不存在: {session_id}")

        # 2.获取会话和子进程
        shell = self.active_shells[session_id]
        process = shell.process

        try:
            # 3.检查子进程是否结束
            if process.returncode is not None:
                logger.error(f"子进程已结束, 无法写入输入: {session_id}")
                raise BadRequestException("子进程已结束, 无法写入输入")

            # 4.ubuntu系统统一使用utf-8与\n
            encoding = "utf-8"
            line_ending = "\n"

            # 5.准备要发送的内容
            text_to_send = input_text
            if press_enter:
                text_to_send += line_ending

            # 6.将字符串编码为字节流(发送给进程使用)
            input_data = text_to_send.encode(encoding)

            # 7.记录日志/输出(直接使用原始字符串，不从input_data编码，避免编码不统一的情况)
            log_text = input_text + ("\n" if press_enter else "")
            shell.output += log_text
            if shell.console_records:
                shell.console_records[-1].output += log_text

            # 8.向子进程写入数据
            process.stdin.write(input_data)
            await process.stdin.drain()

            # 9.记录日志并返回写入结果
            logger.info("成功向子进程写入数据")
            return ShellWriteResult(status="success")
        except UnicodeError as e:
            # 10.捕获编码异常
            logger.error(f"编码错误: {str(e)}")
            raise AppException(f"编码错误: {str(e)}")
        except Exception as e:
            # 11.捕获通用异常
            logger.error(f"向子进程写入数据出错: {str(e)}")
            raise AppException(f"向子进程写入数据出错: {str(e)}")

    async def kill_process(self, session_id: str) -> ShellKillResult:
        """根据传递的Shell会话id关闭对应进程"""
        # 1.判断下传递的会话是否存在
        logger.debug(f"正在终止会话中的进程: {session_id}")
        if session_id not in self.active_shells:
            logger.error(f"Shell会话不存在: {session_id}")
            raise NotFoundException(f"Shell会话不存在: {session_id}")

        # 2.获取会话和子进程
        shell = self.active_shells[session_id]
        process = shell.process

        try:
            # 3.检查子进程是否还在运行
            if process.returncode is None:
                # 4.记录日志并尝试先优雅的关闭
                logger.info(f"尝试优雅终止进程: {session_id}")
                process.terminate()

                try:
                    # 5.等待3秒时间
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError as _:
                    # 6.优雅关闭失败，则强制关闭
                    logger.warning(f"尝试强制关闭进程: {session_id}")
                    process.kill()

                # 7.记录日志并返回关闭结果
                logger.info(f"进程已终止, 返回代码为: {process.returncode}")
                return ShellKillResult(status="terminated", returncode=process.returncode)
            else:
                # 8.进程已结束无需重复关闭
                logger.info(f"进程已终止, 返回代码为: {process.returncode}")
                return ShellKillResult(status="already_terminated", returncode=process.returncode)
        except Exception as e:
            # 9.记录日志并抛出异常
            logger.error(f"关闭进程失败: {str(e)}", exc_info=True)
            raise AppException(f"关闭进程失败: {str(e)}")
