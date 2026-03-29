import logging
import json
import random
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, Body

from app.application.services.app_config_service import AppConfigService
from app.domain.models.app_config import LLMConfig, AgentConfig, MCPConfig
from app.domain.services.tools.mcp import MCPClientManager
from app.infrastructure.external.llm.openai_llm import OpenAILLM
from app.infrastructure.repositories.file_app_config_repository import FileAppConfigRepository
from app.interfaces.middleware.admin_auth import require_admin_auth
from app.interfaces.schemas.app_config import ListMCPServerResponse, ListA2AServerResponse, SuggestedQuestionsResponse
from app.interfaces.schemas.base import Response
from app.interfaces.service_dependencies import get_app_config_service
from core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/app-config", tags=["设置模块"], dependencies=[Depends(require_admin_auth)])
settings = get_settings()


def _fallback_suggested_questions(count: int) -> List[str]:
    date_label = datetime.now().strftime("%Y-%m-%d")
    templates = [
        f"截至 {date_label}，请围绕{{topic}}写一份深度研判：背景演化、核心矛盾、利益相关方、未来 6 个月情景推演。",
        f"基于{{topic}}，做一份政策、产业、资本市场三层联动分析，并给出可执行跟踪清单。",
        f"请对{{topic}}进行正反双方论证：各列 5 条最强论据，最后给出中立裁决与依据。",
        f"围绕{{topic}}输出结构化简报：关键数据、时间线、风险矩阵、结论建议。",
        f"从全球竞争视角分析{{topic}}：中国、美国、欧盟策略差异与潜在连锁反应。",
    ]
    topics = [
        "AI 智能体与多模态应用落地",
        "地缘冲突对大宗商品与航运价格影响",
        "全球利率周期与人民币资产定价",
        "新能源车价格战与产业链利润再分配",
        "低空经济与无人机商业化",
        "网络安全与数据合规治理",
        "开源大模型与闭源模型竞争",
        "平台经济监管与中小商家生态",
    ]
    random.shuffle(topics)
    random.shuffle(templates)
    out: List[str] = []
    for idx in range(min(max(count, 1), 4)):
        out.append(templates[idx % len(templates)].replace("{topic}", topics[idx % len(topics)]))
    return out


def _sanitize_question(text: str) -> str:
    cleaned = (text or "").strip().replace("「", "").replace("」", "")
    return " ".join(cleaned.split())


def _extract_questions_from_content(content: str, count: int) -> List[str]:
    if not content:
        return []
    questions: List[str] = []
    try:
        data = json.loads(content)
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            for item in data["questions"]:
                if isinstance(item, str) and item.strip():
                    questions.append(item.strip())
    except Exception:
        pass
    return [_sanitize_question(q) for q in questions[:count]]


async def _generate_suggested_questions_with_llm(count: int) -> List[str]:
    app_config = FileAppConfigRepository(config_path=settings.app_config_filepath).load()
    llm = OpenAILLM(app_config.llm_config)
    enabled_servers = {
        name: conf for name, conf in app_config.mcp_config.mcpServers.items() if getattr(conf, "enabled", True)
    }
    mcp_manager = MCPClientManager(MCPConfig(mcpServers=enabled_servers))
    tools = []
    try:
        await mcp_manager.initialize()
        tools = await mcp_manager.get_all_tools()
        system_prompt = (
            "你是时事编辑。请生成高质量、复杂、贴近时事的中文问题。"
            "如果有工具可用，优先至少调用一次MCP工具获取最新信息。"
            "最终必须只输出JSON对象，格式：{\"questions\":[\"...\", \"...\", \"...\", \"...\"]}。"
            "questions长度必须为4，每条都应可直接作为深度任务输入。"
            "每条必须是一整句自然语言问题，不要使用「」这类括号包裹主题。"
        )
        user_prompt = (
            f"请生成{count}个热点问题，要求：复杂、紧贴时事、可执行研究，语句自然完整。"
            "不要解释，不要markdown，只返回JSON。"
        )
        messages: List[Dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        message = await llm.invoke(
            messages=messages,
            tools=tools if tools else None,
            response_format={"type": "json_object"},
            tool_choice="auto" if tools else None,
        )
        for _ in range(2):
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                break
            messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            })
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                arguments = function.get("arguments", "{}")
                try:
                    parsed_args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
                except Exception:
                    parsed_args = {}
                result = await mcp_manager.invoke(tool_name, parsed_args)
                tool_result_content = json.dumps(
                    result.data if result and result.data is not None else {
                        "success": bool(result.success) if result else False,
                        "message": getattr(result, "message", ""),
                    },
                    ensure_ascii=False,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": tool_name,
                    "content": tool_result_content,
                })
            message = await llm.invoke(
                messages=messages,
                tools=tools if tools else None,
                response_format={"type": "json_object"},
                tool_choice="auto" if tools else None,
            )
        questions = _extract_questions_from_content(message.get("content", "") or "", count)
        if len(questions) >= count:
            return questions[:count]
        merged = questions + _fallback_suggested_questions(count - len(questions))
        return [_sanitize_question(q) for q in merged[:count]]
    finally:
        await mcp_manager.cleanup()


