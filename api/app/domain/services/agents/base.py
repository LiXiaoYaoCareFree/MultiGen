import asyncio
import difflib
import json
import logging
import math
import re
import uuid
from abc import ABC
from typing import Optional, List, AsyncGenerator, Dict, Any, Callable

from app.domain.external.json_parser import JSONParser
from app.domain.external.llm import LLM
from app.domain.models.app_config import AgentConfig
from app.domain.models.event import ToolEvent, ToolEventStatus, ErrorEvent, MessageEvent, BaseEvent
from app.domain.models.memory import Memory
from app.domain.models.message import Message
from app.domain.models.tool_result import ToolResult
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.tools.base import BaseTool

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础Agent智能体"""
    name: str = ""  # 智能体名字
    _system_prompt: str = ""  # 系统预设prompt
    _format: Optional[str] = None  # Agent的响应格式
    _retry_interval: float = 1.0  # 重试间隔
    _tool_choice: Optional[str] = None  # 强制选择工具
    _summary_prefix: str = "[历史摘要]"
    _deepseek_reasoning_models = {"deepseek-v4-pro", "deepseek-v4-flash"}

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            session_id: str,  # 会话id
            agent_config: AgentConfig,  # Agent配置
            llm: LLM,  # 语言模型协议
            json_parser: JSONParser,  # JSON输出解析器
            tools: List[BaseTool],  # 工具列表
    ) -> None:
        """构造函数，完成Agent的初始化"""
        self._uow_factory = uow_factory
        self._uow = uow_factory()
        self._session_id = session_id
        self._agent_config = agent_config
        self._llm = llm
        self._max_prompt_tokens = max(16800, int(getattr(llm, "max_prompt_tokens", 1000000)))
        self._memory: Optional[Memory] = None
        self._json_parser = json_parser
        self._tools = tools

    async def _ensure_memory(self) -> None:
        """确保智能体记忆是存在的"""
        if self._memory is None:
            async with self._uow:
                self._memory = await self._uow.session.get_memory(self._session_id, self.name)

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """获取Agent所有可用的工具列表参数声明/Schema"""
        available_tools = []
        for tool in self._tools:
            available_tools.extend(tool.get_tools())
        return available_tools

    def _get_tool(self, tool_name: str) -> BaseTool:
        tool, _ = self._resolve_tool(tool_name)
        return tool

    @staticmethod
    def _normalize_tool_name(tool_name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", (tool_name or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    def _list_available_tool_names(self) -> List[str]:
        names: List[str] = []
        for tool in self._tools:
            for schema in tool.get_tools():
                function = schema.get("function") if isinstance(schema, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                if isinstance(name, str) and name:
                    names.append(name)
        return names

    def _resolve_tool(self, tool_name: str) -> tuple[BaseTool, str]:
        for tool in self._tools:
            if tool.has_tool(tool_name):
                return tool, tool_name

        available_names = self._list_available_tool_names()
        normalized_target = self._normalize_tool_name(tool_name)
        normalized_map: Dict[str, List[str]] = {}
        for candidate in available_names:
            normalized_map.setdefault(self._normalize_tool_name(candidate), []).append(candidate)

        normalized_candidates = normalized_map.get(normalized_target, [])
        if len(normalized_candidates) == 1:
            corrected_name = normalized_candidates[0]
            for tool in self._tools:
                if tool.has_tool(corrected_name):
                    logger.warning(f"工具名自动纠正: {tool_name} -> {corrected_name}")
                    return tool, corrected_name

        close_matches = difflib.get_close_matches(
            normalized_target,
            list(normalized_map.keys()),
            n=1,
            cutoff=0.88,
        )
        if close_matches:
            corrected_name = normalized_map[close_matches[0]][0]
            for tool in self._tools:
                if tool.has_tool(corrected_name):
                    logger.warning(f"工具名近似纠正: {tool_name} -> {corrected_name}")
                    return tool, corrected_name

        hint = ", ".join(available_names[:12])
        raise ValueError(f"未知工具: {tool_name}。可用工具示例: {hint}")

    async def _invoke_llm(self, messages: List[Dict[str, Any]], format: Optional[str] = None) -> Dict[str, Any]:
        """调用语言模型并处理记忆内容"""
        # 1.将消息添加到记忆中
        await self._add_to_memory(messages)

        # 2.组装语言模型的响应格式
        response_format = {"type": format} if format else None

        # 3.循环向LLM发起提问直到最大重试次数
        error = "调用语言模型发生错误"
        for _ in range(self._agent_config.max_retries):
            try:
                llm_messages = self._build_llm_messages(self._memory.get_messages())
                effective_prompt_limit = self._get_effective_prompt_token_limit()
                while self._estimate_total_tokens(llm_messages) > effective_prompt_limit:
                    shrunk = await self._shrink_memory_to_target_prompt_tokens(
                        target_prompt_tokens=effective_prompt_limit,
                        reason="preflight_budget_guard",
                    )
                    if not shrunk:
                        break
                    llm_messages = self._build_llm_messages(self._memory.get_messages())

                # 4.调用语言模型获取响应内容
                message = await self._llm.invoke(
                    messages=llm_messages,
                    tools=self._get_available_tools(),
                    response_format=response_format,
                    tool_choice=self._tool_choice,
                    session_id=self._session_id,
                )

                # 5.处理AI响应内容避免空回复
                if message.get("role") == "assistant":
                    if not message.get("content") and not message.get("tool_calls"):
                        logger.warning(f"LLM回复了空内容，执行重试")
                        error = "LLM回复了空内容"
                        await self._add_to_memory([
                            {"role": "assistant", "content": ""},
                            {"role": "user", "content": "AI无响应内容，请继续。"}
                        ])
                        await asyncio.sleep(self._retry_interval)
                        continue

                    # 6.取出非空消息并处理工具调用(兼容DeepSeek思考模型的写法)
                    filtered_message = {"role": "assistant", "content": message.get("content")}
                    if message.get("tool_calls"):
                        # DeepSeek thinking + tool calls 要求回传 reasoning_content（v4-pro 文档要求）
                        reasoning_content = message.get("reasoning_content")
                        if self._is_deepseek_reasoning_model() and not isinstance(reasoning_content, str):
                            raise RuntimeError(
                                "DeepSeek thinking 模式工具调用缺少 reasoning_content，无法继续回传上下文"
                            )
                        if "reasoning_content" in message:
                            filtered_message["reasoning_content"] = reasoning_content
                        filtered_message["tool_calls"] = message.get("tool_calls")
                        logger.info(
                            "记录assistant工具调用消息: model=%s has_reasoning_content=%s tool_calls=%d",
                            self._llm.model_name,
                            "reasoning_content" in filtered_message,
                            len(message.get("tool_calls") or []),
                        )
                    elif message.get("reasoning_content"):
                        filtered_message["reasoning_content"] = message.get("reasoning_content")
                else:
                    # 8.非AI消息则记录日志并存储message
                    logger.warning(f"LLM响应内容无法确认消息角色: {message.get('role')}")
                    filtered_message = message

                # 9.将消息添加到记忆中
                await self._add_to_memory([filtered_message])
                return filtered_message
            except Exception as e:
                # 10.记录日志并睡眠指定的时间
                import traceback
                error_msg = str(e) or repr(e)
                error_type = e.__class__.__name__
                logger.error(f"调用语言模型发生错误[{error_type}]: {error_msg}\n{traceback.format_exc()}")
                error = f"{error_type}: {error_msg}"
                if await self._shrink_memory_for_context_overflow(error_msg):
                    continue
                await asyncio.sleep(self._retry_interval)
                continue

        # 11.所有重试均已耗尽仍未获得有效响应，抛出异常避免返回None
        raise RuntimeError(f"调用语言模型失败, 已达到最大重试次数({self._agent_config.max_retries}): {error}")

    def _build_llm_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        llm_messages: List[Dict[str, Any]] = []
        requires_reasoning = self._is_deepseek_reasoning_model()
        pending_assistant_message: Optional[Dict[str, Any]] = None
        pending_tool_call_ids: set[str] = set()
        pending_tool_call_seen_ids: set[str] = set()
        pending_tool_messages: List[Dict[str, Any]] = []

        def flush_pending_assistant() -> None:
            nonlocal pending_assistant_message, pending_tool_call_ids, pending_tool_call_seen_ids, pending_tool_messages
            if not pending_assistant_message:
                return
            is_complete = pending_tool_call_ids.issubset(pending_tool_call_seen_ids)
            if is_complete:
                llm_messages.append(pending_assistant_message)
                llm_messages.extend(pending_tool_messages)
            else:
                pending_assistant_message.pop("tool_calls", None)
                llm_messages.append(pending_assistant_message)
                logger.warning(
                    "检测到assistant/tool链路不完整，已移除tool_calls后发送: "
                    f"expect={len(pending_tool_call_ids)} seen={len(pending_tool_call_seen_ids)}"
                )
            pending_assistant_message = None
            pending_tool_call_ids = set()
            pending_tool_call_seen_ids = set()
            pending_tool_messages = []

        for message in messages:
            copied = dict(message)
            role = copied.get("role")

            if role == "assistant":
                flush_pending_assistant()
                raw_tool_calls = copied.get("tool_calls")
                valid_tool_calls: List[Dict[str, Any]] = []
                if isinstance(raw_tool_calls, list):
                    for item in raw_tool_calls:
                        if not isinstance(item, dict):
                            continue
                        tool_call_id = item.get("id")
                        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                            continue
                        valid_tool_calls.append(item)

                if valid_tool_calls:
                    copied["tool_calls"] = valid_tool_calls
                    pending_assistant_message = copied
                    pending_tool_call_ids = {
                        item["id"] for item in valid_tool_calls if isinstance(item.get("id"), str) and item["id"].strip()
                    }
                    pending_tool_call_seen_ids = set()
                    pending_tool_messages = []
                    if requires_reasoning and "reasoning_content" not in pending_assistant_message:
                        raise RuntimeError(
                            f"DeepSeek工具调用链路缺少 reasoning_content，model={self._llm.model_name}"
                        )
                else:
                    copied.pop("tool_calls", None)
                    llm_messages.append(copied)
                continue

            if role == "tool":
                tool_call_id = copied.get("tool_call_id")
                if (
                    not isinstance(tool_call_id, str)
                    or not tool_call_id.strip()
                    or not pending_assistant_message
                    or tool_call_id not in pending_tool_call_ids
                ):
                    logger.warning(f"跳过无效tool消息，未匹配到前置tool_calls: {tool_call_id}")
                    continue
                if copied.get("content") is None:
                    copied["content"] = ""
                pending_tool_messages.append(copied)
                pending_tool_call_seen_ids.add(tool_call_id)
                continue

            flush_pending_assistant()
            llm_messages.append(copied)

        flush_pending_assistant()
        return llm_messages

    def _is_deepseek_reasoning_model(self) -> bool:
        model_name = (self._llm.model_name or "").strip().lower()
        if model_name in self._deepseek_reasoning_models:
            return True
        return model_name.startswith("deepseek-v4")

    @staticmethod
    def _estimate_message_tokens(message: Dict[str, Any]) -> int:
        payload = json.dumps(message, ensure_ascii=False, default=str)
        return max(1, math.ceil(len(payload) / 3)) + 12

    def _estimate_total_tokens(self, messages: List[Dict[str, Any]]) -> int:
        return sum(self._estimate_message_tokens(message) for message in messages)

    def _is_summary_message(self, message: Dict[str, Any]) -> bool:
        if message.get("role") != "system":
            return False
        content = message.get("content")
        return isinstance(content, str) and content.startswith(self._summary_prefix)

    @staticmethod
    def _truncate_text(text: str, max_len: int) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= max_len:
            return cleaned
        return f"{cleaned[:max_len]}..."

    def _message_to_summary_line(self, message: Dict[str, Any]) -> Optional[str]:
        role = message.get("role")
        if role == "tool":
            function_name = message.get("function_name") or "tool"
            content = message.get("content")
            if isinstance(content, str):
                snippet = self._truncate_text(content, 180)
            else:
                snippet = self._truncate_text(json.dumps(content, ensure_ascii=False, default=str), 180)
            return f"- 工具[{function_name}]结果: {snippet}"
        if role in {"user", "assistant", "system"}:
            content = message.get("content")
            if content is None:
                return None
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, default=str)
            snippet = self._truncate_text(content, 180)
            if not snippet:
                return None
            role_name = {"user": "用户", "assistant": "助手", "system": "系统"}[role]
            return f"- {role_name}: {snippet}"
        return None

    def _extract_summary_body(self, message: Dict[str, Any]) -> str:
        content = message.get("content")
        if not isinstance(content, str):
            return ""
        return content[len(self._summary_prefix):].strip()

    def _build_trimmed_history_summary(self, dropped_messages: List[Dict[str, Any]], previous_summary: str) -> str:
        lines: List[str] = []
        if previous_summary:
            lines.append(f"- 既有摘要: {self._truncate_text(previous_summary, 500)}")
        for message in dropped_messages:
            line = self._message_to_summary_line(message)
            if line:
                lines.append(line)
            if sum(len(item) for item in lines) >= 2400:
                break
        if not lines:
            return ""
        body = "\n".join(lines)
        return self._truncate_text(body, 3000)

    async def _summarize_trimmed_history(self, dropped_messages: List[Dict[str, Any]], previous_summary: str) -> str:
        if not dropped_messages and not previous_summary:
            return ""

        draft = self._build_trimmed_history_summary(dropped_messages, previous_summary)
        if not draft:
            return ""

        prompt_source = self._truncate_text(draft, 5000)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是会话摘要助手。请将给定历史压缩成简洁中文摘要，保留："
                    "已完成关键动作、关键事实、产物路径、未完成事项。"
                    "输出纯文本，不要Markdown，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": f"请总结以下被裁剪历史：\n{prompt_source}",
            },
        ]

        try:
            summary_message = await self._llm.invoke(
                messages=messages,
                tools=None,
                response_format=None,
                tool_choice=None,
                session_id=self._session_id,
            )
            content = summary_message.get("content") if isinstance(summary_message, dict) else None
            if isinstance(content, str) and content.strip():
                return self._truncate_text(content, 3000)
        except Exception as e:
            logger.warning(f"LLM会话摘要失败，回退规则摘要: {e}")
        return self._truncate_text(draft, 3000)

    @staticmethod
    def _parse_context_limit(error_msg: str) -> Optional[int]:
        match = re.search(r"maximum context length is (\d+)", error_msg, re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _is_context_overflow_error(error_msg: str) -> bool:
        lowered = error_msg.lower()
        return (
            "maximum context length" in lowered
            or "context_length_exceeded" in lowered
            or "prompt token budget exceeded" in lowered
            or ("invalid_request_error" in lowered and "tokens" in lowered and "requested" in lowered)
        )

    def _get_effective_prompt_token_limit(self) -> int:
        base_limit = max(16800, self._max_prompt_tokens)
        resolver = getattr(self._llm, "get_safe_prompt_token_limit", None)
        if not callable(resolver):
            return base_limit
        try:
            resolved = int(resolver(self._session_id))
            return max(16800, min(base_limit, resolved))
        except Exception as e:
            logger.warning(f"获取会话安全prompt预算失败，回退默认预算: {e}")
            return base_limit

    async def _shrink_memory_to_target_prompt_tokens(self, target_prompt_tokens: int, reason: str) -> bool:
        await self._ensure_memory()
        if not self._memory or len(self._memory.messages) <= 2:
            return False

        self._memory.compact()
        messages = self._memory.get_messages()
        if self._estimate_total_tokens(messages) <= target_prompt_tokens:
            return False

        system_message = messages[0] if messages and messages[0].get("role") == "system" else None
        tail_messages = messages[1:] if system_message else messages[:]
        previous_summary_text = ""
        non_system_messages: List[Dict[str, Any]] = []
        for message in tail_messages:
            if self._is_summary_message(message):
                previous_summary_text = self._extract_summary_body(message)
                continue
            non_system_messages.append(message)

        summary_reserved_tokens = 16800
        target_prompt_tokens_without_summary = max(16800, target_prompt_tokens - summary_reserved_tokens)
        kept_reversed: List[Dict[str, Any]] = []
        kept_ids: set[int] = set()
        total_tokens = self._estimate_message_tokens(system_message) if system_message else 0

        for message in reversed(non_system_messages):
            message_tokens = self._estimate_message_tokens(message)
            if total_tokens + message_tokens > target_prompt_tokens_without_summary:
                continue
            kept_reversed.append(message)
            kept_ids.add(id(message))
            total_tokens += message_tokens

        kept_messages = list(reversed(kept_reversed))
        dropped_messages = [message for message in non_system_messages if id(message) not in kept_ids]
        summary_body = await self._summarize_trimmed_history(dropped_messages, previous_summary_text)

        compacted_messages: List[Dict[str, Any]] = []
        if system_message:
            compacted_messages.append(system_message)
        if summary_body:
            compacted_messages.append({
                "role": "system",
                "content": f"{self._summary_prefix}\n{summary_body}",
            })
        compacted_messages.extend(kept_messages)

        if len(compacted_messages) >= len(messages):
            if system_message and len(non_system_messages) > 0:
                compacted_messages = [system_message, *non_system_messages[1:]]
            elif len(messages) > 1:
                compacted_messages = messages[1:]

        if len(compacted_messages) >= len(messages):
            return False

        old_tokens = self._estimate_total_tokens(messages)
        new_tokens = self._estimate_total_tokens(compacted_messages)
        if new_tokens >= old_tokens:
            return False

        self._memory.messages = compacted_messages
        async with self._uow:
            await self._uow.session.save_memory(self._session_id, self.name, self._memory)
        logger.warning(
            f"已压缩记忆以适配prompt预算({reason}): 消息数{len(messages)}->{len(compacted_messages)}, "
            f"估算tokens {old_tokens}->{new_tokens}, 目标上限{target_prompt_tokens}"
        )
        return True

    async def _shrink_memory_for_context_overflow(self, error_msg: str) -> bool:
        if not self._is_context_overflow_error(error_msg):
            return False

        context_limit = self._parse_context_limit(error_msg) or 1000000
        completion_tokens = max(256, self._llm.max_tokens)
        target_prompt_tokens = max(33600, context_limit - completion_tokens - 8400)
        target_prompt_tokens = min(target_prompt_tokens, self._get_effective_prompt_token_limit())
        return await self._shrink_memory_to_target_prompt_tokens(
            target_prompt_tokens=target_prompt_tokens,
            reason="context_overflow",
        )

    async def _invoke_tool(self, tool: BaseTool, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """传递工具包+工具名字+对应参数调用指定工具"""
        # 1.执行循环调用工具获取结果
        err = ""
        for _ in range(self._agent_config.max_retries):
            try:
                return await tool.invoke(tool_name, **arguments)
            except Exception as e:
                err = str(e)
                logger.exception(f"调用工具[{tool_name}]出错, 错误: {str(e)}")
                await asyncio.sleep(self._retry_interval)
                continue

        # 2.循环最大重试次数后没有结果则将错误作为工具的执行结果，让LLM自行处理
        return ToolResult(success=False, message=err)

    @staticmethod
    def _normalize_function_args(function_name: str, function_args: Any) -> Dict[str, Any]:
        if isinstance(function_args, dict):
            return function_args
        if isinstance(function_args, list):
            for item in function_args:
                if isinstance(item, dict):
                    logger.warning(
                        f"工具[{function_name}]参数解析为list，已回退使用其中首个dict参数: {item}"
                    )
                    return item
        logger.warning(
            f"工具[{function_name}]参数解析异常，期望dict但实际为{type(function_args).__name__}，回退为空字典"
        )
        return {}

    async def _add_to_memory(self, messages: List[Dict[str, Any]]) -> None:
        """将对应的信息添加到记忆中"""
        # 1.先检查确保记忆是存在的
        await self._ensure_memory()

        # 2.检查记忆的消息列表是否为空，如果是空则需要添加预设prompt作为初始记忆
        if self._memory.empty:
            self._memory.add_message({
                "role": "system", "content": self._system_prompt,
            })

        # 3.将正常消息添加到记忆中
        self._memory.add_messages(messages)

        # 4.将记忆持久化到数据仓库中
        async with self._uow:
            await self._uow.session.save_memory(self._session_id, self.name, self._memory)

    async def compact_memory(self) -> None:
        """压缩Agent的记忆"""
        await self._ensure_memory()
        self._memory.compact()
        async with self._uow:
            await self._uow.session.save_memory(self._session_id, self.name, self._memory)

    async def roll_back(self, message: Message) -> None:
        """Agent的状态回滚，该函数用于确保Agent的消息列表状态是正确，用于发送新消息、暂停/停止任务、通知用户"""
        # 1.取出记忆中的最后一条消息，检查是否是工具调用
        await self._ensure_memory()
        last_message = self._memory.get_last_message()
        if (
                not last_message or
                not last_message.get("tool_calls") or
                len(last_message.get("tool_calls")) == 0
        ):
            return

        # 2.取出消息中的工具调用参数
        tool_call = last_message.get("tool_calls")[0]

        # 3.提取工具名字、id
        function_name = tool_call.get("function", {}).get("name")
        tool_call_id = tool_call.get("id")

        # 4.判断下当前的工具是不是通知用户(message_ask_user)
        if function_name == "message_ask_user":
            self._memory.add_message({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "function_name": function_name,
                "content": message.model_dump_json(),
            })
        else:
            # 5.否则直接删除最后一条消息
            self._memory.roll_back()

        # 6.将记忆持久化
        async with self._uow:
            await self._uow.session.save_memory(self._session_id, self.name, self._memory)

    async def invoke(self, query: str, format: Optional[str] = None) -> AsyncGenerator[BaseEvent, None]:
        """传递消息+响应格式调用程序生成异步迭代内容"""
        # 1.需要判断下是否传递了format
        format = format if format else self._format

        # 2.调用语言模型获取响应内容
        message = await self._invoke_llm(
            [{"role": "user", "content": query}],
            format,
        )

        # 3.循环遍历直到最大迭代次数
        for _ in range(self._agent_config.max_iterations):
            # 4.如果LLM响应为空或无工具调用则表示LLM生成了文本回答，这时候就是最终答案
            if not message or not message.get("tool_calls"):
                break

            # 5.循环遍历工具参数并执行
            tool_messages = []
            for tool_call in message["tool_calls"]:
                if not tool_call.get("function"):
                    continue

                # 6.取出调用工具id、名字、参数信息
                tool_call_id = tool_call["id"] or str(uuid.uuid4())
                function_name = tool_call["function"]["name"]
                function_args_raw = await self._json_parser.invoke(tool_call["function"]["arguments"])
                function_args = self._normalize_function_args(function_name, function_args_raw)

                # 7.取出Agent中对应的工具
                tool, resolved_function_name = self._resolve_tool(function_name)

                # 8.返回工具即将调用事件，其中tool_content比较特殊，需要在具体业务中进行实现，这里留空即可
                yield ToolEvent(
                    tool_call_id=tool_call_id,
                    tool_name=tool.name,
                    function_name=resolved_function_name,
                    function_args=function_args,
                    status=ToolEventStatus.CALLING,
                )

                # 9.调用工具并获取结果
                result = await self._invoke_tool(tool, resolved_function_name, function_args)

                # 10.返回工具调用结果，其中tool_content比较特殊，需要在业务中进行实现
                yield ToolEvent(
                    tool_call_id=tool_call_id,
                    tool_name=tool.name,
                    function_name=resolved_function_name,
                    function_args=function_args,
                    function_result=result,
                    status=ToolEventStatus.CALLED,
                )

                # 11.组装工具响应
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "function_name": resolved_function_name,
                    "content": result.model_dump_json(),
                })

            # 12.所有工具都执行完成后，调用LLM获取汇总消息二次提供
            message = await self._invoke_llm(tool_messages)
        else:
            # 13.超过最大迭代次数后，则抛出错误
            yield ErrorEvent(error=f"Agent迭代超过最大迭代次数: {self._agent_config.max_iterations}, 任务处理失败")

        # 14.在指定步骤内完成了迭代则返回消息事件
        if message and message.get("content") is not None:
            yield MessageEvent(message=message["content"])
        else:
            yield ErrorEvent(error="Agent未能生成有效回复内容")
