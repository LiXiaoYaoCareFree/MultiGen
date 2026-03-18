from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class QwenTTSTool(BaseTool):
    name: str = "qwen_tts"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="qwen_voice_design",
        description="通过音色描述生成语音样本。",
        parameters={
            "voice_description": {"type": "string", "description": "音色描述"},
            "text": {"type": "string", "description": "合成文本"},
            "language": {"type": "string", "description": "语言代码，如zh、en"},
        },
        required=["voice_description", "text"],
    )
    async def qwen_voice_design(self, voice_description: str, text: str, language: str = "zh") -> ToolResult:
        return await self.core.qwen_voice_design(voice_description, text, language)

    @tool(
        name="qwen_voice_cloning",
        description="根据参考音频复刻音色并合成语音。",
        parameters={
            "reference_audio": {"type": "string", "description": "参考音频路径或URL"},
            "text": {"type": "string", "description": "合成文本"},
            "language": {"type": "string", "description": "语言代码，如zh、en"},
        },
        required=["reference_audio", "text"],
    )
    async def qwen_voice_cloning(self, reference_audio: str, text: str, language: str = "zh") -> ToolResult:
        return await self.core.qwen_voice_cloning(reference_audio, text, language)
