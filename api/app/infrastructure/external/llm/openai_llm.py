import logging
import math
import json
import re
from typing import List, Dict, Any, Tuple, Optional

from openai import AsyncOpenAI

from app.application.errors.exceptions import ServerRequestsError
from app.domain.external.llm import LLM
from app.domain.models.app_config import LLMConfig

logger = logging.getLogger(__name__)


class OpenAILLM(LLM):
    """基于OpenAI SDK/兼容OpenAI格式的LLM调用类"""

    def __init__(self, llm_config: LLMConfig, **kwargs) -> None:
        """构造函数，完成异步OpenAI客户端的创建和参数初始化"""
        # 1.初始化异步客户端
        self._client = AsyncOpenAI(
            base_url=str(llm_config.base_url),
            api_key=llm_config.api_key,
            **kwargs,
        )

        # 2.完成其他参数的存储
        self._model_name = llm_config.model_name
        self._temperature = llm_config.temperature
        self._max_tokens = llm_config.max_tokens
        self._max_prompt_tokens = llm_config.max_prompt_tokens
        self._timeout = 3600
        self._session_budget_overrides: Dict[str, Dict[str, float | int]] = {}
        self._default_multiplier = 1.15
        self._default_offset = 4200
        self._default_reserved_tokens = 16800

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def max_prompt_tokens(self) -> int:
        return self._max_prompt_tokens

    def get_safe_prompt_token_limit(self, session_id: str | None = None) -> int:
        multiplier, offset, _ = self._get_budget_factors(session_id)
        safe_limit = math.floor((self._max_prompt_tokens - offset) / max(multiplier, 1e-6))
        return max(16800, safe_limit)

    @staticmethod
    def _estimate_prompt_tokens(messages: List[Dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            payload = json.dumps(message, ensure_ascii=False, default=str)
            total += max(1, math.ceil(len(payload) / 3)) + 12
        return total

    @staticmethod
    def _extract_context_overflow_metrics(raw_text: str) -> Optional[Tuple[int, int, int, int]]:
        if not raw_text:
            return None
        context_match = re.search(r"maximum context length is (\d+)", raw_text, re.IGNORECASE)
        request_match = re.search(
            r"requested\s+(\d+)\s+tokens\s*\((\d+)\s+in the messages,\s*(\d+)\s+in the completion\)",
            raw_text,
            re.IGNORECASE,
        )
        if not request_match:
            return None
        context_limit = int(context_match.group(1)) if context_match else 1000000
        requested_total = int(request_match.group(1))
        message_tokens = int(request_match.group(2))
        completion_tokens = int(request_match.group(3))
        return context_limit, requested_total, message_tokens, completion_tokens

    def _get_budget_factors(self, session_id: Optional[str]) -> Tuple[float, int, int]:
        if not session_id or session_id not in self._session_budget_overrides:
            return self._default_multiplier, self._default_offset, self._default_reserved_tokens
        budget = self._session_budget_overrides[session_id]
        multiplier = float(budget.get("multiplier", self._default_multiplier))
        offset = int(budget.get("offset", self._default_offset))
        reserved_tokens = int(budget.get("reserved_tokens", self._default_reserved_tokens))
        return multiplier, offset, reserved_tokens

    def _calibrate_session_budget_from_error(
            self,
            session_id: Optional[str],
            messages: List[Dict[str, Any]],
            raw_error_text: str,
    ) -> None:
        if not session_id:
            return
        metrics = self._extract_context_overflow_metrics(raw_error_text)
        if not metrics:
            return

        context_limit, _, actual_message_tokens, completion_tokens = metrics
        estimated_prompt_tokens = self._estimate_prompt_tokens(messages)
        target_prompt_tokens = min(actual_message_tokens + 8400, self._max_prompt_tokens)

        current_multiplier, current_offset, current_reserved = self._get_budget_factors(session_id)
        required_multiplier = target_prompt_tokens / max(1, estimated_prompt_tokens)
        new_multiplier = min(max(current_multiplier, required_multiplier), 6.0)
        base_predicted = math.ceil(estimated_prompt_tokens * new_multiplier)
        required_offset = max(0, target_prompt_tokens - base_predicted)
        new_offset = min(max(current_offset, required_offset), 268800)
        new_reserved = min(max(current_reserved, completion_tokens + 8400), 268800)

        if (
                new_multiplier == current_multiplier
                and new_offset == current_offset
                and new_reserved == current_reserved
        ):
            return

        self._session_budget_overrides[session_id] = {
            "multiplier": new_multiplier,
            "offset": new_offset,
            "reserved_tokens": new_reserved,
        }
        logger.warning(
            f"LLM token预算二次自适应 session_id={session_id} context_limit={context_limit} "
            f"max_prompt_tokens={self._max_prompt_tokens} "
            f"estimated_prompt_tokens={estimated_prompt_tokens} actual_message_tokens={actual_message_tokens} "
            f"multiplier={current_multiplier:.3f}->{new_multiplier:.3f} "
            f"offset={current_offset}->{new_offset} reserved_tokens={current_reserved}->{new_reserved}"
        )

    def _resolve_request_max_tokens(
            self,
            messages: List[Dict[str, Any]],
            session_id: Optional[str] = None,
    ) -> Tuple[int, int, int]:
        model_name = self._model_name.strip().lower()
        context_limit = 1000000
        prompt_tokens = self._estimate_prompt_tokens(messages)
        if "deepseek" not in model_name:
            return self._max_tokens, prompt_tokens, context_limit

        multiplier, offset, reserved_tokens = self._get_budget_factors(session_id)
        conservative_prompt_tokens = math.ceil(prompt_tokens * multiplier) + offset
        if conservative_prompt_tokens > self._max_prompt_tokens:
            requested_total = conservative_prompt_tokens + max(256, self._max_tokens)
            raise ServerRequestsError(
                "调用OpenAI客户端向LLM发起请求出错: "
                f"Prompt token budget exceeded {self._max_prompt_tokens}. "
                f"However, you requested {requested_total} tokens "
                f"({conservative_prompt_tokens} in the messages, {max(256, self._max_tokens)} in the completion). "
                "Please reduce the length of the messages or completion."
            )
        allowed = context_limit - conservative_prompt_tokens - reserved_tokens
        if allowed < 256:
            requested_total = conservative_prompt_tokens + max(256, self._max_tokens)
            raise ServerRequestsError(
                "调用OpenAI客户端向LLM发起请求出错: "
                f"This model's maximum context length is {context_limit} tokens. "
                f"However, you requested {requested_total} tokens "
                f"({conservative_prompt_tokens} in the messages, {max(256, self._max_tokens)} in the completion). "
                "Please reduce the length of the messages or completion."
            )

        request_max_tokens = min(self._max_tokens, allowed)
        if request_max_tokens < self._max_tokens:
            logger.warning(
                f"根据上下文动态下调max_tokens: {self._max_tokens}->{request_max_tokens}, "
                f"估算prompt_tokens={prompt_tokens}, 保守估算prompt_tokens={conservative_prompt_tokens}, "
                f"context_limit={context_limit}, session_id={session_id or '-'}"
            )
        return request_max_tokens, prompt_tokens, context_limit

    async def invoke(
            self,
            messages: List[Dict[str, Any]],
            tools: List[Dict[str, Any]] = None,
            response_format: Dict[str, Any] = None,
            tool_choice: str = None,
            session_id: str | None = None,
    ) -> Dict[str, Any]:
        """使用异步OpenAI客户端发起块响应（该步骤可以切换成流式响应）"""
        try:
            request_max_tokens, prompt_tokens, context_limit = self._resolve_request_max_tokens(
                messages=messages,
                session_id=session_id,
            )
            logger.info(
                f"LLM token预算 session_id={session_id or '-'} prompt_tokens={prompt_tokens} "
                f"request_max_tokens={request_max_tokens} context_limit={context_limit}"
            )

            # 1.检测是否传递了工具列表
            if tools:
                logger.info(f"调用OpenAI客户端向LLM发起请求并携带工具信息: {self._model_name}")
                response = await self._client.chat.completions.create(
                    model=self._model_name,
                    temperature=self._temperature,
                    max_tokens=request_max_tokens,
                    messages=messages,
                    response_format=response_format,
                    tools=tools,
                    tool_choice=tool_choice,
                    parallel_tool_calls=False,  # 关闭并行工具调用(deepseek没有这个参数的)
                    timeout=self._timeout,
                )
            else:
                # 2.为传递工具则删除tools/tool_choice等参数
                logger.info(f"调用OpenAI客户端向LLM发起请求未携带: {self._model_name}")
                response = await self._client.chat.completions.create(
                    model=self._model_name,
                    temperature=self._temperature,
                    max_tokens=request_max_tokens,
                    messages=messages,
                    response_format=response_format,
                    timeout=self._timeout,
                )

            # 3.处理响应数据并返回
            logger.info(f"OpenAI客户端返回内容: {response.model_dump()}")
            return response.choices[0].message.model_dump()
        except Exception as e:
            error_type = e.__class__.__name__
            error_message = str(e) or repr(e)
            status_code = getattr(e, "status_code", None)
            code = getattr(e, "code", None)
            request = getattr(e, "request", None)
            request_method = getattr(request, "method", None) if request else None
            request_url = str(getattr(request, "url", "")) if request else ""
            body = getattr(e, "body", None)
            body_text = ""
            if body is not None:
                body_text = str(body)
                if len(body_text) > 600:
                    body_text = f"{body_text[:600]}..."

            raw_error_text = f"{error_message}\n{body_text}"
            self._calibrate_session_budget_from_error(
                session_id=session_id,
                messages=messages,
                raw_error_text=raw_error_text,
            )

            details = [f"{error_type}: {error_message}"]
            if status_code is not None:
                details.append(f"status={status_code}")
            if code:
                details.append(f"code={code}")
            if request_method or request_url:
                details.append(f"request={request_method or ''} {request_url}".strip())
            if body_text:
                details.append(f"body={body_text}")

            detail_text = " | ".join(details)
            logger.error(f"调用OpenAI客户端发生错误: {detail_text}")
            raise ServerRequestsError(f"调用OpenAI客户端向LLM发起请求出错: {detail_text}")


if __name__ == "__main__":
    import asyncio


    async def main():
        llm = OpenAILLM(LLMConfig(
            base_url="https://api.deepseek.com",
            api_key="",
            model_name="deepseek-chat",
        ))
        response = await llm.invoke([{"role": "user", "content": "Hi"}])
        print(response)


    asyncio.run(main())
