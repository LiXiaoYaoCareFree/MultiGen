import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.middleware import auto_extend_timeout_middleware
from app.interfaces.endpoints.routes import router
from app.interfaces.errors.exception_handler import register_exception_handlers


def setup_logging() -> None:
    """设置沙箱API应用日志"""
    # 1.获取项目配置
    settings = get_settings()

    # 2.获取根日志处理器
    root_logger = logging.getLogger()

    # 3.设置根日志处理器等级
    log_level = getattr(logging, settings.log_level)
    root_logger.setLevel(log_level)

    # 4.日志输出格式定义
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 5.创建控制台日志输出处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 6.将控制台日志处理器添加到根日志处理器中
    root_logger.addHandler(console_handler)

    root_logger.info("沙箱系统系统日志模块初始化完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI生命周期上下文管理器"""
    # 1.应用开始运行之前的操作
    logger.info("MultiGen沙箱正在初始化")

    try:
        # 2.lifespan关键节点
        yield
    finally:
        # 3.应用结束后的操作
        logger.info("MultiGen沙箱关闭成功")


# 1.初始化日志系统
setup_logging()
logger = logging.getLogger(__name__)

# 2.定义FastAPI路由tags标签
openapi_tags = [
    {
        "name": "文件模块",
        "description": "包含 **文件增删改查** 等 API 接口，用于实现对沙箱文件的操作。",
    },
    {
        "name": "Shell模块",
        "description": "包含 **执行/查看Shell** 等 API 接口，用于实现操控沙箱内部的 Shell 命令。",
    },
    {
        "name": "Supervisor模块",
        "description": "使用接口+Supervisor实现管理沙箱系统的程序逻辑",
    },
]

# 3.实例化FastAPI项目实例
app = FastAPI(
    title="MultiGen沙箱系统",
    description="该沙箱系统中预装了Chrome、Python、Node.js，支持运行 Shell 命令、文件管理等功能",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
    version="1.0.0",
)

# 4.添加自动扩展和CORS中间件
app.middleware("http")(auto_extend_timeout_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5.注册错误并处理
register_exception_handlers(app)

# 6.集成路由
app.include_router(router, prefix="/api")
