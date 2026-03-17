from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """健康检查状态"""
    service: str = Field(default="", description="健康检查对应的服务名字")
    status: str = Field(default="", description="健康检查状态，支持ok表示正常, error表示出错")
    details: str = Field(default="", description="出错时的详情提示")
