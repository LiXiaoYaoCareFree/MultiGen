from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class VolcanoImageGenerationTool(BaseTool):
    name: str = "volcano_image"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="generate_volcano_image",
        description="火山引擎图片生成工具。",
        parameters={
            "prompt": {"type": "string", "description": "图片生成提示词"},
            "size": {"type": "string", "description": "尺寸，如3:4、16:9"},
        },
        required=["prompt"],
    )
    async def generate_volcano_image(self, prompt: str, size: str = "3:4") -> ToolResult:
        return await self.core.generate_volcano_image(prompt, size)

    @tool(
        name="edit_volcano_image",
        description="火山引擎图片编辑工具。",
        parameters={
            "prompt": {"type": "string", "description": "图片编辑提示词"},
            "image_url": {"type": "string", "description": "图片路径或URL"},
            "size": {"type": "string", "description": "尺寸，如3:4、16:9"},
        },
        required=["prompt", "image_url"],
    )
    async def edit_volcano_image(self, prompt: str, image_url: str, size: str = "3:4") -> ToolResult:
        return await self.core.edit_volcano_image(prompt, image_url, size)
