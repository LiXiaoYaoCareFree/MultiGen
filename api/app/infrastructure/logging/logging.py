import logging
import sys
from datetime import datetime
from pathlib import Path

from core.config import get_settings

LOG_ROOT_DIR = Path("/app/logs/project")


class DailyFolderFileHandler(logging.Handler):
    def __init__(self, base_dir: Path, filename: str, encoding: str = "utf-8") -> None:
        super().__init__()
        self.base_dir = base_dir
        self.filename = filename
        self.encoding = encoding

    def emit(self, record: logging.LogRecord) -> None:
        try:
            dt = datetime.fromtimestamp(record.created)
            folder = dt.strftime("%m-%d")
            target_dir = self.base_dir / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            log_file = target_dir / self.filename
            message = self.format(record)
            with open(log_file, "a", encoding=self.encoding) as f:
                f.write(message + "\n")
        except Exception:
            self.handleError(record)


def setup_logging():
    """配置MultiGen项目的日志系统，涵盖日志等级、输出格式、输出渠道等"""
    # 1.获取项目配置
    settings = get_settings()

    # 2.获取根日志处理器
    root_logger = logging.getLogger()

    # 3.清除已有的handlers，避免uvicorn的dictConfig重配置后产生冲突或重复
    root_logger.handlers.clear()

    # 4.设置根日志处理器等级
    log_level = getattr(logging, settings.log_level)
    root_logger.setLevel(log_level)

    # 5.日志输出格式定义
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 6.创建控制台日志输出处理器(使用stderr，stderr在Python中始终无缓冲，Docker中更可靠)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    file_handler = DailyFolderFileHandler(base_dir=LOG_ROOT_DIR, filename="api.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # 7.将控制台日志处理器添加到根日志处理器中
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    root_logger.info("日志系统初始化完成")
