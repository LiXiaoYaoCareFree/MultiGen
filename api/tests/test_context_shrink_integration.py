import asyncio

from app.domain.services.agents.base import BaseAgent


class _DummyUow:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class _DummyJSONParser:
    async def invoke(self, payload):
        return payload


class _DummyLLM:
    model_name = "deepseek-v4-flash"
    temperature = 0.7
    max_tokens = 384000
    max_prompt_tokens = 1000000

    @staticmethod
    def get_safe_prompt_token_limit(session_id=None):
        return 1000000

    async def invoke(self, *args, **kwargs):
        return {"role": "assistant", "content": "ok"}


class _DummyAgent(BaseAgent):
    name = "dummy"


def test_context_overflow_target_uses_new_window() -> None:
    agent = _DummyAgent(
        uow_factory=_DummyUow,
        session_id="s1",
        agent_config=type("C", (), {"max_retries": 1, "max_iterations": 1})(),
        llm=_DummyLLM(),
        json_parser=_DummyJSONParser(),
        tools=[],
    )
    captured = {}

    async def _fake_shrink(target_prompt_tokens: int, reason: str):
        captured["target"] = target_prompt_tokens
        captured["reason"] = reason
        return True

    agent._shrink_memory_to_target_prompt_tokens = _fake_shrink  # type: ignore[method-assign]
    overflow = "This model's maximum context length is 1000000 tokens."
    result = asyncio.run(agent._shrink_memory_for_context_overflow(overflow))

    assert result is True
    assert captured["reason"] == "context_overflow"
    assert captured["target"] == 607600
