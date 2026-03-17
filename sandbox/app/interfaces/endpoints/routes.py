from fastapi import APIRouter

from . import file, shell, supervisor


def create_api_routes() -> APIRouter:
    """创建API路由，涵盖整个沙箱项目的所有API"""
    # 1.创建APIRouter实例
    api_router = APIRouter()

    # 2.将各个模块的路由添加/集成进来
    api_router.include_router(file.router)
    api_router.include_router(shell.router)
    api_router.include_router(supervisor.router)

    return api_router


router = create_api_routes()
