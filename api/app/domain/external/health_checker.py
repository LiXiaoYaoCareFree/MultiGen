from typing import Protocol

from app.domain.models.health_status import HealthStatus


class HealthChecker(Protocol):
    """服务健康检查协议"""

    async def check(self) -> HealthStatus:
        """用于检查对应的服务是否健康"""
        ...
