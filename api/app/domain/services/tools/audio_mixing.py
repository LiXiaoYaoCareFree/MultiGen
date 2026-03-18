from typing import List, Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class AudioMixingTool(BaseTool):
    name: str = "audio_mixing"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="concatenate_audio",
        description="将多个音频片段按顺序拼接。",
        parameters={
            "audio_files": {"type": "array", "items": {"type": "string"}, "description": "音频路径列表"},
            "crossfade_duration": {"type": "integer", "description": "交叉淡入淡出时长毫秒"},
            "silence_duration": {"type": "integer", "description": "静音间隔毫秒"},
        },
        required=["audio_files"],
    )
    async def concatenate_audio(self, audio_files: List[str], crossfade_duration: int = 200, silence_duration: int = 1200) -> ToolResult:
        return await self.core.concatenate_audio(audio_files, crossfade_duration, silence_duration)

    @tool(
        name="select_background_music",
        description="根据场景描述选择背景音乐。",
        parameters={
            "scene_description": {"type": "string", "description": "场景描述"},
            "duration_seconds": {"type": "number", "description": "目标时长秒"},
        },
        required=["scene_description"],
    )
    async def select_background_music(self, scene_description: str, duration_seconds: Optional[float] = None) -> ToolResult:
        return await self.core.select_background_music(scene_description, duration_seconds)

    @tool(
        name="mix_audio_with_bgm",
        description="将人声与BGM混音输出播客成品。",
        parameters={
            "voice_audio": {"type": "string", "description": "主音频路径"},
            "bgm_audio": {"type": "string", "description": "背景音频路径"},
            "bgm_volume": {"type": "number", "description": "BGM音量dB"},
            "intro_duration": {"type": "number", "description": "开场原声秒数"},
            "normalize": {"type": "boolean", "description": "是否归一化"},
        },
        required=["voice_audio", "bgm_audio"],
    )
    async def mix_audio_with_bgm(
        self,
        voice_audio: str,
        bgm_audio: str,
        bgm_volume: float = -26,
        intro_duration: float = 3.0,
        normalize: bool = True,
    ) -> ToolResult:
        return await self.core.mix_audio_with_bgm(voice_audio, bgm_audio, bgm_volume, intro_duration, normalize)
