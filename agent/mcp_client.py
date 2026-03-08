import asyncio
import json
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

# 注意：实际运行需要 mcp 包，但模块设计上要能在没有 mcp 包时也能 import（测试用 mock）
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@dataclass
class ServerConfig:
    """MCP Server 配置"""
    name: str
    command: str         # 启动命令，如 "python"
    args: list[str]      # 命令参数，如 ["mcp-servers/log-search/server.py"]
    env: dict = None     # 额外环境变量


class MCPClient:
    """多 MCP Server 连接管理器

    管理多个 MCP Server 的生命周期和工具调用。

    Usage:
        client = MCPClient(servers=[
            ServerConfig(name="log-search", command="python", args=["mcp-servers/log-search/server.py"]),
            ServerConfig(name="rule-engine", command="python", args=["mcp-servers/rule-engine/server.py"]),
        ])
        await client.connect_all()
        tools = client.list_tools()  # 返回所有 Server 的工具定义
        result = await client.call_tool("search_alerts", {"severity": "error"})
        await client.close()
    """

    def __init__(self, servers: list[ServerConfig] = None):
        self.servers = servers or []
        self._sessions: dict[str, Any] = {}      # name -> ClientSession
        self._tool_map: dict[str, str] = {}       # tool_name -> server_name
        self._tool_definitions: list[dict] = []   # Claude API 格式的工具定义
        self._exit_stack = AsyncExitStack()

    async def connect_all(self):
        """连接所有配置的 MCP Server"""
        for server in self.servers:
            await self._connect_server(server)
        self._build_tool_map()

    async def _connect_server(self, server: ServerConfig):
        """连接单个 MCP Server (stdio)"""
        if not HAS_MCP:
            raise RuntimeError("mcp package not installed")

        server_params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env={**os.environ, **(server.env or {})}
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        self._sessions[server.name] = session

    def _build_tool_map(self):
        """构建 tool_name -> server_name 映射，并生成 Claude API 格式的工具定义"""
        self._tool_map = {}
        self._tool_definitions = []

        for name, session in self._sessions.items():
            # 同步方式获取工具列表（实际需要在 connect 时缓存）
            pass

    async def refresh_tools(self):
        """刷新所有 Server 的工具列表"""
        self._tool_map = {}
        self._tool_definitions = []

        for name, session in self._sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                self._tool_map[tool.name] = name
                self._tool_definitions.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema
                })

    def list_tools(self) -> list[dict]:
        """返回所有 Server 的工具定义（Claude API 格式）

        Returns:
            [{"name": "search_alerts", "description": "...", "input_schema": {...}}, ...]
        """
        return self._tool_definitions

    def list_tools_for_claude(self) -> list[dict]:
        """返回 Claude messages.create() 的 tools 参数格式

        Returns:
            [{"type": "custom", "name": "...", "description": "...", "input_schema": {...}}, ...]
        """
        return [
            {
                "type": "custom",
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"]
            }
            for t in self._tool_definitions
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP 工具

        自动路由到对应的 MCP Server。

        Args:
            tool_name: 工具名
            arguments: 工具参数

        Returns:
            工具返回的字符串结果

        Raises:
            KeyError: 工具名不存在
            ConnectionError: MCP Server 不可用
        """
        server_name = self._tool_map.get(tool_name)
        if not server_name:
            raise KeyError(f"Unknown tool: {tool_name}")

        session = self._sessions.get(server_name)
        if not session:
            raise ConnectionError(f"Server {server_name} not connected")

        result = await session.call_tool(tool_name, arguments)

        # result.content 是 list[TextContent | ImageContent | ...]
        # 提取文本内容
        texts = []
        for content in result.content:
            if hasattr(content, 'text'):
                texts.append(content.text)
        return "\n".join(texts) if texts else ""

    async def close(self):
        """关闭所有连接"""
        await self._exit_stack.aclose()

    def get_connected_servers(self) -> list[str]:
        """返回已连接的 Server 名称列表"""
        return list(self._sessions.keys())


# 便捷函数：从配置文件创建 MCPClient
def create_client_from_config(config_path: str = "agent/mcp_servers.yaml") -> MCPClient:
    """从 YAML 配置文件创建 MCPClient

    配置格式:
    servers:
      - name: log-search
        command: python
        args: ["mcp-servers/log-search/server.py"]
        env:
          ICS_DB_PATH: "backend/data/ics-defense.db"
    """
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)

    servers = [
        ServerConfig(
            name=s["name"],
            command=s["command"],
            args=s["args"],
            env=s.get("env")
        )
        for s in config.get("servers", [])
    ]
    return MCPClient(servers=servers)
