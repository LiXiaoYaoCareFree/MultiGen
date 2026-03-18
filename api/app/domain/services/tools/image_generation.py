from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class ImageGenerationTool(BaseTool):
    name: str = "image_generation"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="generate_image",
        description="AI绘画服务，输入提示词生成图片。",
        parameters={
            "prompt": {"type": "string", "description": "图片生成提示词"},
        },
        required=["prompt"],
    )
    async def generate_image(self, prompt: str) -> ToolResult:
        return await self.core.generate_image(prompt)

    @tool(
        name="edit_image",
        description="基于已有图片和提示词进行图片编辑。",
        parameters={
            "prompt": {"type": "string", "description": "图片编辑提示词"},
            "image_url": {"type": "string", "description": "图片路径或URL"},
        },
        required=["prompt", "image_url"],
    )
    async def edit_image(self, prompt: str, image_url: str) -> ToolResult:
        return await self.core.edit_image(prompt, image_url)