@router.get(
    path="/llm",
    response_model=Response[LLMConfig],
    summary="获取LLM配置信息",
    description="包含LLM提供商的base_url、temperature、model_name、max_tokens"
)
async def get_llm_config(
        app_config_service: AppConfigService = Depends(get_app_config_service)
) -> Response[LLMConfig]:
    """获取LLM配置信息"""
    llm_config = await app_config_service.get_llm_config()
    return Response.success(data=llm_config.model_dump(exclude={"api_key"}))


@router.post(
    path="/llm",
    response_model=Response[LLMConfig],
    summary="更新LLM配置信息",
    description="更新LLM配置信息，当api_key为空的时候表示不更新该字段"
)
async def update_llm_config(
        new_llm_config: LLMConfig,
        app_config_service: AppConfigService = Depends(get_app_config_service)
) -> Response[LLMConfig]:
    """更新LLM配置信息"""
    updated_llm_config = await app_config_service.update_llm_config(new_llm_config)
    return Response.success(
        msg="更新LLM信息配置成功",
        data=updated_llm_config.model_dump(exclude={"api_key"})
    )


@router.get(
    path="/agent",
    response_model=Response[AgentConfig],
    summary="获取Agent通用配置信息",
    description="包含最大迭代次数、最大重试次数、最大搜索结果数"
)
async def get_agent_config(
        app_config_service: AppConfigService = Depends(get_app_config_service)
) -> Response[AgentConfig]:
    """获取Agent通用配置信息"""
    agent_config = await app_config_service.get_agent_config()
    return Response.success(data=agent_config.model_dump())


@router.post(
    path="/agent",
    response_model=Response[AgentConfig],
    summary="更新Agent通用配置信息",
    description="更新Agent通用配置信息"
)
async def update_llm_config(
        new_agent_config: AgentConfig,
        app_config_service: AppConfigService = Depends(get_app_config_service)
) -> Response[AgentConfig]:
    """更新Agent配置信息"""
    updated_agent_config = await app_config_service.update_agent_config(new_agent_config)
    return Response.success(
        msg="更新Agent信息配置成功",
        data=updated_agent_config.model_dump()
    )


