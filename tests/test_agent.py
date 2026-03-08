"""
Agent 主循环集成测试

测试:
1. 完整 agent_loop（规划 + 执行 + 结论）
2. 审批流程
3. Guard 异常处理
4. parse_decision 解析
5. Hook 生命周期触发
"""

import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

import pytest

from agent.agent import (
    agent_loop,
    parse_decision,
    _default_decision,
    wait_for_approval,
    _insert_approval_request,
    _ensure_approval_table,
    _convert_tools_to_openai,
)
from agent.guard import MaxStepsExceeded, AgentStuck


# ---------------------------------------------------------------------------
# 辅助: 构造 OpenAI API 响应 Mock
# ---------------------------------------------------------------------------

def _make_tool_call(tool_id: str, name: str, arguments: dict):
    """创建 OpenAI 格式的 tool_call"""
    tc = MagicMock()
    tc.id = tool_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments, ensure_ascii=False)
    return tc


def _make_response(content: str = None, tool_calls=None,
                    finish_reason="stop", prompt_tokens=100, completion_tokens=50):
    """创建完整的 OpenAI API 响应"""
    response = MagicMock()
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason
    response.choices = [choice]
    response.usage = MagicMock()
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_alerts():
    """测试用聚簇告警"""
    return [
        {
            "signature": "SQL注入攻击",
            "sample": {
                "source": "waf",
                "title": "SQL注入攻击",
                "description": "检测到SQL注入攻击尝试",
                "severity": "high",
                "src_ip": "10.0.0.5",
                "dst_ip": "192.168.1.100",
            },
            "count": 150,
            "severity": "high",
            "first_seen": "2026-03-08T10:00:00Z",
            "last_seen": "2026-03-08T10:35:00Z",
            "source_ips": ["10.0.0.5"],
            "target_ips": ["192.168.1.100"],
        }
    ]


@pytest.fixture
def mock_mcp():
    """模拟 MCP Client"""
    client = MagicMock()
    client.list_tools_for_claude.return_value = [
        {
            "type": "custom",
            "name": "search_alerts",
            "description": "查询告警",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "type": "custom",
            "name": "recall",
            "description": "检索记忆",
            "input_schema": {"type": "object", "properties": {}},
        },
    ]
    client.call_tool = AsyncMock(return_value='{"results": [{"id": 1, "title": "SQL注入"}]}')
    client.close = AsyncMock()
    client.get_connected_servers.return_value = ["log-search"]
    return client


