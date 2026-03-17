import logging
from typing import Any

from fastapi import status

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用基础异常"""

    def __init__(
            self,
            msg: str = "应用发生错误请稍后尝试",
            status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
            data: Any = None
    ) -> None:
        """构造函数，完成异常的初始化"""
        # 1.完成数据初始化
        self.msg = msg
        self.status_code = status_code
        self.data = data

        # 2.记录日志并调用父类构造函数
        logger.error(f"沙箱发生错误: {msg} (code: {status_code})")
        super().__init__(self.msg)


class NotFoundException(AppException):
    """资源未找到异常"""

    def __init__(self, msg: str = "资源未找到，请核实后尝试") -> None:
        super().__init__(msg=msg, status_code=status.HTTP_404_NOT_FOUND)


class BadRequestException(AppException):
    """错误请求异常"""

    def __init__(self, msg: str = "客户端请求错误，请检查后重试") -> None:
        super().__init__(msg=msg, status_code=status.HTTP_400_BAD_REQUEST)
