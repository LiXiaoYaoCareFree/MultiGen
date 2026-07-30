"""Unit tests for the MiniMax voice design/cloning tool wiring."""
import asyncio

from app.domain.services.tools.minimax_voice import MiniMaxVoiceTool


def _tool_without_key() -> MiniMaxVoiceTool:
    tool = MiniMaxVoiceTool()
    tool.core.minimax_api_key = ""
    return tool


def test_tool_registers_both_operations():
    """Both voice operations are exposed to the LLM tool schema."""
    tool = MiniMaxVoiceTool()
    names = {schema["function"]["name"] for schema in tool.get_tools()}
    assert {"minimax_voice_design", "minimax_voice_cloning"} <= names
    assert tool.has_tool("minimax_voice_design")
    assert tool.has_tool("minimax_voice_cloning")


def test_endpoint_selects_region_and_group():
    """Endpoint resolution honours the region and appends the group id."""
    core = MiniMaxVoiceTool().core
    core.minimax_base_url = ""
    core.minimax_group_id = ""
    core.minimax_region = "global_en"
    assert core._minimax_endpoint("/v1/voice_clone") == "https://api.minimax.io/v1/voice_clone"
    core.minimax_region = "cn_zh"
    assert core._minimax_endpoint("/v1/voice_clone") == "https://api.minimaxi.com/v1/voice_clone"
    core.minimax_group_id = "grp123"
    assert core._minimax_endpoint("/v1/t2a_v2") == "https://api.minimaxi.com/v1/t2a_v2?GroupId=grp123"


def test_voice_design_requires_api_key():
    """Voice design fails gracefully when no API key is configured."""
    tool = _tool_without_key()
    result = asyncio.run(tool.core.minimax_voice_design("warm female voice", "hello"))
    assert result.success is False


def test_voice_cloning_requires_api_key():
    """Voice cloning fails gracefully when no API key is configured."""
    tool = _tool_without_key()
    result = asyncio.run(tool.core.minimax_voice_cloning("/storage/audios/sample.mp3", "hello"))
    assert result.success is False
