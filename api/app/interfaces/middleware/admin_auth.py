from typing import Optional

from fastapi import Header, Query

from app.application.errors.exceptions import UnauthorizedError
from core.config import get_settings

settings = get_settings()


def _validate_admin_api_key(admin_api_key: Optional[str]) -> None:
    if not settings.admin_auth_required:
        return
    if not settings.admin_api_key:
        raise UnauthorizedError("服务端未配置 ADMIN_API_KEY")
    if admin_api_key != settings.admin_api_key:
        raise UnauthorizedError("管理员鉴权失败")


def require_admin_auth(
        x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
        admin_api_key: Optional[str] = Query(default=None),
) -> None:
    _validate_admin_api_key(x_admin_api_key or admin_api_key)