@pytest.fixture
def db_path(tmp_path):
    """测试数据库路径"""
    path = str(tmp_path / "test_agent.db")
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS approval_queue (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id     TEXT NOT NULL,
            tool_name    TEXT NOT NULL,
            tool_args    TEXT,
            reason       TEXT,
            status       TEXT DEFAULT 'pending',
            responded_at TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id    TEXT NOT NULL,
            alert_id    TEXT,
            event_type  TEXT NOT NULL,
            data        TEXT,
            token_usage TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_logs(trace_id);
    """)
    conn.close()
    return path


# ---------------------------------------------------------------------------
# 测试 1: 完整 agent_loop 流程（规划 + 执行 + 结论）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_agent_loop(sample_alerts, mock_mcp, db_path):
    """测试完整的 agent_loop 流程：规划 → 工具调用 → 最终决策"""

    # 规划阶段响应: 返回 JSON 格式的分析计划
    plan_json = json.dumps({
        "goal": "分析 SQL 注入攻击",
        "steps": [
            {"id": 1, "action": "查询相关告警", "tool": "search_alerts"},
            {"id": 2, "action": "综合研判", "tool": None},
        ],
        "estimated_risk": "high",
    }, ensure_ascii=False)
    planning_response = _make_response(content=plan_json)

    # 执行阶段响应 1: 调用工具
    exec_response_1 = _make_response(
        content="正在查询高危告警...",
        tool_calls=[_make_tool_call("call_1", "search_alerts", {"severity": "high"})],
        finish_reason="tool_calls",
    )

    # 执行阶段响应 2: 返回最终决策
    final_decision = json.dumps({
        "risk_level": "high",
        "confidence": 0.85,
        "attack_chain": [
            {"stage": "初始访问", "technique": "T0866", "evidence": "SQL注入攻击"}
        ],
        "recommendation": "建议立即阻断 10.0.0.5",
        "action_type": "block",
        "rationale": "检测到持续的 SQL 注入攻击，源 IP 10.0.0.5 对 HMI 服务器发起攻击。",
    }, ensure_ascii=False)
    exec_response_2 = _make_response(content=final_decision)

    # Mock OpenAI client
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = [
        planning_response,     # 规划阶段
        exec_response_1,       # 执行阶段第一轮（工具调用）
        exec_response_2,       # 执行阶段第二轮（最终决策）
    ]

    with patch("agent.agent.OpenAI", return_value=mock_client_instance), \
         patch("agent.agent.ToolPolicy") as MockPolicy, \
         patch("agent.agent.HookManager") as MockHooks:

        mock_policy = MagicMock()
        mock_policy.get_level.return_value = "auto"
        mock_policy.approval_timeout = 300
        MockPolicy.return_value = mock_policy

        mock_hooks = AsyncMock()
        MockHooks.return_value = mock_hooks

        result = await agent_loop(
            sample_alerts,
            mcp_client=mock_mcp,
            model="grok-3-mini-fast",
            db_path=db_path,
        )

    # 验证返回结果
    assert result is not None
    assert result["risk_level"] == "high"
    assert result["confidence"] == 0.85
    assert result["action_type"] == "block"
    assert "trace_id" in result
    assert "token_usage" in result

    # 验证 LLM 被调用了 3 次（规划 + 执行两轮）
    assert mock_client_instance.chat.completions.create.call_count == 3

    # 验证 MCP 工具被调用
    mock_mcp.call_tool.assert_called()


# ---------------------------------------------------------------------------
# 测试 2: 审批流程
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_flow(sample_alerts, mock_mcp, db_path):
    """测试 approve 级别工具的审批流程"""

    plan_json = json.dumps({
        "goal": "分析并阻断攻击",
        "steps": [
            {"id": 1, "action": "阻断 IP", "tool": "block_ip"},
        ],
        "estimated_risk": "critical",
    }, ensure_ascii=False)
    planning_response = _make_response(content=plan_json)

    # 执行阶段: 调用需要审批的工具
    exec_response_1 = _make_response(
        content=None,
        tool_calls=[_make_tool_call("call_block", "block_ip", {"ip": "10.0.0.5"})],
        finish_reason="tool_calls",
    )

    # 审批被拒绝后的最终响应
    final_decision = json.dumps({
        "risk_level": "high",
        "confidence": 0.7,
        "attack_chain": [],
        "recommendation": "阻断操作被拒绝，建议人工审查",
        "action_type": "manual_review",
        "rationale": "自动阻断被运维人员拒绝",
    }, ensure_ascii=False)
    exec_response_2 = _make_response(content=final_decision)

    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = [
        planning_response,
        exec_response_1,
        exec_response_2,
    ]

    async def _mock_wait_approval(db_path, approval_id, timeout=300, poll_interval=2.0):
        return "rejected"

    with patch("agent.agent.OpenAI", return_value=mock_client_instance), \
         patch("agent.agent.ToolPolicy") as MockPolicy, \
         patch("agent.agent.HookManager") as MockHooks, \
         patch("agent.agent.wait_for_approval", side_effect=_mock_wait_approval):

        mock_policy = MagicMock()
        mock_policy.get_level.return_value = "approve"
        mock_policy.approval_timeout = 10
        MockPolicy.return_value = mock_policy

        mock_hooks = AsyncMock()
        MockHooks.return_value = mock_hooks

        result = await agent_loop(
            sample_alerts,
            mcp_client=mock_mcp,
            model="grok-3-mini-fast",
            db_path=db_path,
        )

    # 审批被拒绝，MCP 工具不应被调用
    mock_mcp.call_tool.assert_not_called()

    # 验证 on_approval_needed 钩子被触发
    hook_event_names = [
        c.args[0] for c in mock_hooks.trigger.call_args_list
    ]
    assert "on_approval_needed" in hook_event_names


# ---------------------------------------------------------------------------
# 测试 3: Guard 异常处理（max_steps 超限）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guard_max_steps_exceeded(sample_alerts, mock_mcp, db_path):
    """测试超过最大步数时的降级处理"""

    plan_json = json.dumps({
        "goal": "分析告警",
        "steps": [{"id": 1, "action": "查询", "tool": "search_alerts"}],
        "estimated_risk": "medium",
    }, ensure_ascii=False)
    planning_response = _make_response(content=plan_json)

    # 每次执行都返回工具调用（导致无限循环）
    tool_response = _make_response(
        content=None,
        tool_calls=[_make_tool_call("call_loop", "search_alerts", {"page": 1})],
        finish_reason="tool_calls",
    )

    final_response = _make_response(content='{"risk_level": "unknown"}')

    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = [
        planning_response,
    ] + [tool_response] * 5 + [final_response]

    with patch("agent.agent.OpenAI", return_value=mock_client_instance), \
         patch("agent.agent.ToolPolicy") as MockPolicy, \
         patch("agent.agent.HookManager") as MockHooks:

        mock_policy = MagicMock()
        mock_policy.get_level.return_value = "auto"
        mock_policy.approval_timeout = 300
        MockPolicy.return_value = mock_policy

        mock_hooks = AsyncMock()
        MockHooks.return_value = mock_hooks

        result = await agent_loop(
            sample_alerts,
            mcp_client=mock_mcp,
            model="grok-3-mini-fast",
            db_path=db_path,
            guard_config={
                "max_steps": 3,
                "total_timeout": 60,
                "max_retries": 0,
                "step_timeout": 10,
                "stuck_threshold": 10,
            },
        )

    assert result is not None
    assert "trace_id" in result

    hook_event_names = [
        c.args[0] for c in mock_hooks.trigger.call_args_list
    ]
    assert "on_loop_finished" in hook_event_names


# ---------------------------------------------------------------------------
# 测试 4: parse_decision 解析
# ---------------------------------------------------------------------------

class TestParseDecision:
    """测试决策解析函数"""

    def test_parse_json_string(self):
        """从纯 JSON 字符串解析"""
        decision_json = json.dumps({
            "risk_level": "critical",
            "confidence": 0.95,
            "attack_chain": [],
            "recommendation": "立即隔离",
            "action_type": "isolate",
            "rationale": "多阶段攻击",
        })
        result = parse_decision(decision_json)
        assert result["risk_level"] == "critical"
        assert result["confidence"] == 0.95

    def test_parse_json_from_code_block(self):
        """从 Markdown code block 中解析 JSON"""
        text = """分析完成，以下是结论：

```json
{
    "risk_level": "high",
    "confidence": 0.8,
    "attack_chain": [],
    "recommendation": "阻断 IP",
    "action_type": "block",
    "rationale": "持续攻击"
}
```
"""
        result = parse_decision(text)
        assert result["risk_level"] == "high"

    def test_parse_json_mixed_text(self):
        """从混合文本中提取 JSON"""
        text = '根据分析，我的结论是：{"risk_level": "medium", "confidence": 0.6, "recommendation": "监控"}'
        result = parse_decision(text)
        assert result["risk_level"] == "medium"

    def test_parse_empty_response(self):
        """空响应返回默认决策"""
        result = parse_decision("")
        assert result["risk_level"] == "unknown"
        assert result["action_type"] == "manual_review"

    def test_parse_no_json(self):
        """无 JSON 内容返回默认决策"""
        result = parse_decision("这是一段没有 JSON 的分析文本。")
        assert result["risk_level"] == "unknown"

    def test_parse_dict_blocks(self):
        """支持 list of dict 格式的 content blocks（兼容旧格式）"""
        blocks = [{"type": "text", "text": '{"risk_level": "low", "confidence": 0.3}'}]
        result = parse_decision(blocks)
        assert result["risk_level"] == "low"


# ---------------------------------------------------------------------------
# 测试 5: Hook 生命周期触发
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hook_lifecycle(sample_alerts, mock_mcp, db_path):
    """测试 Hook 在各生命周期节点正确触发"""

    plan_json = json.dumps({
        "goal": "分析告警",
        "steps": [{"id": 1, "action": "综合研判", "tool": None}],
        "estimated_risk": "low",
    }, ensure_ascii=False)
    planning_response = _make_response(content=plan_json)

    final_decision = json.dumps({
        "risk_level": "low",
        "confidence": 0.9,
        "attack_chain": [],
        "recommendation": "无需处置",
        "action_type": "monitor",
        "rationale": "低风险告警",
    }, ensure_ascii=False)
    exec_response = _make_response(content=final_decision)

    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = [
        planning_response,
        exec_response,
    ]

    with patch("agent.agent.OpenAI", return_value=mock_client_instance), \
         patch("agent.agent.ToolPolicy") as MockPolicy, \
         patch("agent.agent.HookManager") as MockHooks:

        mock_policy = MagicMock()
        mock_policy.get_level.return_value = "auto"
        MockPolicy.return_value = mock_policy

        mock_hooks = AsyncMock()
        MockHooks.return_value = mock_hooks

        result = await agent_loop(
            sample_alerts,
            mcp_client=mock_mcp,
            model="grok-3-mini-fast",
            db_path=db_path,
        )

    hook_events = [c.args[0] for c in mock_hooks.trigger.call_args_list]

    assert "on_alert_received" in hook_events
    assert "on_plan_generated" in hook_events
    assert "on_decision_made" in hook_events
    assert "on_loop_finished" in hook_events

    idx_alert = hook_events.index("on_alert_received")
    idx_plan = hook_events.index("on_plan_generated")
    idx_decision = hook_events.index("on_decision_made")
    idx_finished = hook_events.index("on_loop_finished")

    assert idx_alert < idx_plan
    assert idx_plan < idx_decision
    assert idx_decision < idx_finished


# ---------------------------------------------------------------------------
# 测试: 审批队列操作
# ---------------------------------------------------------------------------

class TestApprovalQueue:
    """测试审批队列相关功能"""

    def test_insert_and_check_approval(self, db_path):
        approval_id = _insert_approval_request(
            db_path, "trace-123", "block_ip", {"ip": "10.0.0.5"}, "需要审批"
        )
        assert approval_id > 0

        from agent.agent import _check_approval_status
        status = _check_approval_status(db_path, approval_id)
        assert status is None

        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE approval_queue SET status = 'approved' WHERE id = ?",
            (approval_id,),
        )
        conn.commit()
        conn.close()

        status = _check_approval_status(db_path, approval_id)
        assert status == "approved"

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, db_path):
        approval_id = _insert_approval_request(
            db_path, "trace-456", "isolate_host", {"host": "pc-01"}, ""
        )
        result = await wait_for_approval(
            db_path, approval_id, timeout=0.1, poll_interval=0.05
        )
        assert result == "timeout"

    @pytest.mark.asyncio
    async def test_wait_for_approval_approved(self, db_path):
        approval_id = _insert_approval_request(
            db_path, "trace-789", "block_ip", {"ip": "10.0.0.1"}, ""
        )

        async def _approve_later():
            await asyncio.sleep(0.1)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE approval_queue SET status = 'approved' WHERE id = ?",
                (approval_id,),
            )
            conn.commit()
            conn.close()

        task = asyncio.create_task(_approve_later())
        result = await wait_for_approval(
            db_path, approval_id, timeout=5, poll_interval=0.05
        )
        assert result == "approved"
        await task


# ---------------------------------------------------------------------------
# 测试: 工具格式转换
# ---------------------------------------------------------------------------

def test_convert_tools_to_openai():
    """测试 Claude 工具格式转 OpenAI 格式"""
    claude_tools = [
        {
            "type": "custom",
            "name": "search_alerts",
            "description": "查询告警",
            "input_schema": {"type": "object", "properties": {"severity": {"type": "string"}}},
        }
    ]
    openai_tools = _convert_tools_to_openai(claude_tools)
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "search_alerts"
    assert openai_tools[0]["function"]["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# 测试: 默认决策
# ---------------------------------------------------------------------------

def test_default_decision():
    result = _default_decision("测试原因")
    assert result["risk_level"] == "unknown"
    assert result["action_type"] == "manual_review"
    assert "测试原因" in result["rationale"]
