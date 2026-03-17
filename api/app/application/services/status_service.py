import asyncio
from typing import List

from app.domain.external.health_checker import HealthChecker
from app.domain.models.health_status import HealthStatus


class StatusService:
    """状态服务，用于检查系统的服务状态"""

    def __init__(self, checkers: List[HealthChecker]) -> None:
        """构造函数，传递所有检查器完成服务初始化"""
        self._checkers = checkers

    async def check_all(self) -> List[HealthStatus]:
        """调用所有检查器发起检查并返回对应的健康状态"""
        # 1.并行调用所有服务进行检查
        results = await asyncio.gather(
            *(checker.check() for checker in self._checkers),
            return_exceptions=True,  # 捕获异常而不是让gather失效
        )

        # 2.处理可能发生的异常
        processed_results = []
        for res in results:
            if isinstance(res, Exception):
                # 3.如果服务检查本身抛出异常则格式化为HealthStatus
                processed_results.append(HealthStatus(
                    service="未知服务",
                    status="error",
                    details=f"未知检查器发生错误: {str(res)}"
                ))
            else:
                processed_results.append(res)

        return processed_results
