import asyncio
import base64
import importlib
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

import httpx

from app.domain.models.tool_result import ToolResult


class MultimodalCore:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[4]
        self.storage_dir = self.base_dir / "storage"
        self.images_dir = self.storage_dir / "images"
        self.videos_dir = self.storage_dir / "videos"
        self.models_dir = self.storage_dir / "models"
        self.audios_dir = self.storage_dir / "audios"
        self.bgm_dir = self.storage_dir / "bgm"
        self.podcasts_dir = self.storage_dir / "podcasts"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.audios_dir.mkdir(parents=True, exist_ok=True)
        self.bgm_dir.mkdir(parents=True, exist_ok=True)
        self.podcasts_dir.mkdir(parents=True, exist_ok=True)
        self.mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"
        self.mock_image_path = os.getenv("MOCK_IMAGE_PATH", "/storage/images/mock.png").strip()
        self.mock_video_path = os.getenv("MOCK_VIDEO_PATH", "/storage/videos/mock.mp4").strip()
        self.mock_model_path = os.getenv("MOCK_MODEL_PATH", "/storage/models/mock/model.obj").strip()
        self.volcano_api_key = os.getenv("VOLCANO_API_KEY", "").strip()
        self.volcano_base_url = os.getenv("VOLCANO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()
        self.volcano_image_model = os.getenv("VOLCANO_IMAGE_MODEL", "seedream-4.5").strip()
        self.volcano_edit_model = os.getenv("VOLCANO_EDIT_MODEL", self.volcano_image_model).strip()
        self.volcano_video_model = os.getenv("VOLCANO_VIDEO_MODEL", "doubao-seedance-1-5-pro").strip()
        self.volcano_model_name = os.getenv("VOLCANO_MODEL_NAME", "doubao-seed-1-6-251015").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1").strip()
        self.image_model_name = os.getenv("IMAGE_MODEL_NAME", "Qwen/Qwen-Image").strip()
        self.edit_image_model_name = os.getenv("EDIT_IMAGE_MODEL_NAME", "Qwen/Qwen-Image-Edit-2509").strip()
        self.tencent_ai3d_api_key = os.getenv("TENCENT_AI3D_API_KEY", "").strip()
        self.tencent_ai3d_base_url = os.getenv("TENCENT_AI3D_BASE_URL", "https://api.ai3d.cloud.tencent.com").strip()
        self.comfyui_server_address = os.getenv("COMFYUI_SERVER_ADDRESS", "").strip()
        self.comfyui_workflow_path = os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.dashscope_base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").strip()
        self.qwen_voice_design_model = os.getenv("QWEN_VOICE_DESIGN_MODEL", "qwen-voice-design").strip()
        self.qwen_voice_design_target_model = os.getenv("QWEN_VOICE_DESIGN_TARGET_MODEL", "qwen3-tts-vd-2026-01-26").strip()
        self.qwen_voice_enrollment_model = os.getenv("QWEN_VOICE_ENROLLMENT_MODEL", "qwen-voice-enrollment").strip()
        self.qwen_voice_cloning_target_model = os.getenv("QWEN_VOICE_CLONING_TARGET_MODEL", "qwen3-tts-vc-2026-01-22").strip()
        self.qwen_voice_synthesis_model = os.getenv("QWEN_VOICE_SYNTHESIS_MODEL", self.qwen_voice_cloning_target_model).strip()
        self.face_detection_method = os.getenv("FACE_DETECTION_METHOD", "llm").strip().lower()

    @staticmethod
    def _safe_text(text: str, max_length: int = 30) -> str:
        cleaned = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in (text or "")[:max_length])
        return cleaned.replace(" ", "_")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _build_filename(self, prefix: str, text: str, ext: str) -> str:
        uid = str(uuid.uuid4())[:8]
        safe = self._safe_text(text)
        ext = ext if ext.startswith(".") else f".{ext}"
        if safe:
            return f"{prefix}_{self._timestamp()}_{uid}_{safe}{ext}"
        return f"{prefix}_{self._timestamp()}_{uid}{ext}"

    @staticmethod
    def _url_ext(url: str, default_ext: str) -> str:
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1]
        if not ext:
            return default_ext
        return ext if ext.startswith(".") else default_ext

    def _storage_url(self, folder: str, filename: str) -> str:
        return f"/storage/{folder}/{filename}"

    def _local_path(self, storage_path: str) -> Path:
        return self.base_dir / storage_path.lstrip("/")

    async def _download_bytes(self, url: str, timeout: int = 120) -> bytes:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def _download_to(self, url: str, dir_path: Path, folder: str, prefix: str, text: str, default_ext: str) -> str:
        content = await self._download_bytes(url, timeout=300)
        ext = self._url_ext(url, default_ext)
        filename = self._build_filename(prefix, text, ext)
        with open(dir_path / filename, "wb") as f:
            f.write(content)
        return self._storage_url(folder, filename)

    def _save_bytes_to(self, data: bytes, dir_path: Path, folder: str, prefix: str, text: str, ext: str = ".png") -> str:
        filename = self._build_filename(prefix, text, ext)
        with open(dir_path / filename, "wb") as f:
            f.write(data)
        return self._storage_url(folder, filename)

    def _prepare_image_input(self, image_url: str, allow_remote: bool = True) -> str:
        if image_url.startswith("/storage/"):
            fp = self._local_path(image_url)
            if not fp.exists():
                raise FileNotFoundError(f"本地图片不存在: {image_url}")
            with open(fp, "rb") as f:
                data = f.read()
            ext = fp.suffix.lower()
            mime = "image/jpeg"
            if ext == ".png":
                mime = "image/png"
            elif ext == ".webp":
                mime = "image/webp"
            elif ext == ".gif":
                mime = "image/gif"
            return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"
        if allow_remote:
            return image_url
        raise ValueError(f"不支持的图片路径: {image_url}")

    def _prepare_audio_input(self, audio_url: str) -> str:
        if audio_url.startswith("/storage/"):
            fp = self._local_path(audio_url)
            if not fp.exists():
                raise FileNotFoundError(f"本地音频不存在: {audio_url}")
            with open(fp, "rb") as f:
                data = f.read()
            ext = fp.suffix.lower()
            mime = "audio/mpeg"
            if ext == ".wav":
                mime = "audio/wav"
            elif ext == ".m4a":
                mime = "audio/mp4"
            return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"
        return audio_url

    @staticmethod
    def _resolve_face_method(method: Optional[str], default_method: str) -> str:
        final_method = (method or default_method or "llm").strip().lower()
        if final_method not in {"llm", "opencv"}:
            return "llm"
        return final_method

    async def _detect_face_with_opencv(self, image_url: str) -> ToolResult:
        try:
            cv2 = importlib.import_module("cv2")
            np = importlib.import_module("numpy")
        except Exception:
            return ToolResult(success=False, message="未安装 opencv-python 或 numpy")
        try:
            image_bytes = await self._download_bytes(image_url, timeout=60) if image_url.startswith("http") else None
            if image_url.startswith("/storage/"):
                fp = self._local_path(image_url)
                if not fp.exists():
                    return ToolResult(success=False, message=f"图片不存在: {image_url}")
                img = cv2.imread(str(fp))
            elif image_bytes is not None:
                arr = np.frombuffer(image_bytes, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            else:
                fp = Path(image_url)
                if not fp.exists():
                    return ToolResult(success=False, message=f"图片不存在: {image_url}")
                img = cv2.imread(str(fp))
            if img is None:
                return ToolResult(success=False, message="图片读取失败")
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
            face_count = int(len(faces))
            has_face = face_count > 0
            largest_conf = 0.0
            if has_face:
                largest = max(faces, key=lambda x: x[2] * x[3])
                face_area = int(largest[2] * largest[3])
                image_area = int(img.shape[0] * img.shape[1]) if img.shape[0] and img.shape[1] else 1
                ratio = face_area / image_area
                largest_conf = min(max(ratio * 8.0, 0.4), 1.0)
            is_valid = has_face and largest_conf >= 0.5
            message = "检测完成" if has_face else "未检测到清晰正面人脸"
            return ToolResult(
                success=True,
                message="人脸检测完成",
                data={
                    "has_face": has_face,
                    "face_count": face_count,
                    "is_valid": is_valid,
                    "validation_message": message,
                    "method": "opencv",
                    "largest_face": {"confidence": largest_conf} if has_face else None,
                },
            )
        except Exception as e:
            return ToolResult(success=False, message=f"OpenCV 人脸检测失败: {e}", data={"has_face": False, "is_valid": False, "method": "opencv"})

    @staticmethod
    def _image_resp_url(data: Dict[str, Any]) -> Optional[str]:
        if isinstance(data.get("data"), list) and data["data"]:
            return data["data"][0].get("url")
        if isinstance(data.get("images"), list) and data["images"]:
            return data["images"][0].get("url")
        if isinstance(data.get("url"), str):
            return data["url"]
        return None

    @staticmethod
    def _first_image_item(data: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(data.get("data"), list) and data["data"] and isinstance(data["data"][0], dict):
            return data["data"][0]
        if isinstance(data.get("images"), list) and data["images"] and isinstance(data["images"][0], dict):
            return data["images"][0]
        return data if isinstance(data, dict) else {}

    async def _resolve_image_to_local(
        self,
        data: Dict[str, Any],
        prefix: str,
        prompt: str,
        default_ext: str = ".png",
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        item = self._first_image_item(data)
        remote_url = item.get("url") if isinstance(item.get("url"), str) else None
        if remote_url:
            local_url = await self._download_to(remote_url, self.images_dir, "images", prefix, prompt, default_ext)
            return local_url, remote_url, "url"
        b64 = None
        for k in ("b64_json", "b64", "base64", "image_base64"):
            if isinstance(item.get(k), str) and item.get(k):
                b64 = item.get(k)
                break
        if not b64:
            return None, None, None
        if b64.startswith("data:image/"):
            b64 = b64.split(",", 1)[1] if "," in b64 else b64
        image_bytes = base64.b64decode(b64)
        local_url = self._save_bytes_to(image_bytes, self.images_dir, "images", prefix, prompt, default_ext)
        return local_url, None, "base64"

    @staticmethod
    def _json_from_text(text: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text or "")
        if not match:
            return {}
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}

    async def _volcano_post(self, path: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
        if not self.volcano_api_key:
            raise ValueError("未配置 VOLCANO_API_KEY")
        headers = {"Authorization": f"Bearer {self.volcano_api_key}", "Content-Type": "application/json"}
        url = f"{self.volcano_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = resp.text
                raise ValueError(f"火山接口错误[{resp.status_code}]: {detail}") from e
            return resp.json()

    async def _volcano_get(self, path: str, timeout: int = 30) -> Dict[str, Any]:
        if not self.volcano_api_key:
            raise ValueError("未配置 VOLCANO_API_KEY")
        headers = {"Authorization": f"Bearer {self.volcano_api_key}", "Content-Type": "application/json"}
        url = f"{self.volcano_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def generate_image(self, prompt: str) -> ToolResult:
        try:
            if not self.openai_api_key:
                return ToolResult(success=False, message="未配置 OPENAI_API_KEY")
            payload = {"model": self.image_model_name, "prompt": prompt, "image_size": "768x1024"}
            headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.openai_base_url.rstrip('/')}/images/generations", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            local_url, remote_url, source_type = await self._resolve_image_to_local(data, "image", prompt, ".png")
            if not local_url:
                return ToolResult(success=False, message="图片生成返回为空", data=data)
            return ToolResult(
                success=True,
                message="图片生成成功",
                data={"image_url": local_url, "local_path": local_url, "original_url": remote_url, "source_type": source_type, "model": self.image_model_name},
            )
        except Exception as e:
            return ToolResult(success=False, message=f"图片生成失败: {e}")

    async def edit_image(self, prompt: str, image_url: str) -> ToolResult:
        try:
            if not self.openai_api_key:
                return ToolResult(success=False, message="未配置 OPENAI_API_KEY")
            image_input = image_url
            if image_url.startswith("/storage/"):
                base = os.getenv("BASE_URL", "http://localhost:8000").strip()
                image_input = f"{base}{image_url}"
            payload = {"model": self.edit_image_model_name, "prompt": prompt, "image": image_input}
            headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.openai_base_url.rstrip('/')}/images/generations", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            local_url, remote_url, source_type = await self._resolve_image_to_local(data, "image_edit", prompt, ".png")
            if not local_url:
                return ToolResult(success=False, message="图片编辑返回为空", data=data)
            return ToolResult(
                success=True,
                message="图片编辑成功",
                data={
                    "image_url": local_url,
                    "local_path": local_url,
                    "original_url": remote_url,
                    "source_image": image_url,
                    "source_type": source_type,
                    "model": self.edit_image_model_name,
                },
            )
        except Exception as e:
            return ToolResult(success=False, message=f"图片编辑失败: {e}")

    @staticmethod
    def _normalize_volcano_image_size(size: str) -> str:
        raw = (size or "").strip().lower()
        if not raw:
            return "1728x2304"
        mapping = {
            "1:1": "2048x2048",
            "4:3": "2304x1728",
            "3:4": "1728x2304",
            "16:9": "2560x1440",
            "9:16": "1440x2560",
            "21:9": "2940x1260",
            "9:21": "1260x2940",
            "1k": "1k",
            "2k": "2k",
            "4k": "4k",
        }
        if raw in mapping:
            return mapping[raw]
        if re.fullmatch(r"\d{2,5}x\d{2,5}", raw):
            return raw
        return "1728x2304"

    async def generate_volcano_image(self, prompt: str, size: str = "3:4") -> ToolResult:
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"image_url": self.mock_image_path, "mock": True})
            payload = {
                "model": self.volcano_image_model,
                "prompt": prompt,
                "size": self._normalize_volcano_image_size(size),
                "n": 1,
                "response_format": "url",
                "stream": False,
                "watermark": True,
            }
            data = await self._volcano_post("/images/generations", payload)
            remote = self._image_resp_url(data)
            if not remote:
                return ToolResult(success=False, message="火山图片生成返回为空", data=data)
            local = await self._download_to(remote, self.images_dir, "images", "volcano", prompt, ".png")
            return ToolResult(success=True, message="图片生成成功", data={"image_url": local, "local_path": local, "original_url": remote, "provider": "volcano"})
        except Exception as e:
            return ToolResult(success=False, message=f"火山图片生成失败: {e}")

    async def edit_volcano_image(self, prompt: str, image_url: str, size: str = "3:4") -> ToolResult:
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"image_url": self.mock_image_path, "mock": True})
            payload = {
                "model": self.volcano_edit_model,
                "prompt": prompt,
                "image": self._prepare_image_input(image_url, allow_remote=True),
                "size": self._normalize_volcano_image_size(size),
                "response_format": "url",
                "stream": False,
                "watermark": True,
            }
            data = await self._volcano_post("/images/generations", payload)
            remote = self._image_resp_url(data)
            if not remote:
                return ToolResult(success=False, message="火山图片编辑返回为空", data=data)
            local = await self._download_to(remote, self.images_dir, "images", "volcano_edit", prompt, ".png")
            return ToolResult(success=True, message="图片编辑成功", data={"image_url": local, "local_path": local, "original_url": remote, "source_image": image_url, "provider": "volcano"})
        except Exception as e:
            return ToolResult(success=False, message=f"火山图片编辑失败: {e}")

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
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"video_url": self.mock_video_path, "mock": True})
            content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            if mode == "image":
                if not image_url:
                    return ToolResult(success=False, message="image模式缺少image_url")
                content.append({"type": "image_url", "image_url": {"url": self._prepare_image_input(image_url, allow_remote=True)}})
            elif mode == "start_end":
                if not start_image_url or not end_image_url:
                    return ToolResult(success=False, message="start_end模式缺少首尾帧")
                content.append({"type": "image_url", "role": "first_frame", "image_url": {"url": self._prepare_image_input(start_image_url, allow_remote=True)}})
                content.append({"type": "image_url", "role": "last_frame", "image_url": {"url": self._prepare_image_input(end_image_url, allow_remote=True)}})
            payload: Dict[str, Any] = {
                "model": self.volcano_video_model,
                "content": content,
                "ratio": ratio,
                "watermark": False,
                "resolution": "720p",
                "audio": True,
            }
            if duration:
                payload["duration"] = duration
            submit = await self._volcano_post("/contents/generations/tasks", payload, timeout=60)
            task_id = submit.get("id")
            if not task_id:
                return ToolResult(success=False, message="视频任务提交失败", data=submit)
            remote_video = None
            for _ in range(120):
                detail = await self._volcano_get(f"/contents/generations/tasks/{task_id}")
                status = str(detail.get("status", "")).lower()
                if status in {"succeeded", "success", "completed", "done", "finished"}:
                    content_data = detail.get("content") if isinstance(detail.get("content"), dict) else {}
                    remote_video = content_data.get("video_url") or detail.get("video_url")
                    if remote_video:
                        break
                if status in {"failed", "error", "cancelled", "canceled"}:
                    return ToolResult(success=False, message=f"视频生成失败: {detail}")
                await asyncio.sleep(5)
            if not remote_video:
                return ToolResult(success=False, message="视频生成超时")
            local = await self._download_to(remote_video, self.videos_dir, "videos", "volcano", prompt, ".mp4")
            return ToolResult(success=True, message="视频生成成功", data={"video_url": local, "local_path": local, "original_url": remote_video, "task_id": task_id, "provider": "volcano"})
        except Exception as e:
            return ToolResult(success=False, message=f"火山视频生成失败: {e}")

    async def concatenate_videos(self, video_urls: List[str], output_filename: Optional[str] = None) -> ToolResult:
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"video_url": self.mock_video_path, "mock": True})
            if len(video_urls) < 2:
                return ToolResult(success=False, message="至少需要2个视频片段")
            moviepy_mod = importlib.import_module("moviepy")
            video_clip = getattr(moviepy_mod, "VideoFileClip", None)
            concat = getattr(moviepy_mod, "concatenate_videoclips", None)
            if video_clip is None or concat is None:
                editor = importlib.import_module("moviepy.editor")
                video_clip = getattr(editor, "VideoFileClip", None)
                concat = getattr(editor, "concatenate_videoclips", None)
            if video_clip is None or concat is None:
                return ToolResult(success=False, message="moviepy 不可用")
            files: List[Path] = []
            temp: List[Path] = []
            for url in video_urls:
                if url.startswith("/storage/"):
                    fp = self._local_path(url)
                    if not fp.exists():
                        return ToolResult(success=False, message=f"视频文件不存在: {url}")
                    files.append(fp)
                else:
                    data = await self._download_bytes(url, timeout=300)
                    ext = self._url_ext(url, ".mp4")
                    name = self._build_filename("temp_video", "", ext)
                    fp = self.videos_dir / name
                    with open(fp, "wb") as f:
                        f.write(data)
                    files.append(fp)
                    temp.append(fp)
            clips = []
            final_clip = None
            target_size = None
            target_fps = None
            try:
                for i, fp in enumerate(files):
                    clip = video_clip(str(fp))
                    if i == 0:
                        target_size = clip.size
                        target_fps = clip.fps
                    else:
                        if clip.size != target_size:
                            clip = clip.resized(target_size) if hasattr(clip, "resized") else clip.resize(target_size)
                        if clip.fps != target_fps:
                            clip = clip.with_fps(target_fps) if hasattr(clip, "with_fps") else clip.set_fps(target_fps)
                    clips.append(clip)
                final_clip = concat(clips, method="compose")
                if not output_filename:
                    output_filename = self._build_filename("concatenated", "", ".mp4")
                if not output_filename.endswith(".mp4"):
                    output_filename = f"{output_filename}.mp4"
                out = self.videos_dir / output_filename
                final_clip.write_videofile(str(out), codec="libx264", audio_codec="aac", fps=target_fps, preset="medium")
            finally:
                for c in clips:
                    try:
                        c.close()
                    except Exception:
                        pass
                if final_clip is not None:
                    try:
                        final_clip.close()
                    except Exception:
                        pass
                for fp in temp:
                    fp.unlink(missing_ok=True)
            result_url = self._storage_url("videos", output_filename)
            return ToolResult(success=True, message="视频拼接成功", data={"video_url": result_url, "local_path": result_url, "video_count": len(video_urls)})
        except Exception as e:
            return ToolResult(success=False, message=f"视频拼接失败: {e}")

    async def generate_3d_model(self, prompt: Optional[str], image_url: Optional[str], format: Literal["obj", "glb"]) -> ToolResult:
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"model_url": self.mock_model_path, "preview_url": self.mock_model_path, "mock": True})
            if not prompt and not image_url:
                return ToolResult(success=False, message="prompt 与 image_url 至少提供一个")
            if prompt and image_url:
                return ToolResult(success=False, message="prompt 与 image_url 不能同时提供")
            if not self.tencent_ai3d_api_key:
                return ToolResult(success=False, message="未配置 TENCENT_AI3D_API_KEY")
            submit_url = f"{self.tencent_ai3d_base_url.rstrip('/')}/v1/ai3d/submit"
            query_url = f"{self.tencent_ai3d_base_url.rstrip('/')}/v1/ai3d/query"
            payload: Dict[str, Any] = {
                "Prompt": prompt if prompt else None,
                "ImageBase64": None,
                "ImageUrl": None,
                "MultiViewImages": None,
                "EnablePBR": None,
                "FaceCount": None,
                "GenerateType": None,
                "PolygonType": None,
            }
            if image_url:
                payload["Prompt"] = None
                if image_url.startswith("/storage/"):
                    fp = self._local_path(image_url)
                    if not fp.exists():
                        return ToolResult(success=False, message=f"图片不存在: {image_url}")
                    with open(fp, "rb") as f:
                        payload["ImageBase64"] = base64.b64encode(f.read()).decode("utf-8")
                else:
                    payload["ImageUrl"] = image_url
            headers = {"Authorization": self.tencent_ai3d_api_key, "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=60) as client:
                submit_resp = await client.post(submit_url, json=payload, headers=headers)
                submit_resp.raise_for_status()
                submit_data = submit_resp.json()
            rd = submit_data.get("Response") if isinstance(submit_data.get("Response"), dict) else submit_data
            job_id = rd.get("JobId") or rd.get("job_id") or rd.get("jobId")
            if not job_id:
                return ToolResult(success=False, message="3D任务提交失败", data=submit_data)
            result_data = None
            for _ in range(100):
                async with httpx.AsyncClient(timeout=30) as client:
                    query_resp = await client.post(query_url, json={"JobId": job_id}, headers=headers)
                    query_resp.raise_for_status()
                    query_data = query_resp.json()
                qd = query_data.get("Response") if isinstance(query_data.get("Response"), dict) else query_data
                status = str(qd.get("Status") or qd.get("status") or qd.get("State") or "").upper()
                if status in {"SUCCESS", "COMPLETED", "DONE"}:
                    result_files = qd.get("ResultFile3Ds") or qd.get("result_file_3ds") or []
                    if result_files:
                        result_data = qd
                        break
                if status in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
                    return ToolResult(success=False, message=f"3D生成失败: {qd}")
                await asyncio.sleep(3)
            if not result_data:
                return ToolResult(success=False, message="3D生成超时")
            files = result_data.get("ResultFile3Ds") or result_data.get("result_file_3ds") or []
            item = None
            target = format.upper()
            for f in files:
                if str(f.get("Type") or f.get("type") or "").upper() == target:
                    item = f
                    break
            if item is None and files:
                item = files[0]
            if not item:
                return ToolResult(success=False, message="未找到3D模型文件")
            model_url = item.get("Url") or item.get("url")
            preview_url = item.get("PreviewImageUrl") or item.get("preview_image_url")
            if not model_url:
                return ToolResult(success=False, message="3D模型URL为空")
            folder_name = f"{self._timestamp()}_{str(uuid.uuid4())[:8]}"
            folder = self.models_dir / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            ext = self._url_ext(model_url, ".zip" if format == "obj" else ".glb")
            temp_model = folder / f"temp{ext}"
            with open(temp_model, "wb") as f:
                f.write(await self._download_bytes(model_url, timeout=180))
            model_http = ""
            mtl_http = None
            texture_http = None
            if ext.lower() == ".zip":
                extract_dir = folder / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(temp_model, "r") as zf:
                    zf.extractall(extract_dir)
                obj_file = None
                mtl_file = None
                texture_file = None
                for p in extract_dir.rglob("*"):
                    if p.is_file():
                        lower = p.name.lower()
                        if lower.endswith(".obj") and obj_file is None:
                            obj_file = p
                        elif lower.endswith(".mtl") and mtl_file is None:
                            mtl_file = p
                        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")) and texture_file is None:
                            texture_file = p
                if not obj_file:
                    return ToolResult(success=False, message="ZIP中未找到obj文件")
                target_obj = folder / "model.obj"
                shutil.copy2(obj_file, target_obj)
                model_http = f"/storage/models/{folder_name}/model.obj"
                if mtl_file:
                    target_mtl = folder / "model.mtl"
                    shutil.copy2(mtl_file, target_mtl)
                    mtl_http = f"/storage/models/{folder_name}/model.mtl"
                if texture_file:
                    target_tex = folder / f"texture{texture_file.suffix.lower()}"
                    shutil.copy2(texture_file, target_tex)
                    texture_http = f"/storage/models/{folder_name}/{target_tex.name}"
                temp_model.unlink(missing_ok=True)
                shutil.rmtree(extract_dir, ignore_errors=True)
            else:
                target_glb = folder / "model.glb"
                shutil.move(str(temp_model), str(target_glb))
                model_http = f"/storage/models/{folder_name}/model.glb"
            preview_http = model_http
            if preview_url:
                try:
                    pv_ext = self._url_ext(preview_url, ".png")
                    pv_name = f"preview{pv_ext}"
                    pv_path = folder / pv_name
                    with open(pv_path, "wb") as f:
                        f.write(await self._download_bytes(preview_url, timeout=60))
                    preview_http = f"/storage/models/{folder_name}/{pv_name}"
                except Exception:
                    preview_http = model_http
            data = {"model_url": model_http, "local_path": model_http, "preview_url": preview_http, "job_id": job_id}
            if mtl_http:
                data["mtl_url"] = mtl_http
            if texture_http:
                data["texture_url"] = texture_http
            return ToolResult(success=True, message="3D模型生成成功", data=data)
        except Exception as e:
            return ToolResult(success=False, message=f"3D模型生成失败: {e}")

    async def detect_face(self, image_url: str, method: Optional[str] = None) -> ToolResult:
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"has_face": True, "face_count": 1, "is_valid": True, "validation_message": "mock", "method": "mock"})
            final_method = self._resolve_face_method(method, self.face_detection_method)
            if final_method == "opencv":
                return await self._detect_face_with_opencv(image_url)
            payload = {
                "model": self.volcano_model_name,
                "thinking": {"type": "disabled"},
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": self._prepare_image_input(image_url, allow_remote=True)},
                        {"type": "input_text", "text": "请判断图片是否包含清晰正面人脸，并返回JSON：has_face(bool),face_count(int),is_clear(bool),suitable_for_virtual_anchor(bool),message(str)"},
                    ],
                }],
            }
            data = await self._volcano_post("/responses", payload, timeout=60)
            text = ""
            output = data.get("output")
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    if isinstance(item.get("summary"), list):
                        for summary in item["summary"]:
                            if isinstance(summary, dict) and isinstance(summary.get("text"), str):
                                text += summary["text"] + "\n"
                    if isinstance(item.get("text"), str):
                        text += item["text"] + "\n"
                    if isinstance(item.get("content"), list):
                        for c in item["content"]:
                            if isinstance(c, dict) and isinstance(c.get("text"), str):
                                text += c["text"] + "\n"
            result = self._json_from_text(text)
            has_face = bool(result.get("has_face", False))
            face_count = int(result.get("face_count", 1 if has_face else 0))
            is_clear = bool(result.get("is_clear", has_face))
            suitable = bool(result.get("suitable_for_virtual_anchor", has_face and is_clear))
            return ToolResult(
                success=True,
                message="人脸检测完成",
                data={
                    "has_face": has_face,
                    "face_count": face_count,
                    "is_valid": suitable,
                    "validation_message": result.get("message", "检测完成"),
                    "method": final_method,
                    "largest_face": {"confidence": 1.0 if is_clear else 0.5} if has_face else None,
                    "llm_analysis": result,
                },
            )
        except Exception as e:
            return ToolResult(success=False, message=f"人脸检测失败: {e}", data={"has_face": False, "is_valid": False})

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
        try:
            if self.mock_mode:
                return ToolResult(success=True, message="mock", data={"video_url": self.mock_video_path, "provider": "comfyui", "mock": True})
            if not self.comfyui_server_address:
                return ToolResult(success=False, message="未配置 COMFYUI_SERVER_ADDRESS")
            server = self.comfyui_server_address
            if not server.startswith("http"):
                server = f"https://{server}"
            wf = workflow_path or self.comfyui_workflow_path
            if not wf:
                return ToolResult(success=False, message="未配置 workflow_path")
            wf_path = Path(wf)
            if not wf_path.is_absolute():
                wf_path = self.base_dir / wf.lstrip("/")
            if not wf_path.exists():
                return ToolResult(success=False, message=f"工作流文件不存在: {wf_path}")
            img_path = self._local_path(image_url) if image_url.startswith("/storage/") else Path(image_url)
            aud_path = self._local_path(audio_url) if audio_url.startswith("/storage/") else Path(audio_url)
            if not img_path.exists():
                return ToolResult(success=False, message=f"图片不存在: {image_url}")
            if not aud_path.exists():
                return ToolResult(success=False, message=f"音频不存在: {audio_url}")
            async with httpx.AsyncClient(timeout=120) as client:
                with open(img_path, "rb") as f:
                    up_img = await client.post(f"{server}/upload/image", files={"image": (img_path.name, f, "application/octet-stream")})
                up_img.raise_for_status()
                uploaded_image = up_img.json().get("name")
                with open(aud_path, "rb") as f:
                    up_aud = await client.post(f"{server}/upload/image", files={"image": (aud_path.name, f, "application/octet-stream")})
                up_aud.raise_for_status()
                uploaded_audio = up_aud.json().get("name")
            if not uploaded_image or not uploaded_audio:
                return ToolResult(success=False, message="上传素材到ComfyUI失败")
            with open(wf_path, "r", encoding="utf-8") as f:
                workflow_data = json.load(f)
            try:
                workflow_data["133"]["inputs"]["image"] = uploaded_image
                workflow_data["125"]["inputs"]["audio"] = uploaded_audio
                if prompt_text:
                    workflow_data["135"]["inputs"]["positive_prompt"] = prompt_text
                if negative_prompt:
                    workflow_data["135"]["inputs"]["negative_prompt"] = negative_prompt
                if seed is not None:
                    workflow_data["128"]["inputs"]["seed"] = seed
                workflow_data["194"]["inputs"]["num_frames"] = num_frames
                workflow_data["194"]["inputs"]["fps"] = fps
                workflow_data["131"]["inputs"]["frame_rate"] = fps
            except Exception:
                pass
            payload = {"prompt": workflow_data, "client_id": str(uuid.uuid4())}
            async with httpx.AsyncClient(timeout=60) as client:
                queue_resp = await client.post(f"{server}/prompt", json=payload)
                queue_resp.raise_for_status()
                queue_data = queue_resp.json()
            prompt_id = queue_data.get("prompt_id")
            if not prompt_id:
                return ToolResult(success=False, message="ComfyUI未返回prompt_id", data=queue_data)
            if not wait_for_completion:
                return ToolResult(success=True, message="任务已提交", data={"prompt_id": prompt_id, "provider": "comfyui"})
            outputs = None
            elapsed = 0
            while elapsed < 3600:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        history_resp = await client.get(f"{server}/history/{prompt_id}")
                        history_resp.raise_for_status()
                        history = history_resp.json()
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        if outputs:
                            break
                except Exception:
                    continue
            if not outputs:
                return ToolResult(success=False, message="虚拟人生成超时", data={"prompt_id": prompt_id})
            filename = None
            subfolder = ""
            for _, out in outputs.items():
                if isinstance(out, dict):
                    if isinstance(out.get("gifs"), list) and out["gifs"]:
                        item = out["gifs"][0]
                        filename = item.get("filename")
                        subfolder = item.get("subfolder", "")
                        break
                    if isinstance(out.get("images"), list) and out["images"]:
                        item = out["images"][0]
                        filename = item.get("filename")
                        subfolder = item.get("subfolder", "")
                        break
            if not filename:
                return ToolResult(success=False, message="未找到ComfyUI输出文件", data={"prompt_id": prompt_id})
            params = {"filename": filename, "subfolder": subfolder, "type": "output"}
            async with httpx.AsyncClient(timeout=300) as client:
                view_resp = await client.get(f"{server}/view", params=params)
                view_resp.raise_for_status()
                video_bin = view_resp.content
            local_name = self._build_filename("virtual_anchor", "", ".mp4")
            with open(self.videos_dir / local_name, "wb") as f:
                f.write(video_bin)
            video_url = self._storage_url("videos", local_name)
            return ToolResult(success=True, message="虚拟人视频生成成功", data={"video_url": video_url, "prompt_id": prompt_id, "provider": "comfyui"})
        except Exception as e:
            return ToolResult(success=False, message=f"虚拟人视频生成失败: {e}")

    async def qwen_voice_design(self, voice_description: str, text: str, language: str = "zh") -> ToolResult:
        try:
            if not self.dashscope_api_key:
                return ToolResult(success=False, message="未配置 DASHSCOPE_API_KEY")
            payload = {
                "model": self.qwen_voice_design_model,
                "input": {
                    "action": "create",
                    "target_model": self.qwen_voice_design_target_model,
                    "voice_prompt": voice_description,
                    "preview_text": text,
                    "preferred_name": f"vd{uuid.uuid4().hex[:8]}",
                    "language": language,
                },
                "parameters": {"sample_rate": 24000, "response_format": "wav"},
            }
            headers = {"Authorization": f"Bearer {self.dashscope_api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.dashscope_base_url.rstrip('/')}/api/v1/services/audio/tts/customization", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            base64_audio = (((data.get("output") or {}).get("preview_audio") or {}).get("data")) if isinstance(data, dict) else None
            if not base64_audio:
                return ToolResult(success=False, message="声音设计返回为空", data=data)
            filename = self._build_filename("voice_design", text, ".wav")
            with open(self.audios_dir / filename, "wb") as f:
                f.write(base64.b64decode(base64_audio))
            url = self._storage_url("audios", filename)
            return ToolResult(success=True, message="声音设计成功", data={"audio_url": url, "local_path": url, "voice_name": (data.get("output") or {}).get("voice"), "provider": "qwen-tts-voice-design"})
        except Exception as e:
            return ToolResult(success=False, message=f"声音设计失败: {e}")

    async def qwen_voice_cloning(self, reference_audio: str, text: str, language: str = "zh") -> ToolResult:
        try:
            if not self.dashscope_api_key:
                return ToolResult(success=False, message="未配置 DASHSCOPE_API_KEY")
            headers = {"Authorization": f"Bearer {self.dashscope_api_key}", "Content-Type": "application/json"}
            create_payload = {
                "model": self.qwen_voice_enrollment_model,
                "input": {
                    "action": "create",
                    "target_model": self.qwen_voice_cloning_target_model,
                    "preferred_name": f"vc{uuid.uuid4().hex[:8]}",
                    "audio": {"data": self._prepare_audio_input(reference_audio)},
                    "language": language,
                },
            }
            async with httpx.AsyncClient(timeout=120) as client:
                create_resp = await client.post(
                    f"{self.dashscope_base_url.rstrip('/')}/api/v1/services/audio/tts/customization",
                    json=create_payload,
                    headers=headers,
                )
                create_resp.raise_for_status()
                create_data = create_resp.json()
            voice_name = ((create_data.get("output") or {}).get("voice")) if isinstance(create_data, dict) else None
            if not voice_name:
                return ToolResult(success=False, message="未获取到复刻音色", data=create_data)
            synth_payload = {"model": self.qwen_voice_synthesis_model, "input": {"text": text, "voice": voice_name, "language_type": "Auto"}}
            async with httpx.AsyncClient(timeout=180) as client:
                synth_resp = await client.post(
                    f"{self.dashscope_base_url.rstrip('/')}/api/v1/services/aigc/multimodal-generation/generation",
                    json=synth_payload,
                    headers=headers,
                )
                synth_resp.raise_for_status()
                synth_data = synth_resp.json()
            remote_audio = (((synth_data.get("output") or {}).get("audio") or {}).get("url")) if isinstance(synth_data, dict) else None
            if not remote_audio:
                return ToolResult(success=False, message="语音合成返回为空", data=synth_data)
            ext = ".wav" if ".wav" in remote_audio else ".mp3"
            local_audio = await self._download_to(remote_audio, self.audios_dir, "audios", "voice_cloning", text, ext)
            return ToolResult(success=True, message="声音复刻成功", data={"audio_url": local_audio, "local_path": local_audio, "original_url": remote_audio, "voice_name": voice_name, "provider": "qwen-tts-voice-cloning"})
        except Exception as e:
            return ToolResult(success=False, message=f"声音复刻失败: {e}")

    async def concatenate_audio(self, audio_files: List[str], crossfade_duration: int = 200, silence_duration: int = 1200) -> ToolResult:
        try:
            if len(audio_files) < 2:
                return ToolResult(success=False, message="至少需要2个音频文件")
            try:
                from pydub import AudioSegment
            except Exception:
                return ToolResult(success=False, message="未安装 pydub")
            segs = []
            for item in audio_files:
                fp = self._local_path(item) if item.startswith("/storage/") else Path(item)
                if not fp.exists():
                    return ToolResult(success=False, message=f"文件不存在: {item}")
                segs.append(AudioSegment.from_file(str(fp)))
            merged = segs[0]
            for seg in segs[1:]:
                if crossfade_duration > 0:
                    merged = merged.append(seg, crossfade=crossfade_duration)
                else:
                    if silence_duration > 0:
                        merged = merged + AudioSegment.silent(duration=silence_duration) + seg
                    else:
                        merged = merged + seg
            name = self._build_filename("concatenated", "", ".wav")
            merged.export(str(self.audios_dir / name), format="wav")
            path = self._storage_url("audios", name)
            return ToolResult(success=True, message="音频拼接成功", data={"audio_url": path, "local_path": path, "duration_seconds": len(merged) / 1000.0, "file_count": len(audio_files)})
        except Exception as e:
            return ToolResult(success=False, message=f"音频拼接失败: {e}")

    async def select_background_music(self, scene_description: str, duration_seconds: Optional[float] = None) -> ToolResult:
        try:
            candidates = list(self.bgm_dir.glob("*.mp3")) + list(self.bgm_dir.glob("*.wav"))
            if not candidates:
                return ToolResult(success=False, message=f"BGM目录为空: {self.bgm_dir}")
            words = [w for w in scene_description.lower().split() if w]
            best = candidates[0]
            best_score = -1
            for item in candidates:
                name = item.stem.lower()
                score = sum(1 for w in words if w in name)
                if score > best_score:
                    best = item
                    best_score = score
            bgm_path = best
            original_duration = None
            adjusted_duration = None
            if duration_seconds and duration_seconds > 0:
                try:
                    from pydub import AudioSegment
                except Exception:
                    return ToolResult(success=False, message="未安装 pydub")
                bgm = AudioSegment.from_file(str(best))
                original_duration = len(bgm) / 1000.0
                target = int(duration_seconds * 1000)
                if len(bgm) < target:
                    loops = target // len(bgm) + 1
                    bgm = (bgm * loops)[:target]
                else:
                    bgm = bgm[:target]
                bgm = bgm.fade_out(duration=2000)
                name = self._build_filename("bgm", best.stem, ".mp3")
                bgm_path = self.audios_dir / name
                bgm.export(str(bgm_path), format="mp3")
                adjusted_duration = len(bgm) / 1000.0
            url = f"/storage/bgm/{bgm_path.name}" if bgm_path.parent == self.bgm_dir else f"/storage/audios/{bgm_path.name}"
            return ToolResult(success=True, message="BGM选择成功", data={"bgm_path": url, "bgm_name": best.stem, "match_score": best_score, "original_duration": original_duration, "adjusted_duration": adjusted_duration})
        except Exception as e:
            return ToolResult(success=False, message=f"BGM选择失败: {e}")

    async def mix_audio_with_bgm(
        self,
        voice_audio: str,
        bgm_audio: str,
        bgm_volume: float = -26,
        intro_duration: float = 3.0,
        normalize: bool = True,
    ) -> ToolResult:
        try:
            try:
                from pydub import AudioSegment
                from pydub.effects import normalize as normalize_audio
            except Exception:
                return ToolResult(success=False, message="未安装 pydub")
            voice_path = self._local_path(voice_audio) if voice_audio.startswith("/storage/") else Path(voice_audio)
            bgm_path = self._local_path(bgm_audio) if bgm_audio.startswith("/storage/") else Path(bgm_audio)
            if not voice_path.exists():
                return ToolResult(success=False, message=f"主音频不存在: {voice_audio}")
            if not bgm_path.exists():
                return ToolResult(success=False, message=f"BGM不存在: {bgm_audio}")
            voice = AudioSegment.from_file(str(voice_path))
            bgm = AudioSegment.from_file(str(bgm_path))
            intro_ms = int(intro_duration * 1000)
            total_ms = intro_ms + len(voice)
            if len(bgm) < total_ms:
                loops = total_ms // len(bgm) + 1
                bgm = (bgm * loops)[:total_ms]
            else:
                bgm = bgm[:total_ms]
            fade_ms = 2000
            if intro_ms + fade_ms < len(bgm):
                head = bgm[:intro_ms]
                fade = bgm[intro_ms:intro_ms + fade_ms]
                tail = bgm[intro_ms + fade_ms:] + bgm_volume
                step_count = 20
                step_ms = fade_ms // step_count
                fade_out = AudioSegment.empty()
                for i in range(step_count):
                    part = fade[i * step_ms:min((i + 1) * step_ms, len(fade))]
                    gain = bgm_volume * (i / step_count)
                    fade_out += part + gain
                bgm_final = head + fade_out + tail
            else:
                bgm_final = bgm[:intro_ms] + (bgm[intro_ms:] + bgm_volume)
            bgm_final = bgm_final.fade_out(duration=3000)
            voice_track = AudioSegment.silent(duration=intro_ms) + voice
            if len(voice_track) > len(bgm_final):
                voice_track = voice_track[:len(bgm_final)]
            elif len(voice_track) < len(bgm_final):
                bgm_final = bgm_final[:len(voice_track)]
            mixed = bgm_final.overlay(voice_track)
            if normalize:
                mixed = normalize_audio(mixed)
            name = self._build_filename("podcast", "", ".mp3")
            mixed.export(str(self.podcasts_dir / name), format="mp3", bitrate="192k")
            out = self._storage_url("podcasts", name)
            return ToolResult(success=True, message="混音成功", data={"audio_url": out, "local_path": out, "duration_seconds": len(mixed) / 1000.0, "voice_audio": voice_audio, "bgm_audio": bgm_audio})
        except Exception as e:
            return ToolResult(success=False, message=f"混音失败: {e}")
