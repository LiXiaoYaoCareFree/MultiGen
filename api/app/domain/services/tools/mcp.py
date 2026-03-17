import logging
import os
from contextlib import AsyncExitStack
from typing import Optional, Dict, List, Any

from mcp import ClientSession, Tool, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from app.application.errors.exceptions import NotFoundError
from app.domain.models.app_config import MCPConfig, MCPServerConfig, MCPTransport
from app.domain.models.tool_result import ToolResult
from .base import BaseTool

"""
MCP客户端管理器的开发思路:
1.在Agent执行的过程中，有可能需要调用多次工具,
  但是因为MCP工具的每次获取都需要调用客户端会话的list_tools()方法,
  非常耗时, 所以需要我们缓存工具的参数信息, 只有在初始化的时候才调用一次,
  并且在销毁MCP客户端管理器的时候一并清除;
2.在前端UI交互中, 无论MCP服务是否启动, 都会显示工具列表信息,
  但是在Agent执行的过程中, 我们只会传递已启动的MCP服务,
  所以对于MCP客户端管理器来说, 可以根据接收的MCP配置的差异加载不同的服务器,
  而不是仅从配置文件中读取数据;
3.MCP客户端管理器会同时管理多个MCP服务, 有可能有stdio、sse、streamable_http等传输协议.
  需要根据传输协议的不同来创建客户端会话(ClientSession), 同时缓存会话;
4.另外有可能有一些环境变量是存储在我们整个系统中的, 在初始化MCP服务的时候，需要将传递进来的
  环境变量与系统的环境变量进行合并后传递给MCP服务;
5.使用AsyncExitStack异步上下文管理器来管理上下文，避免使用with多层嵌套;
6.MCPClientManager的初始化非常耗时, 所以需要有机制可以判断避免重复初始化;
7.由于config.yaml是直接暴露在项目中的, 所以在使用config.yaml进行初始化的时候必须二次校验;
8.同时缓存ClientSession+Tool-Schema, 一个是客户端会话, 一个是工具参数声明;
9.MCP客户端管理器在清除/停止使用的时候, 必须关闭异步上下文管理器、清除资源(ClientSession、Tool-Schema)、
  初始化标识等, 从而避免资源泄露;
"""

logger = logging.getLogger(__name__)


