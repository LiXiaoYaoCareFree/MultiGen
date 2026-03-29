import asyncio
import io
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import List, AsyncGenerator, Callable, BinaryIO, Any, Optional, Dict, Tuple
from urllib.parse import urlparse

from fastapi import UploadFile
from pydantic import TypeAdapter

from app.domain.external.browser import Browser
from app.domain.external.file_storage import FileStorage
from app.domain.external.json_parser import JSONParser
from app.domain.external.llm import LLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.search import SearchEngine
from app.domain.external.task import TaskRunner, Task
from app.domain.models.app_config import AgentConfig, MCPConfig, A2AConfig
from app.domain.models.event import ErrorEvent, Event, MessageEvent, BaseEvent, ToolEvent, ToolEventStatus, \
    BrowserToolContent, SearchToolContent, ShellToolContent, FileToolContent, MCPToolContent, A2AToolContent, \
    TitleEvent, WaitEvent, DoneEvent
from app.domain.models.file import File
from app.domain.models.message import Message
from app.domain.models.search import SearchResults
from app.domain.models.session import SessionStatus
from app.domain.models.tool_result import ToolResult
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.flows.planner_react import PlannerReActFlow
from app.domain.services.tools.a2a import A2ATool
from app.domain.services.tools.mcp import MCPTool
from app.utils.session_error_logger import write_session_error_log
from core.config import get_settings

logger = logging.getLogger(__name__)


