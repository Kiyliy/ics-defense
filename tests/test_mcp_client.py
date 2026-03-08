"""Tests for agent/mcp_client.py

由于 MCP client 需要实际 Server 进程，这里主要测试 mock 场景。
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from agent.mcp_client import MCPClient, ServerConfig, create_client_from_config


class TestServerConfig:
    def test_server_config_dataclass(self):
        """ServerConfig 字段正确"""
        cfg = ServerConfig(
            name="log-search",
            command="python",
            args=["mcp-servers/log-search/server.py"],
            env={"ICS_DB_PATH": "test.db"}
        )
        assert cfg.name == "log-search"
        assert cfg.command == "python"
        assert cfg.args == ["mcp-servers/log-search/server.py"]
        assert cfg.env == {"ICS_DB_PATH": "test.db"}

    def test_server_config_default_env(self):
        """ServerConfig env 默认为 None"""
        cfg = ServerConfig(name="test", command="python", args=[])
        assert cfg.env is None


class TestMCPClient:
    def test_list_tools_empty(self):
        """未连接时返回空列表"""
        client = MCPClient()
        assert client.list_tools() == []

    def test_list_tools_for_claude_format(self):
        """返回格式包含 type, name, description, input_schema"""
        client = MCPClient()
        client._tool_definitions = [
            {"name": "search_alerts", "description": "查询告警", "input_schema": {"type": "object", "properties": {}}},
        ]
        result = client.list_tools_for_claude()
        assert len(result) == 1
        tool = result[0]
        assert tool["type"] == "custom"
        assert tool["name"] == "search_alerts"
        assert tool["description"] == "查询告警"
        assert "input_schema" in tool

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self):
        """调用未知工具 raises KeyError"""
        client = MCPClient()
        with pytest.raises(KeyError, match="Unknown tool"):
            await client.call_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Server 未连接 raises ConnectionError"""
        client = MCPClient()
        # 手动设置 tool_map 指向一个不存在的 session
        client._tool_map["some_tool"] = "missing-server"
        with pytest.raises(ConnectionError, match="not connected"):
            await client.call_tool("some_tool", {})

    def test_get_connected_servers(self):
        """返回已连接的 server 名称"""
        client = MCPClient()
        assert client.get_connected_servers() == []

        # 模拟已连接的 sessions
        client._sessions = {"log-search": MagicMock(), "rule-engine": MagicMock()}
        servers = client.get_connected_servers()
        assert set(servers) == {"log-search", "rule-engine"}

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """成功调用工具返回文本结果"""
        client = MCPClient()
        mock_session = AsyncMock()
        text_content = MagicMock()
        text_content.text = '{"results": [1, 2, 3]}'
        mock_result = MagicMock()
        mock_result.content = [text_content]
        mock_session.call_tool.return_value = mock_result

        client._sessions = {"log-search": mock_session}
        client._tool_map = {"search_alerts": "log-search"}

        result = await client.call_tool("search_alerts", {"severity": "high"})
        assert result == '{"results": [1, 2, 3]}'
        mock_session.call_tool.assert_called_once_with("search_alerts", {"severity": "high"})

    @pytest.mark.asyncio
    async def test_refresh_tools(self):
        """refresh_tools 从 session 获取工具列表并构建映射"""
        client = MCPClient()
        mock_tool = MagicMock()
        mock_tool.name = "search_alerts"
        mock_tool.description = "查询告警"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        mock_response = MagicMock()
        mock_response.tools = [mock_tool]

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_response
        client._sessions = {"log-search": mock_session}

        await client.refresh_tools()
        assert "search_alerts" in client._tool_map
        assert client._tool_map["search_alerts"] == "log-search"
        assert len(client._tool_definitions) == 1
        assert client._tool_definitions[0]["name"] == "search_alerts"

    @pytest.mark.asyncio
    async def test_close(self):
        """close 调用 exit_stack.aclose"""
        client = MCPClient()
        client._exit_stack = AsyncMock()
        await client.close()
        client._exit_stack.aclose.assert_called_once()


class TestCreateClientFromConfig:
    def test_create_client_from_config(self, tmp_path):
        """从 yaml 创建 client，servers 列表正确"""
        config_content = """
servers:
  - name: log-search
    command: python
    args: ["mcp-servers/log-search/server.py"]
    env:
      ICS_DB_PATH: "test.db"
  - name: rule-engine
    command: python
    args: ["mcp-servers/rule-engine/server.py"]
"""
        config_file = tmp_path / "mcp_servers.yaml"
        config_file.write_text(config_content)

        client = create_client_from_config(str(config_file))
        assert len(client.servers) == 2
        assert client.servers[0].name == "log-search"
        assert client.servers[0].command == "python"
        assert client.servers[0].args == ["mcp-servers/log-search/server.py"]
        assert client.servers[0].env == {"ICS_DB_PATH": "test.db"}
        assert client.servers[1].name == "rule-engine"
        assert client.servers[1].env is None
