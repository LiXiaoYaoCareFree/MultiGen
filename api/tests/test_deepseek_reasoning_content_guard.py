import pytest

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


def test_detect_v4_flash_as_reasoning_model() -> None:
    agent = _new_agent("deepseek-v4-flash")
    assert agent._is_deepseek_reasoning_model() is True


def test_raise_when_tool_call_without_reasoning_content() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
    ]
    with pytest.raises(RuntimeError, match="reasoning_content"):
        agent._build_llm_messages(messages)


def test_keep_reasoning_content_when_no_tool_call() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {"role": "assistant", "content": "final answer", "reasoning_content": "inner think"},
        {"role": "user", "content": "next turn"},
    ]
    llm_messages = agent._build_llm_messages(messages)
    assistant = llm_messages[1]
    assert assistant["role"] == "assistant"
    assert assistant.get("reasoning_content") == "inner think"


def test_keep_reasoning_content_when_tool_call_chain_complete() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "inner think",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "user", "content": "continue"},
    ]
    llm_messages = agent._build_llm_messages(messages)
    assistant = llm_messages[1]
    assert assistant["role"] == "assistant"
    assert assistant.get("reasoning_content") == "inner think"
    assert assistant.get("tool_calls")
    assert llm_messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "{}"}


def test_raise_when_tool_call_reasoning_content_is_empty() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
    ]
    with pytest.raises(RuntimeError, match="reasoning_content"):
        agent._build_llm_messages(messages)


def test_keep_reasoning_content_for_final_assistant_in_tool_turn() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "inner think",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "assistant", "content": "done", "reasoning_content": "final think"},
        {"role": "user", "content": "continue"},
    ]
    llm_messages = agent._build_llm_messages(messages)
    assert llm_messages[1].get("tool_calls")
    assert llm_messages[1].get("reasoning_content") == "inner think"
    assert llm_messages[3].get("reasoning_content") == "final think"


def test_allow_final_assistant_in_tool_turn_without_reasoning_content() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "question"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "inner think",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "next"},
    ]
    llm_messages = agent._build_llm_messages(messages)
    final_assistant = llm_messages[4]
    assert final_assistant["role"] == "assistant"
    assert final_assistant.get("content") == "done"
    assert "reasoning_content" not in final_assistant


def test_tool_message_strips_non_spec_fields() -> None:
    agent = _new_agent("deepseek-v4-flash")
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "inner think",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "function_name": "f", "content": "{}"},
        {"role": "user", "content": "continue"},
    ]
    llm_messages = agent._build_llm_messages(messages)
    assert llm_messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "{}"}
