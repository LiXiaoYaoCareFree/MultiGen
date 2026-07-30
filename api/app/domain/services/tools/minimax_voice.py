from typing import Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class MiniMaxVoiceTool(BaseTool):
    name: str = "minimax_voice"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="minimax_voice_design",
        description="通过音色描述设计音色并合成语音。",
        parameters={
            "voice_description": {"type": "string", "description": "音色描述"},
            "text": {"type": "string", "description": "合成文本"},
            "model": {"type": "string", "description": "合成模型，可选"},
        },
        required=["voice_description", "text"],
    )
    async def minimax_voice_design(self, voice_description: str, text: str, model: Optional[str] = None) -> ToolResult:
        return await self.core.minimax_voice_design(voice_description, text, model)

    @tool(
        name="minimax_voice_cloning",
        description="根据参考音频复刻音色并合成语音。",
        parameters={
            "reference_audio": {"type": "string", "description": "参考音频路径或URL"},
            "text": {"type": "string", "description": "合成文本"},
            "model": {"type": "string", "description": "复刻/合成模型，可选"},
        },
        required=["reference_audio", "text"],
    )
    async def minimax_voice_cloning(self, reference_audio: str, text: str, model: Optional[str] = None) -> ToolResult:
        return await self.core.minimax_voice_cloning(reference_audio, text, model)