class MCPClientManager:
    """MCP客户端管理器"""

    def __init__(self, mcp_config: Optional[MCPConfig] = None) -> None:
        """构造函数，完成MCP客户端管理器的初步初始化"""
        self._mcp_config: MCPConfig = mcp_config  # mcp配置信息
        self._exit_stack: AsyncExitStack = AsyncExitStack()  # 异步上下文管理器
        self._clients: Dict[str, ClientSession] = {}  # 缓存的客户端会话
        self._tools: Dict[str, List[Tool]] = {}  # 缓存的MCP工具参数声明
        self._initialized: bool = False  # 是否初始化标识

    @property
    def tools(self) -> Dict[str, List[Tool]]:
        """只读属性，返回缓存的MCP工具参数声明，键就是服务名字，值就是服务对应的工具声明"""
        return self._tools

    async def initialize(self) -> None:
        """初始化函数，用于连接所有配置的MCP服务器"""
        # 1.检查下是否已经初始化成功
        if self._initialized:
            return

        try:
            # 2.记录日志并连接MCP服务器
            logger.info(f"从config.yaml中加载了{len(self._mcp_config.mcpServers)}个MCP服务器")
            await self._connect_mcp_servers()
            self._initialized = True
            logger.info(f"MCP客户端管理器加载成功")
        except Exception as e:
            # 3.记录错误信息并直接抛出
            logger.error(f"MCP客户端管理器加载失败: {str(e)}")
            raise

    async def _connect_mcp_servers(self) -> None:
        """根据配置连接所有MCP服务"""
        # 1.循环遍历传递进来的所有MCP服务器，不用理会enabled的状态，因为在外部会执行筛选
        for server_name, server_config in self._mcp_config.mcpServers.items():
            try:
                # 2.根据服务名字+服务配置连接到MCP服务器
                await self._connect_mcp_server(server_name, server_config)
            except Exception as e:
                # 3.记录错误日志并跳过错误的MCP服务器
                logger.error(f"连接MCP服务器[{server_name}]出错: {str(e)}")
                continue

    async def _connect_mcp_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """根据传递的服务名字+服务配置连接到单个MCP服务"""
        try:
            # 1.获取mcp服务的传输协议
            transport = server_config.transport

            # 2.根据不同的传输协议调用不同的方法连接MCP服务器
            if transport == MCPTransport.STDIO:
                await self._connect_stdio_server(server_name, server_config)
            elif transport == MCPTransport.SSE:
                await self._connect_sse_server(server_name, server_config)
            elif transport == MCPTransport.STREAMABLE_HTTP:
                await self._connect_streamable_http_server(server_name, server_config)
            else:
                raise ValueError(f"MCP服务[{server_name}]使用了不支持的传输协议: {transport}")
        except Exception as e:
            # 3.记录日志并抛出异常
            logger.error(f"连接MCP服务器[{server_name}]出错: {str(e)}")
            raise

    async def _connect_stdio_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """根据服务名字+配置连接stdio服务"""
        # 1.从配置中提取相关命令信息
        command = server_config.command
        args = server_config.args
        env = server_config.env

        # 2.检查command是否存在
        if not command:
            raise ValueError("连接stdio-mcp服务器需要配置command命令")

        # 3.构建stdio连接参数
        server_parameters = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, **env},
        )

        try:
            # 4.使用异步上下文管理器创建传输协议
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_parameters),
            )
            read_stream, write_stream = stdio_transport

            # 5.根据读取与写入流构建会话
            session: ClientSession = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )

            # 6.初始化MCP服务会话
            await session.initialize()

            # 7.缓存对应的mcp连接客户端
            self._clients[server_name] = session

            # 8.缓存对应mcp服务的工具列表
            await self._cache_mcp_server_tools(server_name, session)
            logger.info(f"连接stdio-mcp服务器成功: {server_name}")
        except Exception as e:
            # 记录错误日志并直接抛出异常
            logger.error(f"连接stdio-mcp服务器失败: {str(e)}")
            raise

    async def _connect_sse_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """根据服务名字+配置连接sse服务"""
        # 1.提取sse服务器的连接url并判断是否存在
        url = server_config.url
        if not url:
            raise ValueError("连接sse-mcp服务器需要配置url")

        try:
            # 2.建立sse连接
            sse_transport = await self._exit_stack.enter_async_context(
                sse_client(url=url, headers=server_config.headers),
            )
            read_stream, write_stream = sse_transport

            # 3.创建客户端会话
            session: ClientSession = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )

            # 4.初始化MCP服务会话
            await session.initialize()

            # 5.缓存对应的mcp连接客户端
            self._clients[server_name] = session

            # 6.缓存对应mcp服务的工具列表
            await self._cache_mcp_server_tools(server_name, session)
            logger.info(f"连接sse-mcp服务器成功: {server_name}")
        except Exception as e:
            # 7.记录错误日志并直接抛出异常
            logger.error(f"连接sse-mcp服务器失败: {str(e)}")
            raise

    async def _connect_streamable_http_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """根据服务名字+配置连接streamable-http服务"""
        # 1.提取streamable-http服务器的连接url并判断是否存在
        url = server_config.url
        if not url:
            raise ValueError("连接sse-mcp服务器需要配置url")

        try:
            # 2.连接streamable-http服务
            streamable_http_transport = await self._exit_stack.enter_async_context(
                streamablehttp_client(url=url, headers=server_config.headers),
            )

            # 3.streamable-http模型需要解包获取输入与输出流
            if len(streamable_http_transport) == 3:
                read_stream, write_stream, _ = streamable_http_transport
            else:
                read_stream, write_stream = streamable_http_transport

            # 4.创建客户端会话
            session: ClientSession = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )

            # 5.初始化MCP服务会话
            await session.initialize()

            # 6.缓存对应的mcp连接客户端
            self._clients[server_name] = session

            # 7.缓存对应mcp服务的工具列表
            await self._cache_mcp_server_tools(server_name, session)
            logger.info(f"连接streamable-http-mcp服务器成功: {server_name}")
        except Exception as e:
            # 7.记录错误日志并直接抛出异常
            logger.error(f"连接streamable-http-mcp服务器失败: {str(e)}")
            raise

    async def _cache_mcp_server_tools(self, server_name: str, session: ClientSession) -> None:
        """根据传递的服务名字+会话缓存mcp服务工具列表"""
        try:
            tools_response = await session.list_tools()
            tools = tools_response.tools if tools_response else []
            self._tools[server_name] = tools
            logger.info(f"MCP服务器[{server_name}]提供了{len(tools)}个工具")
        except Exception as e:
            # 记录日志并将缓存设置为空
            logger.error(f"获取MCP服务器[{server_name}]工具列表失败: {str(e)}")
            self._tools[server_name] = []

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有MCP工具列表，返回LLM可以使用的工具参数声明列表并处理MCP的名字"""
        # 1.定义一个变量存储所有结果
        all_tools = []

        # 2.循环遍历所有缓存的工具
        for server_name, tools in self._tools.items():
            # 3.循环取出每个MCP服务的工具列表
            for tool in tools:
                # 4.修改工具名字加上mcp_前缀+服务名字
                if server_name.startswith("mcp_"):
                    tool_name = f"{server_name}_{tool.name}"
                else:
                    tool_name = f"mcp_{server_name}_{tool.name}"

                # 5.生成OpenAI工具描述
                tool_schema = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": f"[{server_name}] {tool.description or tool.name}",
                        "parameters": tool.inputSchema,
                    }
                }
                all_tools.append(tool_schema)

        return all_tools

    async def invoke(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """根据传递的工具名字+参数调用MCP工具"""
        try:
            # 1.定义变量存储原始的服务名字+工具
            original_server_name = None
            original_tool_name = None

            # 2.循环遍历当前的所有mcp服务配置
            for server_name in self._mcp_config.mcpServers.keys():
                # 3.为server_name组装前缀
                expected_prefix = server_name if server_name.startswith("mcp_") else f"mcp_{server_name}"

                # 4.判断工具名字是否以该服务名字为开头
                if tool_name.startswith(f"{expected_prefix}_"):
                    # 5.取出原始的服务名字+工具名字
                    original_server_name = server_name
                    original_tool_name = tool_name[len(expected_prefix) + 1:]
                    break

            # 6.判断服务名字+工具是否都存在
            if not original_server_name or not original_tool_name:
                raise NotFoundError(f"服务器解析MCP工具不存在: {tool_name}")

            # 7.获取该工具所属的会话
            session = self._clients.get(original_server_name)
            if not session:
                return ToolResult(success=False, message=f"MCP服务器[{original_server_name}]未连接")

            # 8.使用会话调用工具
            result = await session.call_tool(original_tool_name, arguments)

            # 9.判断结果是否存在执行不同的操作
            if result:
                # 10.处理MCP工具生成的content
                content = []
                if hasattr(result, "content") and result.content:
                    for item in result.content:
                        if hasattr(item, "text"):
                            content.append(item.text)
                        else:
                            content.append(str(item))

                # 11.返回工具结果
                return ToolResult(
                    success=True,
                    data="\n".join(content) if content else "工具执行成功"
                )
            else:
                return ToolResult(success=True, data="工具执行成功")
        except Exception as e:
            # 记录错误日志并返回失败的工具结果
            logger.error(f"调用MCP工具[{tool_name}]失败: {str(e)}")
            return ToolResult(
                success=False,
                message=f"调用MCP工具[{tool_name}]失败: {str(e)}",
            )

    async def cleanup(self) -> None:
        """当退出MCP服务时，清除对应资源

        该方法是幂等的，多次调用不会产生副作用。
        注意：必须在初始化MCP的同一个asyncio Task中调用此方法，
        否则anyio会因cancel scope上下文不匹配而抛出RuntimeError。
        """
        # 幂等检查：如果未初始化则跳过清理
        if not self._initialized:
            return

        try:
            await self._exit_stack.aclose()
            logger.info(f"清除MCP客户端管理器成功")
        except RuntimeError as e:
            # 防御性处理：anyio.create_task_group() 在不同任务中退出的已知问题
            if "Attempted to exit cancel scope in a different task" in str(e):
                logger.warning(f"清理MCP客户端管理器时遇到任务上下文切换警告（可忽略）: {str(e)}")
            else:
                logger.error(f"清理MCP客户端管理器失败: {str(e)}")
        except Exception as e:
            logger.error(f"清理MCP客户端管理器失败: {str(e)}")
        finally:
            # 无论aclose()是否成功，都必须清除缓存并重置状态
            self._clients.clear()
            self._tools.clear()
            self._initialized = False


class MCPTool(BaseTool):
    """MCP工具包，包含所有已配置+已启动的MCP工具"""
    name: str = "mcp"

    def __init__(self) -> None:
        """构造函数，完成MCP工具包的初始化"""
        super().__init__()
        self._initialized: bool = False
        self._tools = []
        self._manager: MCPClientManager = None

    async def initialize(self, mcp_config: Optional[MCPConfig] = None) -> None:
        """初始化MCP工具包"""
        # 1.判断是否初始化，如果未初始化则进行初始化
        if not self._initialized:
            # 2.初始化MCP客户端管理器
            self._manager = MCPClientManager(mcp_config=mcp_config)
            await self._manager.initialize()

            # 3.获取mcpServers工具列表
            self._tools = await self._manager.get_all_tools()
            self._initialized = True

    def get_tools(self) -> List[Dict[str, Any]]:
        """同步获取工具包下的所有工具列表"""
        return self._tools

    def has_tool(self, tool_name: str) -> bool:
        """传递工具名字判断工具是否存在"""
        # 1.循环遍历所有的工具
        for tool in self._tools:
            # 2.判断工具的名字是否存在，如果是则返回True，否则返回False
            if tool["function"]["name"] == tool_name:
                return True

        return False

    async def invoke(self, tool_name: str, **kwargs) -> ToolResult:
        """传递工具名字+参数调用MCP工具并获取结果"""
        return await self._manager.invoke(tool_name, kwargs)

    async def cleanup(self) -> None:
        """清除MCP工具资源"""
        if self._manager:
            await self._manager.cleanup()
