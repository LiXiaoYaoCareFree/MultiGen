from app.domain.models.app_config import LLMConfig
from app.infrastructure.external.llm.openai_llm import OpenAILLM


def test_llm_config_deepseek_limits() -> None:
    config = LLMConfig(
        base_url="https://api.deepseek.com",
        api_key="test",
        model_name="deepseek-chat",
        max_tokens=384000,
        max_prompt_tokens=1000000,
    )
    assert config.max_tokens == 384000
    assert config.max_prompt_tokens == 1000000


def test_openai_llm_uses_updated_defaults() -> None:
    llm = OpenAILLM(
        LLMConfig(
            base_url="https://api.deepseek.com",
            api_key="test",
            model_name="deepseek-chat",
            max_tokens=384000,
            max_prompt_tokens=1000000,
        ),
    )
    assert llm.max_tokens == 384000
    assert llm.max_prompt_tokens == 1000000
    assert llm.get_safe_prompt_token_limit() >= 16800

