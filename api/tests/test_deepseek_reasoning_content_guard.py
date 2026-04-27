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
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.temperature = 0.7
        self.max_tokens = 384000
        self.max_prompt_tokens = 1000000

    async def invoke(self, *args, **kwargs):
        return {"role": "assistant", "content": "ok"}


class _DummyAgent(BaseAgent):
    name = "dummy"


def _new_agent(model_name: str) -> _DummyAgent:
    return _DummyAgent(
        uow_factory=_DummyUow,
        session_id="s1",
        agent_config=type("C", (), {"max_retries": 1, "max_iterations": 1})(),
        llm=_DummyLLM(model_name),
        json_parser=_DummyJSONParser(),
        tools=[],
    )


def test_detect_v4_pro_as_reasoning_model() -> None:
    agent = _new_agent("deepseek-v4-pro")
    assert agent._is_deepseek_reasoning_model() is True


def test_raise_when_tool_call_without_reasoning_content() -> None:
    agent = _new_agent("deepseek-v4-pro")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
    ]
    try:
        agent._build_llm_messages(messages)
    except RuntimeError as e:
        assert "reasoning_content" in str(e)
    else:
        raise AssertionError("expected RuntimeError when reasoning_content is missing")

