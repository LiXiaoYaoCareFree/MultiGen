from typing import List, Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class VideoConcatenationTool(BaseTool):
    name: str = "video_concatenation"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="concatenate_videos",
        description="将多个视频片段拼接为完整视频。",
        parameters={
            "video_urls": {"type": "array", "items": {"type": "string"}, "description": "按顺序拼接的视频路径列表"},
            "output_filename": {"type": "string", "description": "可选输出文件名"},
        },
        required=["video_urls"],
    )
    async def concatenate_videos(self, video_urls: List[str], output_filename: Optional[str] = None) -> ToolResult:
        return await self.core.concatenate_videos(video_urls, output_filename)
