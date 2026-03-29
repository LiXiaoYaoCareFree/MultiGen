"""
会话错误日志工具
将错误日志记录到 logs/sessions/{MM-DD}/{会话标题}.log 文件中
"""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOG_DIR = Path("/app/logs/sessions")


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符"""
    if not filename:
        return "untitled"
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip()
    if len(filename) > 100:
        filename = filename[:100]
    return filename or "untitled"


def ensure_log_dir() -> None:
    """确保日志目录存在"""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"无法创建日志目录: {e}")


def get_daily_log_dir(log_time: datetime) -> Path:
    folder = log_time.strftime("%m-%d")
    return LOG_DIR / folder


def write_session_error_log(
        session_title: Optional[str],
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None
) -> Optional[Path]:
    """
    将会话错误写入日志文件

    Args:
        session_title: 会话标题，用于生成日志文件名
        error_type: 错误类型
        error_message: 错误信息
        stack_trace: 堆栈跟踪（可选）

    Returns:
        日志文件路径，如果写入失败返回 None
    """
    if not session_title:
        return None

    ensure_log_dir()
    timestamp_dt = datetime.now()
    daily_log_dir = get_daily_log_dir(timestamp_dt)
    daily_log_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(session_title)
    log_file = daily_log_dir / f"{safe_title}.log"

    try:
        timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
        log_content = f"\n{'='*60}\n"
        log_content += f"时间: {timestamp}\n"
        log_content += f"错误类型: {error_type}\n"
        log_content += f"错误信息: {error_message}\n"
        if stack_trace:
            log_content += f"\n堆栈跟踪:\n{stack_trace}\n"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_content)

        logger.info(f"错误日志已写入: {log_file}")
        return log_file
    except Exception as e:
        logger.warning(f"写入日志文件失败: {e}")
        return None