@router.get(
    path="/mcp-servers",
    response_model=Response[ListMCPServerResponse],
    summary="获取MCP服务器工具列表",
    description="获取当前系统的MCP服务器列表，包含MCP服务名字、工具列表、启用状态等",
)
async def get_mcp_servers(
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[ListMCPServerResponse]:
    """获取当前系统的MCP服务器工具列表"""
    mcp_servers = await app_config_service.get_mcp_servers()
    return Response.success(
        msg="获取mcp服务器列表成功",
        data=ListMCPServerResponse(mcp_servers=mcp_servers)
    )


@router.post(
    path="/mcp-servers",
    response_model=Response[Optional[Dict]],
    summary="新增MCP服务配置，支持传递一个或者多个配置",
    description="传递MCP配置信息为系统新增MCP工具",
)
async def create_mcp_servers(
        mcp_config: MCPConfig,
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """根据传递的配置信息创建mcp服务"""
    await app_config_service.update_and_create_mcp_servers(mcp_config)
    return Response.success(msg="新增MCP服务配置成功")


@router.post(
    path="/mcp-servers/{server_name}/delete",
    response_model=Response[Optional[Dict]],
    summary="删除MCP服务配置",
    description="根据传递的MCP服务名字删除指定的MCP服务",
)
async def delete_mcp_server(
        server_name: str,
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """根据服务名字删除MCP服务器"""
    await app_config_service.delete_mcp_server(server_name)
    return Response.success(msg="删除MCP服务配置成功")


@router.post(
    path="/mcp-servers/{server_name}/enabled",
    response_model=Response[Optional[Dict]],
    summary="更新MCP服务的启用状态",
    description="根据传递的server_name+enabled更新指定MCP服务的启用状态",
)
async def set_mcp_server_enabled(
        server_name: str,
        enabled: bool = Body(..., embed=True),
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """根据传递的server_name+enabled更新服务的启用状态"""
    await app_config_service.set_mcp_server_enabled(server_name, enabled)
    return Response.success(msg="更新MCP服务启用状态成功")


@router.get(
    path="/a2a-servers",
    response_model=Response[ListA2AServerResponse],
    summary="获取a2a服务器列表",
    description="获取MultiGen项目中的所有已配置的a2a服务列表",
)
async def get_a2a_servers(
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[ListA2AServerResponse]:
    """获取a2a服务列表"""
    a2a_servers = await app_config_service.get_a2a_servers()
    return Response.success(
        msg="获取a2a服务列表成功",
        data=ListA2AServerResponse(a2a_servers=a2a_servers)
    )


@router.post(
    path="/a2a-servers",
    response_model=Response[Optional[Dict]],
    summary="新增a2a服务器",
    description="为MultiGen项目新增a2a服务器",
)
async def create_a2a_server(
        base_url: str = Body(..., embed=True),
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """新增a2a服务器"""
    await app_config_service.create_a2a_server(base_url)
    return Response.success(msg="新增A2A服务配置成功")


@router.post(
    path="/a2a-servers/{a2a_id}/delete",
    response_model=Response[Optional[Dict]],
    summary="删除a2a服务器",
    description="根据A2A服务id标识删除指定的A2A服务"
)
async def delete_a2a_server(
        a2a_id: str,
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """删除a2a服务器"""
    await app_config_service.delete_a2a_server(a2a_id)
    return Response.success(msg="删除a2a服务器成功")


@router.post(
    path="/a2a-servers/{a2a_id}/enabled",
    response_model=Response[Optional[Dict]],
    summary="更新A2A服务的启用状态",
    description="启动or禁用A2A服务的状态",
)
async def set_a2a_server_enabled(
        a2a_id: str,
        enabled: bool = Body(..., embed=True),
        app_config_service: AppConfigService = Depends(get_app_config_service),
) -> Response[Optional[Dict]]:
    """更新A2A服务的启用状态"""
    await app_config_service.set_a2a_server_enabled(a2a_id, enabled)
    return Response.success(msg="更新a2a服务器启用状态成功")


@router.get(
    path="/suggested-questions",
    response_model=Response[SuggestedQuestionsResponse],
    summary="生成首页热点问题",
    description="每次请求都会调用LLM并尽量结合MCP工具生成4个复杂且贴近时事的问题",
)
async def get_suggested_questions(
        count: int = 4,
) -> Response[SuggestedQuestionsResponse]:
    try:
        target = max(1, min(count, 4))
        questions = await _generate_suggested_questions_with_llm(target)
        return Response.success(
            msg="获取热点问题成功",
            data=SuggestedQuestionsResponse(questions=[_sanitize_question(q) for q in questions[:target]]),
        )
    except Exception as e:
        logger.exception(f"生成热点问题失败: {e}")
        fallback = _fallback_suggested_questions(max(1, min(count, 4)))
        return Response.success(
            msg="获取热点问题成功",
            data=SuggestedQuestionsResponse(questions=[_sanitize_question(q) for q in fallback]),
        )
