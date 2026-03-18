from typing import Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class VolcanoVideoGenerationTool(BaseTool):
    name: str = "volcano_video"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="generate_volcano_video",
        description="火山引擎视频生成工具，支持text、image、start_end模式。",
        parameters={
            "prompt": {"type": "string", "description": "视频提示词"},
            "duration": {"type": "integer", "description": "视频时长秒，4-12"},
            "ratio": {"type": "string", "description": "宽高比，如16:9"},
            "mode": {"type": "string", "description": "text、image、start_end"},
            "image_url": {"type": "string", "description": "image模式使用"},
            "start_image_url": {"type": "string", "description": "start_end模式首帧"},
            "end_image_url": {"type": "string", "description": "start_end模式尾帧"},
        },
        required=["prompt"],
    )
    async def generate_volcano_video(
        self,
        prompt: str,
        duration: Optional[int] = None,
        ratio: str = "16:9",
        mode: str = "text",
        image_url: Optional[str] = None,
        start_image_url: Optional[str] = None,
        end_image_url: Optional[str] = None,
    ) -> ToolResult:
        return await self.core.generate_volcano_video(
            prompt=prompt,
            duration=duration,
            ratio=ratio,
            mode=mode,
            image_url=image_url,
            start_image_url=start_image_url,
            end_image_url=end_image_url,
        )
