"""Unit tests for the MiniMax music generation tool wiring."""
import asyncio

from app.domain.services.tools.minimax_music import MiniMaxMusicTool


def _tool_without_key() -> MiniMaxMusicTool:
    tool = MiniMaxMusicTool()
    tool.core.minimax_api_key = ""
    return tool


def _tool_with_key() -> MiniMaxMusicTool:
    tool = MiniMaxMusicTool()
    tool.core.minimax_api_key = "test-key"
    return tool


def test_tool_registers_music_generation():
    """The music generation operation is exposed to the LLM tool schema."""
    tool = MiniMaxMusicTool()
    names = {schema["function"]["name"] for schema in tool.get_tools()}
    assert "minimax_music_generation" in names
    assert tool.has_tool("minimax_music_generation")


def test_music_endpoint_covers_both_regions():
    """Music generation resolves the global and CN hosts of the same path."""
    core = MiniMaxMusicTool().core
    core.minimax_base_url = ""
    core.minimax_group_id = ""
    core.minimax_region = "global_en"
    assert core._minimax_endpoint("/v1/music_generation") == "https://api.minimax.io/v1/music_generation"
    core.minimax_region = "cn_zh"
    assert core._minimax_endpoint("/v1/music_generation") == "https://api.minimaxi.com/v1/music_generation"


def test_payload_defaults_and_optional_fields():
    """Only the model is mandatory; optional fields appear when provided."""
    core = MiniMaxMusicTool().core
    core.minimax_region = "global_en"
    minimal = core._minimax_music_payload("music-3.0", "calm piano", None, "hex", "mp3", None, None)
    assert minimal == {
        "model": "music-3.0",
        "output_format": "hex",
        "stream": False,
        "audio_setting": {"format": "mp3"},
        "prompt": "calm piano",
    }
    full = core._minimax_music_payload("music-2.6", "rock", "line one\nline two", "url", "wav", True, False)
    assert full["lyrics"] == "line one\nline two"
    assert full["is_instrumental"] is True
    assert full["lyrics_optimizer"] is False
    assert full["output_format"] == "url"
    assert full["audio_setting"] == {"format": "wav"}


def test_watermark_field_is_cn_only():
    """The watermark flag is only sent to the CN endpoint."""
    core = MiniMaxMusicTool().core
    core.minimax_music_aigc_watermark = True
    core.minimax_region = "global_en"
    assert "aigc_watermark" not in core._minimax_music_payload("music-3.0", "jazz", None, "hex", "mp3", None, None)
    core.minimax_region = "cn_zh"
    assert core._minimax_music_payload("music-3.0", "jazz", None, "hex", "mp3", None, None)["aigc_watermark"] is True


def test_completed_response_returns_audio():
    """A completed task exposes the audio payload."""
    core = MiniMaxMusicTool().core
    data = {"data": {"status": 2, "audio": "1a2b3c"}, "base_resp": {"status_code": 0}}
    assert core._extract_minimax_music_audio(data) == "1a2b3c"


def test_in_progress_response_is_rejected():
    """An unfinished task does not yield audio."""
    core = MiniMaxMusicTool().core
    data = {"data": {"status": 1, "audio": ""}, "base_resp": {"status_code": 0}}
    try:
        core._extract_minimax_music_audio(data)
    except RuntimeError:
        pass
    else:
        raise AssertionError("in-progress response should raise")


def test_api_error_and_empty_audio_are_rejected():
    """Non-zero status codes and empty audio are reported as failures."""
    core = MiniMaxMusicTool().core
    for data in (
        {"data": {"status": 2, "audio": "1a2b"}, "base_resp": {"status_code": 1004, "status_msg": "bad key"}},
        {"data": {"status": 2, "audio": ""}, "base_resp": {"status_code": 0}},
    ):
        try:
            core._extract_minimax_music_audio(data)
        except RuntimeError:
            continue
        raise AssertionError("invalid response should raise")


def test_music_generation_requires_api_key():
    """Music generation fails gracefully when no API key is configured."""
    tool = _tool_without_key()
    result = asyncio.run(tool.core.generate_music(prompt="calm piano"))
    assert result.success is False


def test_music_generation_requires_prompt_or_lyrics():
    """At least one of prompt or lyrics must be supplied."""
    tool = _tool_with_key()
    result = asyncio.run(tool.core.generate_music())
    assert result.success is False


def test_music_generation_validates_formats():
    """Unsupported output and audio formats are rejected before any request."""
    tool = _tool_with_key()
    bad_output = asyncio.run(tool.core.generate_music(prompt="calm piano", output_format="mp4"))
    assert bad_output.success is False
    bad_audio = asyncio.run(tool.core.generate_music(prompt="calm piano", audio_format="flac"))
    assert bad_audio.success is False
