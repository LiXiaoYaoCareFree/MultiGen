from typing import Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class MiniMaxMusicTool(BaseTool):
    name: str = "minimax_music"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="minimax_music_generation",
        description="根据风格描述与歌词生成音乐，返回本地音频文件。",
        parameters={
            "prompt": {"type": "string", "description": "音乐风格、情绪或场景描述"},
            "lyrics": {"type": "string", "description": "歌词，换行分隔，可选"},
            "model": {"type": "string", "description": "音乐生成模型，可选"},
            "output_format": {
                "type": "string",
                "enum": list(MultimodalCore.MINIMAX_MUSIC_OUTPUT_FORMATS),
                "description": "接口返回形式，可选",
            },
            "audio_format": {
                "type": "string",
                "enum": list(MultimodalCore.MINIMAX_MUSIC_AUDIO_FORMATS),
                "description": "音频编码格式，可选",
            },
            "is_instrumental": {"type": "boolean", "description": "是否生成纯伴奏，可选"},
            "lyrics_optimizer": {"type": "boolean", "description": "是否自动优化歌词，可选"},
        },
        required=["prompt"],
    )
    async def minimax_music_generation(
        self,
        prompt: Optional[str] = None,
        lyrics: Optional[str] = None,
        model: Optional[str] = None,
        output_format: Optional[str] = None,
        audio_format: Optional[str] = None,
        is_instrumental: Optional[bool] = None,
        lyrics_optimizer: Optional[bool] = None,
    ) -> ToolResult:
        return await self.core.generate_music(
            prompt=prompt,
            lyrics=lyrics,
            model=model,
            output_format=output_format,
            audio_format=audio_format,
            is_instrumental=is_instrumental,
            lyrics_optimizer=lyrics_optimizer,
        )
