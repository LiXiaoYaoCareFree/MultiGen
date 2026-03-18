from typing import Literal, Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class Model3DGenerationTool(BaseTool):
    name: str = "model_3d"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="generate_3d_model",
        description="生成3D模型，支持文生3D和图生3D。",
        parameters={
            "prompt": {"type": "string", "description": "文生3D提示词"},
            "image_url": {"type": "string", "description": "图生3D图片路径或URL"},
            "format": {"type": "string", "description": "obj 或 glb"},
        },
        required=[],
    )
    async def generate_3d_model(
        self,
        prompt: Optional[str] = None,
        image_url: Optional[str] = None,
        format: Literal["obj", "glb"] = "obj",
    ) -> ToolResult:
        return await self.core.generate_3d_model(prompt, image_url, format)
