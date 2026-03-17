import logging
import urllib.parse

from fastapi import APIRouter, UploadFile, File, Depends
from starlette.responses import StreamingResponse

from app.application.services.file_service import FileService
from app.domain.models.file import File as FileInfo
from app.interfaces.schemas import Response
from app.interfaces.service_dependencies import get_file_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["文件模块"])


@router.post(
    path="",
    response_model=Response[FileInfo],
    summary="对话文件上传接口",
    description="在对话接口中，将文件上传到cos对象存储和沙箱中"
)
async def upload_file(
        file: UploadFile = File(...),
        file_service: FileService = Depends(get_file_service),
) -> Response[FileInfo]:
    """文件上传接口，传递文件返回文件的File信息"""
    fileinfo = await file_service.upload_file(upload_file=file)
    return Response.success(
        msg="上传文件成功",
        data=fileinfo,
    )


@router.get(
    path="/{file_id}",
    response_model=Response[FileInfo],
    summary="获取文件信息接口",
    description="获取指定会话中对应文件的基础信息",
)
async def get_file_info(
        file_id: str,
        file_service: FileService = Depends(get_file_service),
) -> Response[FileInfo]:
    """获取指定会话中对应文件的基础信息"""
    fileinfo = await file_service.get_file_info(file_id)
    return Response.success(
        msg="获取文件信息成功",
        data=fileinfo,
    )


@router.get(
    path="/{file_id}/download",
    summary="文件下载接口",
    description="从沙箱or对象存储中下载指定的文件到本地",
)
async def download_file(
        file_id: str,
        file_service: FileService = Depends(get_file_service),
) -> StreamingResponse:
    """下载指定会话中的指定文件"""
    # 1.调用服务获取文件源数据
    file_data, fileinfo = await file_service.download_file(file_id)

    # 2.对文件中的中文名字进行url编码
    encoded_filename = urllib.parse.quote(fileinfo.filename)

    # 3.返回文件流数据
    return StreamingResponse(
        content=file_data,
        media_type=fileinfo.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}",
            "Content-Length": str(fileinfo.size)
        }
    )
