import asyncio
import logging
import uuid
from typing import Optional, Dict

from app.domain.external.message_queue import MessageQueue
from app.domain.external.task import Task, TaskRunner
from app.infrastructure.external.message_queue.redis_stream_message_queue import RedisStreamMessageQueue

logger = logging.getLogger(__name__)


class RedisStreamTask(Task):
    """基于Redis流的任务类"""

    # 定义一个全局变量用于存储所有已注册的任务
    _task_registry: Dict[str, "RedisStreamTask"] = {}

    def __init__(self, task_runner: TaskRunner) -> None:
        """构造函数，传递任务运行器完成Task初始化"""
        self._task_runner = task_runner
        self._id = str(uuid.uuid4())
        self._execution_task: Optional[asyncio.Task] = None  # 定义在后台执行的任务

        input_stream_name = f"task:input:{self._id}"
        output_stream_name = f"task:output:{self._id}"

        self._input_stream = RedisStreamMessageQueue(input_stream_name)
        self._output_stream = RedisStreamMessageQueue(output_stream_name)

        # 将当前类实例注册到全局变量中
        RedisStreamTask._task_registry[self._id] = self

    def _cleanup_registry(self) -> None:
        """清除类全局变量中当前注册的任务"""
        if self._id in RedisStreamTask._task_registry:
            del RedisStreamTask._task_registry[self._id]
            logger.info(f"任务[{self._id}]从注册中心移除")

    def _on_task_done(self) -> None:
        """任务结束时的回调函数"""
        # 1.检测task_runner是否存在，如果存在则调用task_runner的回调函数
        if self._task_runner:
            asyncio.create_task(self._task_runner.on_done(self))

        # 2.清除当前任务对应的资源
        self._cleanup_registry()

    async def _execute_task(self) -> None:
        """使用TaskRunner执行任务"""
        try:
            await self._task_runner.invoke(self)
        except asyncio.CancelledError:
            logger.info(f"任务[{self._id}]执行被取消")
            raise
        except Exception as e:
            logger.error(f"任务[{self._id}]执行出现异常: {str(e)}")
        finally:
            self._on_task_done()

    async def invoke(self) -> None:
        """使用提供的task_runner来运行任务"""
        if self.done:
            self._execution_task = asyncio.create_task(self._execute_task())
            logger.info(f"任务[{self._id}]开始执行")

    def cancel(self) -> bool:
        """取消当前执行的任务"""
        if not self.done:
            # 1.取消任务
            self._execution_task.cancel()
            logger.info(f"任务[{self._id}]已取消")

            # 2.清除注册的当前任务
            self._cleanup_registry()
            return True

        # 3.否则代表任务已结束，无需重复取消
        self._cleanup_registry()
        return True

    @property
    def input_stream(self) -> MessageQueue:
        return self._input_stream

    @property
    def output_stream(self) -> MessageQueue:
        return self._output_stream

    @property
    def id(self) -> str:
        return self._id

    @property
    def done(self) -> bool:
        if self._execution_task is None:
            return True
        return self._execution_task.done()

    @classmethod
    def get(cls, task_id: str) -> Optional["Task"]:
        return RedisStreamTask._task_registry.get(task_id)

    @classmethod
    def create(cls, task_runner: TaskRunner) -> "Task":
        return cls(task_runner)

    @classmethod
    async def destroy(cls) -> None:
        for task_id in RedisStreamTask._task_registry:
            # 1.获取对应的任务
            task = RedisStreamTask._task_registry[task_id]
            task.cancel()

            # 2.检测任务是否有任务运行器
            if task._task_runner:
                await task._task_runner.destroy()

        # 3.清除全局变量
        cls._task_registry.clear()