class AgentTaskRunner(TaskRunner):
    """基于Agent智能体的任务运行器"""

    def _is_transient_sandbox_error(self, e: Exception) -> bool:
        message = str(e)
        transient_signals = (
            "Sandbox Supervisor",
            "supervisor/status",
            "Could not resolve host",
            "Name or service not known",
            "Temporary failure in name resolution",
            "Connection refused",
            "ConnectError",
            "ReadTimeout",
            "ConnectTimeout",
            "Timeout",
            "Connection reset by peer",
            "Server disconnected",
        )
        return any(signal in message for signal in transient_signals)

    def _get_retry_sleep_seconds(self, attempt: int) -> int:
        schedule = (2, 4, 8, 15, 30)
        if attempt <= 0:
            return schedule[0]
        return schedule[min(attempt - 1, len(schedule) - 1)]

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],  # uow模块
            llm: LLM,  # 大语言模型
            agent_config: AgentConfig,  # 智能体配置
            mcp_config: MCPConfig,  # mcp配置
            a2a_config: A2AConfig,  # a2a配置
            session_id: str,  # 会话id
            file_storage: FileStorage,  # 文件存储桶
            json_parser: JSONParser,  # json解析器
            browser: Browser,  # 浏览器
            search_engine: SearchEngine,  # 搜索引擎
            sandbox: Sandbox,  # 沙箱
    ) -> None:
        """构造函数，完成Agent任务运行器的创建"""
        self._uow_factory = uow_factory
        self._uow = uow_factory()
        self._session_id = session_id
        self._sandbox = sandbox
        self._mcp_config = mcp_config
        self._mcp_tool = MCPTool()
        self._a2a_config = a2a_config
        self._a2a_tool = A2ATool()
        self._file_storage = file_storage
        self._api_base_dir = Path(__file__).resolve().parents[3]
        self._pending_generated_files: Dict[str, File] = {}
        self._browser = browser
        self._flow = PlannerReActFlow(
            uow_factory=uow_factory,
            llm=llm,
            agent_config=agent_config,
            session_id=session_id,
            json_parser=json_parser,
            browser=browser,
            sandbox=sandbox,
            search_engine=search_engine,
            mcp_tool=self._mcp_tool,
            a2a_tool=self._a2a_tool,
        )

    async def _put_and_add_event(self, task: Task, event: Event) -> None:
        """往指定任务的消息队列中添加事件"""
        # 1.往任务的输出消息队列中新增事件
        event_id = await task.output_stream.put(event.model_dump_json())
        event.id = event_id

        # 2.将事件添加到对应的会话中
        async with self._uow:
            await self._uow.session.add_event(self._session_id, event)

    @classmethod
    async def _pop_event(cls, task: Task) -> Tuple[Optional[str], Optional[str], Optional[Event]]:
        """从任务的输入流中获取事件信息"""
        # 1.从任务task中读取数据
        event_id, event_str = await task.input_stream.pop()
        if event_str is None:
            logger.warning(f"AgentTaskRunner接收到空消息")
            return None, None, None

        # 2.使用pydantic+type类型将字符串转换成事件
        event = TypeAdapter(Event).validate_json(event_str)
        event.id = event_id

        return event_id, event_str, event

    async def _sync_file_to_sandbox(self, file_id: str) -> File:
        """根据文件id将文件同步到沙箱中"""
        try:
            # 1.调用文件存储下载文件信息
            file_data, file = await self._file_storage.download_file(file_id)

            # 2.组装沙箱文件路径
            filepath = f"/home/ubuntu/upload/{file.filename}"

            # 3.调用沙箱将文件上传至沙箱
            tool_result = await self._sandbox.upload_file(
                file_data=file_data,
                filepath=filepath,
                filename=file.filename
            )

            # 4.判断是否上传成功
            if tool_result.success:
                file.filepath = filepath
                async with self._uow:
                    await self._uow.file.save(file)  # 可以更新也可以不更新
                return file
        except Exception as e:
            logger.exception(f"AgentTaskRunner同步文件[{file_id}]失败: {str(e)}")

    async def _sync_message_attachments_to_sandbox(self, event: MessageEvent) -> None:
        """将消息事件中的附件同步到沙箱中"""
        # 1.定义附件列表
        attachments: List[str] = []

        try:
            # 2.判断消息中是否存在附件
            if event.attachments:
                # 3.循环遍历所有的消息附件
                for attachment in event.attachments:
                    # 4.根据同步文件的id将数据同步到沙箱中
                    file = await self._sync_file_to_sandbox(attachment.id)

                    # 5.文件是否同步成功
                    if file:
                        attachments.append(file)
                        async with self._uow:
                            await self._uow.session.add_file(self._session_id, file)

            # 6.更新消息事件中的attachments
            event.attachments = attachments
        except Exception as e:
            logger.exception(f"AgentTaskRunner同步消息附件到沙箱失败: {str(e)}")

    @classmethod
    def _get_stream_size(cls, f: BinaryIO) -> int:
        """根据传递的文件流，获取计算文件的大小"""
        # 1.记录当前文件指针位置
        current_pos = f.tell()

        # 2.将指针移动到文件末尾, seek，0: 偏移量、2: 相对文件末尾
        f.seek(0, 2)

        # 3.获取当前位置，也就是文件大小
        size = f.tell()

        # 4.恢复指针到原始位置
        f.seek(current_pos)

        return size

    async def _sync_file_to_storage(self, filepath: str) -> File:
        """将沙箱中指定的文件路径数据同步到存储桶中"""
        try:
            # 1.根据文件路径从会话中查找文件数据
            async with self._uow:
                file = await self._uow.session.get_file_by_path(self._session_id, filepath)

            # 2.从沙箱中下载文件
            file_data = await self._sandbox.download_file(filepath)

            # 3.判断会话中的文件是否存在
            if file:
                async with self._uow:
                    await self._uow.session.remove_file(self._session_id, file.id)

            # 4.提取文件名字、文件信息并更新文件路径
            filename = filepath.split("/")[-1]
            upload_file = UploadFile(
                file=file_data,
                filename=filename,
                size=self._get_stream_size(file_data),
            )

            # 5.上传文件到文件存储桶
            file = await self._file_storage.upload_file(upload_file)
            file.filepath = filepath

            # 6.往会话中新增一个文件信息
            async with self._uow:
                await self._uow.session.add_file(self._session_id, file)
            return file
        except Exception as e:
            logger.exception(f"AgentTaskRunner同步消息附件到文件存储桶失败: {str(e)}")

    @staticmethod
    def _normalize_storage_path(value: str) -> Optional[str]:
        if not value:
            return None
        if value.startswith("/storage/"):
            return value
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            if parsed.path.startswith("/storage/"):
                return parsed.path
        return None

    def _extract_storage_paths(self, data: Any) -> List[str]:
        paths: List[str] = []
        if isinstance(data, dict):
            for value in data.values():
                paths.extend(self._extract_storage_paths(value))
        elif isinstance(data, list):
            for item in data:
                paths.extend(self._extract_storage_paths(item))
        elif isinstance(data, str):
            normalized = self._normalize_storage_path(data)
            if normalized:
                paths.append(normalized)
        return list(dict.fromkeys(paths))

    async def _sync_local_storage_file_to_storage(self, storage_path: str) -> Optional[File]:
        try:
            normalized = self._normalize_storage_path(storage_path)
            if not normalized:
                return None
            async with self._uow:
                existed = await self._uow.session.get_file_by_path(self._session_id, normalized)
            if existed:
                return existed
            local_path = self._api_base_dir / normalized.lstrip("/")
            if not local_path.exists() or not local_path.is_file():
                return None
            filename = local_path.name
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            data = local_path.read_bytes()
            upload_file = UploadFile(
                file=io.BytesIO(data),
                filename=filename,
                size=len(data),
                headers={"content-type": mime_type},
            )
            file = await self._file_storage.upload_file(upload_file)
            file.filepath = normalized
            async with self._uow:
                await self._uow.session.add_file(self._session_id, file)
            return file
        except Exception as e:
            logger.exception(f"AgentTaskRunner同步本地存储文件失败[{storage_path}]: {str(e)}")
            return None

    async def _sync_result_storage_files(self, result_data: Any) -> List[File]:
        files: List[File] = []
        for storage_path in self._extract_storage_paths(result_data):
            synced = await self._sync_local_storage_file_to_storage(storage_path)
            if synced:
                files.append(synced)
        return files

    def _remember_generated_files(self, files: List[File]) -> None:
        for file in files:
            if file and file.id:
                self._pending_generated_files[file.id] = file

    def _pop_pending_generated_files(self) -> List[File]:
        files = list(self._pending_generated_files.values())
        self._pending_generated_files.clear()
        return files

    async def _sync_message_attachments_to_storage(self, event: MessageEvent) -> None:
        """将消息事件的附件同步到文件存储桶中"""
        # 1.定义附件列表存储数据
        attachments: List[File] = []

        try:
            # 2.判断消息中是否存在附件
            if event.attachments:
                # 3.循环遍历所有附件
                for attachment in event.attachments:
                    if not attachment:
                        continue
                    filepath = getattr(attachment, "filepath", None) or ""
                    if filepath.startswith("/storage/"):
                        file = attachment
                        if not getattr(file, "id", None):
                            file = await self._sync_local_storage_file_to_storage(filepath)
                        elif not getattr(file, "key", None):
                            synced = await self._sync_local_storage_file_to_storage(filepath)
                            file = synced or file
                        if file:
                            attachments.append(file)
                        continue
                    if filepath:
                        file = await self._sync_file_to_storage(filepath)
                        if file:
                            attachments.append(file)

            # 5.更新时间中的附件列表资源
            event.attachments = attachments
        except Exception as e:
            logger.exception(f"AgentTaskRunner同步消息附件到存储桶失败: {str(e)}")

    async def _get_browser_screenshot(self) -> str:
        """获取浏览器截图并返回截图文件对应的在线URL"""
        # 1.调用浏览器完成截图
        screenshot = await self._browser.screenshot()

        # 2.将浏览器截图上传到文件存储中
        file = await self._file_storage.upload_file(UploadFile(
            file=io.BytesIO(screenshot),
            filename=f"{str(uuid.uuid4())}.png",
            # bugfix:添加size尺寸
            size=self._get_stream_size(io.BytesIO(screenshot)),
        ))

        # 3.获取setting并组装完整URL
        settings = get_settings()
        return f"https://{settings.cos_bucket}.cos.{settings.cos_region}.myqcloud.com/{file.key}"

    async def _handle_tool_event(self, event: ToolEvent) -> None:
        """额外处理工具消息，使其前端交互更友好"""
        try:
            # 1.如果事件状态为已调用则执行以下代码
            if event.status == ToolEventStatus.CALLED:
                # 2.工具为浏览器则补全工具浏览器工具内容
                if event.tool_name == "browser":
                    event.tool_content = BrowserToolContent(
                        screenshot=await self._get_browser_screenshot(),
                    )
                elif event.tool_name == "search":
                    # 3.工具为搜索则添加搜索工具内容
                    search_results: ToolResult[SearchResults] = event.function_result
                    logger.info(f"搜索工具结果: {search_results}")
                    event.tool_content = SearchToolContent(results=search_results.data.results)
                elif event.tool_name == "shell":
                    # 4.工具为shell则生成shell工具内容
                    if "session_id" in event.function_args:
                        shell_result = await self._sandbox.read_shell_output(
                            event.function_args["session_id"],
                            console=True,
                        )
                        event.tool_content = ShellToolContent(
                            console=(shell_result.data or {}).get("console_records", [])
                        )
                    else:
                        event.tool_content = ShellToolContent(console="(No console)")
                elif event.tool_name == "file":
                    # 5.工具为file则将文件同步到对象存储
                    if "filepath" in event.function_args:
                        filepath = event.function_args["filepath"]
                        file_read_result = await self._sandbox.read_file(filepath)
                        file_content: str = (file_read_result.data or {}).get("content", "")
                        event.tool_content = FileToolContent(content=file_content)
                        # bugfix:修改为同步文件到storage
                        await self._sync_file_to_storage(filepath)
                    else:
                        event.tool_content = FileToolContent(content="(No Content)")
                elif event.tool_name in ["mcp", "a2a"]:
                    # 6.工具为mcp/a2a则处理调用结果
                    logger.info(f"处理MCP/A2A工具事件, function_result: {event.function_result}")
                    if event.function_result:
                        # 7.如果结果包含data则提取data
                        if hasattr(event.function_result, "data") and event.function_result.data:
                            logger.info(f"MCP/A2A工具调用结果: {event.function_result.data}")
                            event.tool_content = MCPToolContent(result=event.function_result.data) \
                                if event.tool_name == "mcp" \
                                else A2AToolContent(a2a_result=event.function_result.data)
                        elif hasattr(event.function_result, "success") and event.function_result.success:
                            # 8.mcp/a2a工具调用正常，但是无结果产生
                            logger.info(f"MCP/A2A工具调用成功返回，但无结果: {event.function_result}")
                            result_data = event.function_result.model_dump() \
                                if hasattr(event.function_result, "model_dump") \
                                else str(event.function_result)
                            event.tool_content = MCPToolContent(result=result_data) \
                                if event.tool_name == "mcp" \
                                else A2AToolContent(a2a_result=result_data)
                        else:
                            # 9.其他情况将结果转换成字符串进行传递
                            logger.info(f"MCP/A2A工具额记过: {event.function_result}")
                            event.tool_content = MCPToolContent(result=str(event.function_result)) \
                                if event.tool_name == "mcp" \
                                else A2AToolContent(a2a_result=str(event.function_result))
                    else:
                        logger.warning("MCP/A2A工具调用结果未发现")
                        event.tool_content = MCPToolContent(result="(MCP工具无可用结果)") \
                            if event.tool_name == "mcp" \
                            else A2AToolContent(a2a_result="(A2A智能体无可用结果)")
                elif event.tool_name in [
                    "image_generation",
                    "volcano_image",
                    "volcano_video",
                    "video_concatenation",
                    "model_3d",
                    "virtual_anchor",
                    "qwen_tts",
                    "audio_mixing",
                ]:
                    result_payload: Any = None
                    if event.function_result and hasattr(event.function_result, "data"):
                        result_payload = event.function_result.data
                    elif event.function_result and hasattr(event.function_result, "model_dump"):
                        result_payload = event.function_result.model_dump()
                    else:
                        result_payload = "(多模态工具无可用结果)"
                    if event.function_result and hasattr(event.function_result, "success"):
                        base_payload: Dict[str, Any] = {
                            "success": bool(event.function_result.success),
                            "message": getattr(event.function_result, "message", "") or "",
                        }
                        if result_payload is not None:
                            base_payload["result"] = result_payload
                        result_payload = base_payload
                    synced_files = await self._sync_result_storage_files(result_payload)
                    if synced_files:
                        self._remember_generated_files(synced_files)
                        if isinstance(result_payload, dict):
                            result_payload = {
                                **result_payload,
                                "synced_files": [f.model_dump() for f in synced_files],
                            }
                        else:
                            result_payload = {
                                "result": result_payload,
                                "synced_files": [f.model_dump() for f in synced_files],
                            }
                    event.tool_content = MCPToolContent(result=result_payload)
        except Exception as e:
            logger.exception(f"AgentTaskRunner生成工具内容失败: {str(e)}")

    async def _run_flow(self, message: Message) -> AsyncGenerator[BaseEvent, None]:
        """根据消息对象运行PlannerReActFlow"""
        # 1.判断传递的消息是否为空
        if not message.message:
            logger.warning(f"AgentTaskRunner接收了一条空消息")
            yield ErrorEvent(error="空消息错误")
            return

        # 2.调用流并运行获取事件信息
        async for event in self._flow.invoke(message):
            # 3.判断是否为工具事件，如果是则额外处理
            if isinstance(event, ToolEvent):
                await self._handle_tool_event(event)
            elif isinstance(event, MessageEvent):
                if event.role == "assistant":
                    generated_files = self._pop_pending_generated_files()
                    if generated_files:
                        existed_map: Dict[str, File] = {}
                        if event.attachments:
                            for file in event.attachments:
                                if file and file.id:
                                    existed_map[file.id] = file
                        for file in generated_files:
                            existed_map[file.id] = file
                        event.attachments = list(existed_map.values())
                # 4.如果是消息事件则将AI消息事件中的附件同步到存储中
                await self._sync_message_attachments_to_storage(event)

            # 5.将事件直接返回
            yield event

    async def _cleanup_tools(self) -> None:
        """清理MCP和A2A工具资源，确保在同一任务上下文中释放

        注意：该方法必须在初始化MCP/A2A的同一个asyncio Task中调用，
        否则anyio的cancel scope会检测到任务上下文切换并抛出RuntimeError。
        """
        try:
            if self._mcp_tool:
                await self._mcp_tool.cleanup()
        except Exception as e:
            logger.warning(f"清理MCP工具资源时出错: {e}")
        try:
            if self._a2a_tool:
                await self._a2a_tool.manager.cleanup()
        except Exception as e:
            logger.warning(f"清理A2A工具资源时出错: {e}")

    async def invoke(self, task: Task) -> None:
        """根据传递的任务处理agent消息队列并运行agent流"""
        try:
            # 1.确保沙箱、mcp、a2a均初始化完成
            logger.info(f"AgentTaskRunner任务处理开始")
            loop = asyncio.get_running_loop()
            degrade_started_at = loop.time()
            init_attempt = 0

            while True:
                try:
                    await self._sandbox.ensure_sandbox()
                    await self._mcp_tool.initialize(self._mcp_config)
                    await self._a2a_tool.initialize(self._a2a_config)
                    break
                except Exception as e:
                    init_attempt += 1
                    if self._is_transient_sandbox_error(e) and loop.time() - degrade_started_at < 600:
                        if init_attempt == 1 or init_attempt % 5 == 0:
                            await self._put_and_add_event(
                                task,
                                MessageEvent(role="assistant", message="沙箱暂不可用，正在自动恢复并重试…"),
                            )
                        await asyncio.sleep(self._get_retry_sleep_seconds(init_attempt))
                        continue
                    raise

            # 2.循环读取任务中的输入消息队列
            while not await task.input_stream.is_empty():
                # 3.从输入流中获取数据
                original_event_id, original_event_str, event = await self._pop_event(task)
                if event is None:
                    continue
                message = ""

                # 4.判断事件类型是否为消息事件，如果是则处理消息并将附件同步到沙箱中
                if isinstance(event, MessageEvent):
                    message = event.message or ""
                    await self._sync_message_attachments_to_sandbox(event)
                    logger.info(f"AgentTaskRunner接收到新消息: {message[:50]}...")

                # 5.将消息事件转换称消息对象
                message_obj = Message(
                    message=message,
                    attachments=[attachment.filepath for attachment in event.attachments]
                )

                # 6.传递消息对象并运行PlannerReActFlow
                message_attempt = 0
                while True:
                    try:
                        async for event in self._run_flow(message_obj):
                            await self._put_and_add_event(task, event)

                            if isinstance(event, TitleEvent):
                                async with self._uow:
                                    await self._uow.session.update_title(self._session_id, event.title)
                            elif isinstance(event, MessageEvent):
                                async with self._uow:
                                    await self._uow.session.update_latest_message(
                                        self._session_id,
                                        event.message,
                                        event.created_at,
                                    )
                                    await self._uow.session.increment_unread_message_count(self._session_id)
                            elif isinstance(event, WaitEvent):
                                async with self._uow:
                                    await self._uow.session.update_status(self._session_id, SessionStatus.WAITING)
                                return

                            if not await task.input_stream.is_empty():
                                break
                        break
                    except Exception as e:
                        message_attempt += 1
                        if self._is_transient_sandbox_error(e) and message_attempt <= 20 and original_event_str:
                            await task.input_stream.put(original_event_str)
                            if message_attempt == 1 or message_attempt % 5 == 0:
                                await self._put_and_add_event(
                                    task,
                                    MessageEvent(role="assistant", message="沙箱短暂不可用，任务已进入重试队列并将自动继续…"),
                                )
                            await asyncio.sleep(self._get_retry_sleep_seconds(message_attempt))
                            break
                        raise

            # 12.更新会话状态为已完成
            async with self._uow:
                await self._uow.session.update_status(self._session_id, SessionStatus.COMPLETED)
        except asyncio.CancelledError:
            # 13.异步任务被取消，推送结束事件并跟新状态
            logger.info(f"AgentTaskRunner任务运行取消")
            await self._put_and_add_event(task, DoneEvent())
            async with self._uow:
                await self._uow.session.update_status(self._session_id, SessionStatus.COMPLETED)
            raise
        except Exception as e:
            # 14.记录日志并往任务队列/消息队列中写入异常事件并更新会话状态
            logger.exception(f"AgentTaskRunner运行出错: {str(e)}")

            # 记录错误到文件日志
            try:
                session_title = None
                async with self._uow:
                    session = await self._uow.session.get_by_id(self._session_id)
                    if session:
                        session_title = session.title
                if session_title:
                    import traceback
                    write_session_error_log(
                        session_title=session_title,
                        error_type="AgentTaskRunner",
                        error_message=str(e),
                        stack_trace=traceback.format_exc()
                    )
            except Exception:
                pass

            await self._put_and_add_event(task, ErrorEvent(error=f"AgentTaskRunner出错: {str(e)}"))
            async with self._uow:
                await self._uow.session.update_status(self._session_id, SessionStatus.COMPLETED)
        finally:
            # 15.在同一个asyncio Task上下文中清理MCP/A2A工具资源
            # 这是关键：streamablehttp_client内部使用anyio.create_task_group()，
            # 要求在同一个Task中进入和退出cancel scope，
            # 所以必须在invoke()的finally块（即初始化MCP的同一个Task）中清理
            await self._cleanup_tools()

    async def destroy(self) -> None:
        """销毁任务运行器并释放资源"""
        # 1.清除沙箱
        logger.info(f"开始清除销毁AgentTaskRunner资源")
        if self._sandbox:
            logger.info("销毁AgentTaskRunner中的沙箱环境")
            await self._sandbox.destroy()

        # 2.清除mcp和a2a工具（幂等操作，如果invoke()中已清理则不会重复执行）
        await self._cleanup_tools()

    async def on_done(self, task: Task) -> None:
        """任务结束时执行的回调函数"""
        logger.info(f"AgentTaskRunner任务执行结束")
