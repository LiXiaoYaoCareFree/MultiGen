from typing import Optional

from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool
from .multimodal_core import MultimodalCore


class VirtualAnchorGenerationTool(BaseTool):
    name: str = "virtual_anchor"

    def __init__(self) -> None:
        super().__init__()
        self.core = MultimodalCore()

    @tool(
        name="detect_face",
        description="检测图片中是否有人脸并验证是否适合虚拟人生成。",
        parameters={
            "image_url": {"type": "string", "description": "图片路径或URL"},
            "method": {"type": "string", "description": "检测方法，llm或opencv"},
        },
        required=["image_url"],
    )
    async def detect_face(self, image_url: str, method: Optional[str] = None) -> ToolResult:
        return await self.core.detect_face(image_url, method)

    @tool(
        name="generate_virtual_anchor",
        description="基于图片和音频生成虚拟人口型同步视频。",
        parameters={
            "image_url": {"type": "string", "description": "角色图片路径"},
            "audio_url": {"type": "string", "description": "音频路径"},
            "workflow_path": {"type": "string", "description": "可选工作流JSON路径"},
            "prompt_text": {"type": "string", "description": "可选正向提示词"},
            "negative_prompt": {"type": "string", "description": "可选负向提示词"},
            "seed": {"type": "integer", "description": "可选随机种子"},
            "num_frames": {"type": "integer", "description": "帧数"},
            "fps": {"type": "integer", "description": "帧率"},
            "poll_interval": {"type": "integer", "description": "轮询间隔秒"},
            "wait_for_completion": {"type": "boolean", "description": "是否等待完成"},
        },
        required=["image_url", "audio_url"],
    )
    async def generate_virtual_anchor(
        self,
        image_url: str,
        audio_url: str,
        workflow_path: Optional[str] = None,
        prompt_text: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        num_frames: int = 1450,
        fps: int = 25,
        poll_interval: int = 10,
        wait_for_completion: bool = True,
    ) -> ToolResult:
        return await self.core.generate_virtual_anchor(
            image_url=image_url,
            audio_url=audio_url,
            workflow_path=workflow_path,
            prompt_text=prompt_text,
            negative_prompt=negative_prompt,
            seed=seed,
            num_frames=num_frames,
            fps=fps,
            poll_interval=poll_interval,
            wait_for_completion=wait_for_completion,
        )
