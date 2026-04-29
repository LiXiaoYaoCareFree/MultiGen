import asyncio
from types import SimpleNamespace

from app.domain.models.app_config import LLMConfig
from app.infrastructure.external.llm.openai_llm import OpenAILLM


class _FakeCompletions:
    def __init__(self):
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(model_dump=lambda: {"role": "assistant", "content": "ok"})
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], model_dump=lambda: {"choices": [{"message": {"content": "ok"}}]})


class _FakeMessageWithAttr:
    def __init__(self):
        self.reasoning_content = "inner think"
        self.model_extra = {}

    def model_dump(self):
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
        }


class _FakeResponseWithRawReasoning:
    def __init__(self):
        self.choices = [SimpleNamespace(message=_FakeMessageWithAttr())]

    def model_dump(self):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "inner think",
                        "tool_calls": [{"id": "call_1", "function": {"name": "f", "arguments": "{}"}}],
                    }
                }
            ]
        }


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_deepseek_v4_flash_enables_thinking_flags() -> None:
    llm = OpenAILLM(
        LLMConfig(
            base_url="https://api.deepseek.com",
            api_key="test",
            model_name="deepseek-v4-flash",
            max_tokens=384000,
            max_prompt_tokens=1000000,
        )
    )
    fake_client = _FakeClient()
    llm._client = fake_client

    asyncio.run(
        llm.invoke(
            messages=[{"role": "user", "content": "hello"}],
            tools=None,
            session_id="s1",
        )
    )

    kwargs = fake_client.chat.completions.last_kwargs
    assert kwargs is not None
    assert kwargs.get("reasoning_effort") == "high"
    assert kwargs.get("extra_body") == {"thinking": {"type": "enabled"}}
    assert "temperature" not in kwargs


def test_extract_message_payload_keeps_reasoning_content_from_message_attr() -> None:
    payload = OpenAILLM._extract_message_payload(_FakeResponseWithRawReasoning())
    assert payload["reasoning_content"] == "inner think"
    assert payload["tool_calls"][0]["id"] == "call_1"
