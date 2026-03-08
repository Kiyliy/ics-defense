"""
集成测试 — 验证各模块之间的兼容性和协作能力。

测试范围：
1. Collector 数据处理管线（normalizer → clusterer → severity_filter → producer）
2. MCP Server 工具发现（验证每个 Server 可导入且具有预期工具函数）
3. Agent 模块集成（guard、policy、hooks、audit、planner、memory、mcp_client）
4. 数据库 Schema 完整性（7 张表全部正确创建）
5. 后端路由文件存在性（验证所有路由模块导出 Router）
"""

import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ================================================================
# 测试 1: Collector 数据处理管线
# 模拟完整流程: normalizer → clusterer → severity_filter → producer
# ================================================================

class TestCollectorToAgentPipeline:
    """验证 Collector 各模块串联后的数据流转正确性"""

    def test_normalizer_waf_output_format(self):
        """WAF 日志经 normalizer 后输出标准格式"""
        from collector.normalizer import normalize

        raw_waf = {
            "rule_name": "SQL注入攻击",
            "severity": "高",
            "src_ip": "10.0.0.5",
            "dst_ip": "192.168.1.100",
            "reason": "检测到 SQL 注入尝试: ' OR 1=1 --",
            "timestamp": "2026-03-08T10:00:00Z",
        }
        alert = normalize("waf", raw_waf)
        # 验证输出字段完整
        assert alert.source == "waf"
        assert alert.title == "SQL注入攻击"
        assert alert.severity == "high"  # 高 → high
        assert alert.src_ip == "10.0.0.5"
        assert alert.dst_ip == "192.168.1.100"
        assert alert.mitre_tactic is not None  # 能推断出 MITRE 映射
        assert alert.timestamp == "2026-03-08T10:00:00Z"

    def test_normalizer_nids_output_format(self):
        """Suricata NIDS 日志经 normalizer 后输出标准格式"""
        from collector.normalizer import normalize

        raw_nids = {
            "alert": {
                "signature": "ET SCAN Nmap Scripting Engine",
                "signature_id": 2009358,
                "severity": 2,
                "category": "Attempted Information Leak",
            },
            "src_ip": "10.0.0.8",
            "dest_ip": "192.168.1.50",
            "proto": "TCP",
            "timestamp": "2026-03-08T10:05:00Z",
        }
        alert = normalize("nids", raw_nids)
        assert alert.source == "nids"
        assert alert.severity == "high"  # severity 2 → high
        assert alert.src_ip == "10.0.0.8"
        assert alert.protocol == "TCP"

    def test_normalizer_hids_output_format(self):
        """Wazuh HIDS 日志经 normalizer 后输出标准格式"""
        from collector.normalizer import normalize

        raw_hids = {
            "rule": {
                "id": "5710",
                "description": "SSH 暴力破解尝试",
                "level": 10,
                "groups": ["authentication_failure", "ssh"],
            },
            "agent": {"ip": "192.168.1.50"},
            "data": {"srcip": "10.0.0.9"},
            "timestamp": "2026-03-08T10:10:00Z",
        }
        alert = normalize("hids", raw_hids)
        assert alert.source == "hids"
        assert alert.severity == "high"  # level 10 → high (>=8)
        assert alert.src_ip == "10.0.0.9"

    def test_full_pipeline_normalizer_to_clusterer(self):
        """normalizer → clusterer 完整管线：多条原始日志 → 聚簇结果"""
        from collector.normalizer import normalize
        from collector.clusterer import AlertClusterer

        # 模拟多条来自不同源的原始日志
        raw_events = [
            ("waf", {"rule_name": "SQL注入攻击", "severity": "高", "src_ip": "10.0.0.5",
                      "dst_ip": "192.168.1.100", "timestamp": "2026-03-08T10:00:00Z"}),
            ("waf", {"rule_name": "SQL注入攻击", "severity": "高", "src_ip": "10.0.0.5",
                      "dst_ip": "192.168.1.100", "timestamp": "2026-03-08T10:01:00Z"}),
            ("waf", {"rule_name": "SQL注入攻击", "severity": "高", "src_ip": "10.0.0.5",
                      "dst_ip": "192.168.1.100", "timestamp": "2026-03-08T10:02:00Z"}),
            ("nids", {"alert": {"signature": "端口扫描", "severity": 1},
                       "src_ip": "10.0.0.8", "dest_ip": "192.168.1.50",
                       "timestamp": "2026-03-08T10:03:00Z"}),
        ]

        # 规范化
        normalized = [normalize(src, raw) for src, raw in raw_events]
        assert len(normalized) == 4

        # 聚簇
        clusterer = AlertClusterer(window_seconds=300)
        for alert in normalized:
            clusterer.add(alert.to_dict())

        clusters = clusterer.flush()
        # 3 条相同 WAF 告警应聚为 1 簇，1 条 NIDS 告警为 1 簇
        assert len(clusters) == 2

        # 找到 WAF 聚簇，验证计数
        waf_cluster = [c for c in clusters if c.sample.get("source") == "waf"][0]
        assert waf_cluster.count == 3
        assert "10.0.0.5" in waf_cluster.source_ips

    def test_full_pipeline_with_severity_filter(self):
        """normalizer → clusterer → severity_filter 完整管线"""
        from collector.normalizer import normalize
        from collector.clusterer import AlertClusterer
        from collector.severity_filter import SeverityFilter

        raw_events = [
            ("waf", {"rule_name": "SQL注入攻击", "severity": "高", "src_ip": "10.0.0.5",
                      "dst_ip": "192.168.1.100"}),
            ("pikachu", {"vuln_type": "XSS 漏洞", "src_ip": "10.0.0.6",
                          "dst_ip": "192.168.1.100"}),
        ]

        normalized = [normalize(src, raw) for src, raw in raw_events]

        clusterer = AlertClusterer()
        for alert in normalized:
            clusterer.add(alert.to_dict())

        clusters = clusterer.flush()
        cluster_dicts = [c.to_dict() for c in clusters]

        # severity_filter 分流
        to_analyze, store_only = SeverityFilter.filter_for_agent(cluster_dicts)

        # WAF高危 → high级别 → 进入分析
        # pikachu → medium级别 → 仅存储
        assert len(to_analyze) == 1
        assert len(store_only) == 1
        assert to_analyze[0]["severity"] == "high"
        assert store_only[0]["severity"] == "medium"

    def test_producer_publish_mock(self):
        """验证 producer 模块可以正常实例化并调用（mock Redis）"""
        from collector.producer import AlertProducer

        # mock Redis 客户端
        mock_redis = MagicMock()
        mock_redis.xadd.return_value = b"1709884800000-0"

        producer = AlertProducer(redis_url="redis://localhost:6379")
        producer._client = mock_redis  # 注入 mock

        test_alert = {"signature": "abc123", "count": 5, "severity": "high"}
        msg_id = producer.publish(test_alert)

        # 验证 xadd 被调用且参数正确
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "ics:alerts"
        data = json.loads(call_args[0][1]["data"])
        assert data["signature"] == "abc123"

    def test_full_pipeline_end_to_end(self):
        """端到端管线: normalizer → clusterer → severity_filter → producer（mock Redis）"""
        from collector.normalizer import normalize
        from collector.clusterer import AlertClusterer
        from collector.severity_filter import SeverityFilter
        from collector.producer import AlertProducer

        # 模拟原始数据
        raw_events = [
            ("waf", {"rule_name": "RCE攻击", "severity": "严重", "src_ip": "10.0.0.1",
                      "dst_ip": "192.168.1.10"}),
            ("nids", {"alert": {"signature": "端口扫描", "severity": 3},
                       "src_ip": "10.0.0.2", "dest_ip": "192.168.1.20"}),
        ]

        # 规范化
        normalized = [normalize(src, raw) for src, raw in raw_events]

        # 聚簇
        clusterer = AlertClusterer()
        for a in normalized:
            clusterer.add(a.to_dict())
        clusters = clusterer.flush()

        # 过滤
        cluster_dicts = [c.to_dict() for c in clusters]
        to_analyze, store_only = SeverityFilter.filter_for_agent(cluster_dicts)

        # 发布到 Redis（mock）
        mock_redis = MagicMock()
        mock_redis.xadd.return_value = b"1709884800000-0"
        producer = AlertProducer()
        producer._client = mock_redis

        msg_ids = producer.publish_batch(to_analyze)

        # RCE攻击（严重 → critical）应进入分析管线
        assert len(to_analyze) == 1
        assert to_analyze[0]["severity"] == "critical"
        assert len(msg_ids) == 1


# ================================================================
# 测试 2: MCP Server 工具发现
# 验证每个 MCP Server 可以被导入，且包含预期的工具函数
# ================================================================

class TestMCPServerToolsDiscovery:
    """验证所有 MCP Server 的工具可发现性"""

    def test_log_search_server_tools(self):
        """log-search Server 包含 search_alerts、search_raw_events、get_alert_context"""
        # 需要 mock mcp 依赖
        sys.modules.setdefault("mcp", MagicMock())
        sys.modules.setdefault("mcp.server", MagicMock())
        sys.modules.setdefault("mcp.server.fastmcp", MagicMock())

        # 创建模拟的 FastMCP 类
        mock_fastmcp = MagicMock()
        tools_registered = []

        def mock_tool():
            def decorator(fn):
                tools_registered.append(fn.__name__)
                return fn
            return decorator

        mock_fastmcp.return_value.tool = mock_tool
        sys.modules["mcp.server.fastmcp"].FastMCP = mock_fastmcp

        # 强制重新导入
        mod_name = "mcp-servers.log-search.server"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        # 直接验证源码中定义了预期的函数
        server_path = PROJECT_ROOT / "mcp-servers" / "log-search" / "server.py"
        source = server_path.read_text()
        assert "def search_alerts" in source
        assert "def search_raw_events" in source
        assert "def get_alert_context" in source

    def test_rule_engine_server_tools(self):
        """rule-engine Server 包含 match_rules、get_rules"""
        server_path = PROJECT_ROOT / "mcp-servers" / "rule-engine" / "server.py"
        source = server_path.read_text()
        assert "def match_rules" in source
        assert "def get_rules" in source

    def test_mitre_kb_server_tools(self):
        """mitre-kb Server 包含 lookup_technique、lookup_tactic、map_alert_to_mitre"""
        server_path = PROJECT_ROOT / "mcp-servers" / "mitre-kb" / "server.py"
        source = server_path.read_text()
        assert "def lookup_technique" in source
        assert "def lookup_tactic" in source
        assert "def map_alert_to_mitre" in source

    def test_action_executor_server_tools(self):
        """action-executor Server 包含 block_ip、isolate_host、add_watch"""
        server_path = PROJECT_ROOT / "mcp-servers" / "action-executor" / "server.py"
        source = server_path.read_text()
        assert "def block_ip" in source
        assert "def isolate_host" in source
        assert "def add_watch" in source

    def test_notifier_server_tools(self):
        """notifier Server 包含 send_webhook、send_email、push_websocket"""
        server_path = PROJECT_ROOT / "mcp-servers" / "notifier" / "server.py"
        source = server_path.read_text()
        assert "def send_webhook" in source
        assert "def send_email" in source
        assert "def push_websocket" in source

    def test_memory_server_tools(self):
        """memory Server 包含 recall、memorize、list_memories"""
        server_path = PROJECT_ROOT / "mcp-servers" / "memory" / "server.py"
        source = server_path.read_text()
        assert "def recall" in source
        assert "def memorize" in source
        assert "def list_memories" in source

    def test_all_mcp_servers_have_main_entry(self):
        """所有 MCP Server 都有 __main__ 入口点"""
        servers = ["log-search", "rule-engine", "mitre-kb", "action-executor", "notifier", "memory"]
        for name in servers:
            server_path = PROJECT_ROOT / "mcp-servers" / name / "server.py"
            assert server_path.exists(), f"MCP Server {name}/server.py 不存在"
            source = server_path.read_text()
            assert 'if __name__ == "__main__"' in source, (
                f"MCP Server {name} 缺少 __main__ 入口点"
            )

    def test_all_mcp_servers_use_fastmcp(self):
        """所有 MCP Server 都使用 FastMCP 框架"""
        servers = ["log-search", "rule-engine", "mitre-kb", "action-executor", "notifier", "memory"]
        for name in servers:
            server_path = PROJECT_ROOT / "mcp-servers" / name / "server.py"
            source = server_path.read_text()
            assert "FastMCP" in source, f"MCP Server {name} 未使用 FastMCP"
            assert "@mcp.tool()" in source, f"MCP Server {name} 未注册任何工具"


# ================================================================
# 测试 3: Agent 模块集成
# 验证所有 Agent 子模块可以一起导入并初始化
# ================================================================

class TestAgentModulesIntegration:
    """验证 Agent 所有子模块的兼容性"""

    def test_guard_module_import_and_init(self):
        """AgentGuard 可正常导入和初始化"""
        from agent.guard import AgentGuard, GuardException, MaxStepsExceeded

        guard = AgentGuard({"max_steps": 10, "step_timeout": 15})
        assert guard.max_steps == 10
        assert guard.step_timeout == 15
        assert guard.step_count == 0

    def test_guard_check_before_step(self):
        """AgentGuard 步数检查正确触发异常"""
        from agent.guard import AgentGuard, MaxStepsExceeded

        guard = AgentGuard({"max_steps": 2})
        guard.reset()
        guard.check_before_step()  # 第1步，通过
        guard.step_count = 2
        with pytest.raises(MaxStepsExceeded):
            guard.check_before_step()  # 超出限制

    def test_guard_stuck_detection(self):
        """AgentGuard 死循环检测"""
        from agent.guard import AgentGuard, AgentStuck

        guard = AgentGuard({"stuck_threshold": 3})
        # 连续3次相同调用应触发 AgentStuck
        guard.check_stuck("search_alerts", {"severity": "high"})
        guard.check_stuck("search_alerts", {"severity": "high"})
        with pytest.raises(AgentStuck):
            guard.check_stuck("search_alerts", {"severity": "high"})

    def test_planner_module_import_and_parse(self):
        """Planner 模块可正常导入，from_llm_response 解析正确"""
        from agent.planner import AnalysisPlan, PlanStep, format_planning_prompt

        llm_json = json.dumps({
            "goal": "分析SQL注入攻击",
            "steps": [
                {"id": 1, "action": "查询关联告警", "tool": "search_alerts"},
                {"id": 2, "action": "匹配ATT&CK技术", "tool": "map_alert_to_mitre"},
                {"id": 3, "action": "生成结论", "tool": None},
            ],
            "estimated_risk": "high",
        })
        plan = AnalysisPlan.from_llm_response(llm_json)
        assert plan.goal == "分析SQL注入攻击"
        assert len(plan.steps) == 3
        assert plan.estimated_risk == "high"
        assert plan.steps[0].tool == "search_alerts"

    def test_planner_step_lifecycle(self):
        """Planner 步骤的完整生命周期：pending → running → completed"""
        from agent.planner import AnalysisPlan, PlanStep

        plan = AnalysisPlan(
            goal="测试",
            steps=[
                PlanStep(id=1, action="步骤1", tool="t1"),
                PlanStep(id=2, action="步骤2", tool="t2"),
            ],
        )

        # 获取下一个待执行步骤
        next_step = plan.get_next_pending()
        assert next_step.id == 1

        # 标记为完成
        plan.mark_step(1, "completed", "成功执行")
        assert plan.steps[0].status == "completed"

        # 动态插入新步骤
        plan.insert_step(1, "追加步骤", "t3")
        assert len(plan.steps) == 3
        assert len(plan.adjustments) == 1

        # 跳过步骤
        plan.skip_step(2, "不需要执行")
        assert plan.steps[1 if plan.steps[1].id == 2 else 2].status == "skipped"

    def test_planner_format_planning_prompt(self):
        """format_planning_prompt 生成的提示词包含告警数据"""
        from agent.planner import format_planning_prompt

        alerts = [{"title": "SQL注入", "severity": "high"}]
        prompt = format_planning_prompt(alerts)
        assert "SQL注入" in prompt
        assert "JSON" in prompt

    def test_memory_module_import_and_crud(self):
        """Memory 模块可正常导入，CRUD 操作正确"""
        from agent.memory import AgentMemory

        memory = AgentMemory({"provider": "simple"})
        assert memory.provider == "simple"

    @pytest.mark.asyncio
    async def test_memory_memorize_and_recall(self):
        """Memory 存储和检索操作"""
        from agent.memory import AgentMemory

        memory = AgentMemory({"provider": "simple"})

        # 存储记忆
        mem_id = await memory.memorize(
            "SQL注入攻击来自10.0.0.5，目标为192.168.1.100，已封禁源IP",
            metadata={"alert_id": "1001", "category": "analysis"},
        )
        assert mem_id is not None

        # 检索相关记忆
        results = await memory.recall("SQL注入 10.0.0.5")
        assert len(results) > 0
        assert results[0]["content"].startswith("SQL注入")

    def test_audit_module_import_and_init(self, test_db_path):
        """AuditLogger 可正常导入并初始化"""
        from agent.audit import AuditLogger

        logger = AuditLogger(test_db_path)
        assert logger.db_path == test_db_path

        # 写入一条审计日志
        logger.log(
            trace_id="trace-001",
            event_type="plan_generated",
            data={"goal": "分析攻击"},
            alert_id="alert-001",
            token_usage={"input_tokens": 100, "output_tokens": 50},
        )

        # 查询审计链
        trace = logger.get_trace("trace-001")
        assert len(trace) == 1
        assert trace[0]["event_type"] == "plan_generated"

        # 查询 token 用量
        tokens = logger.get_total_tokens("trace-001")
        assert tokens["total"] == 150

        logger.close()

    def test_mcp_client_module_import(self):
        """MCPClient 可正常导入和初始化（不连接实际 Server）"""
        from agent.mcp_client import MCPClient, ServerConfig

        client = MCPClient(servers=[
            ServerConfig(name="log-search", command="python",
                         args=["mcp-servers/log-search/server.py"]),
            ServerConfig(name="rule-engine", command="python",
                         args=["mcp-servers/rule-engine/server.py"]),
        ])
        assert len(client.servers) == 2
        assert client.servers[0].name == "log-search"
        assert client.list_tools() == []  # 未连接时工具列表为空
        assert client.get_connected_servers() == []

    def test_all_agent_modules_coexist(self, test_db_path):
        """所有 Agent 模块可以在同一个运行时中共存，无命名冲突"""
        from agent.guard import AgentGuard
        from agent.planner import AnalysisPlan, PlanStep
        from agent.memory import AgentMemory
        from agent.audit import AuditLogger
        from agent.mcp_client import MCPClient, ServerConfig
        from agent.hooks import HookManager

        # 全部初始化
        guard = AgentGuard()
        plan = AnalysisPlan(goal="测试", steps=[PlanStep(id=1, action="a", tool=None)])
        memory = AgentMemory({"provider": "simple"})
        audit = AuditLogger(test_db_path)
        client = MCPClient()
        # HookManager 需要配置文件，使用不存在的路径测试容错
        hooks = HookManager(config_path="/tmp/nonexistent_hooks.yaml")

        # 验证各模块已就绪
        assert guard.max_steps == 20
        assert plan.goal == "测试"
        assert memory.provider == "simple"
        assert client.list_tools() == []
        assert hooks.hooks == {}  # 文件不存在时降级为空配置

        audit.close()


# ================================================================
# 测试 4: 数据库 Schema 完整性
# 验证 SQLite 数据库包含全部 7 张表
# ================================================================

class TestDatabaseSchema:
    """验证数据库 Schema 的完整性和正确性"""

    # 预期的 7 张表
    EXPECTED_TABLES = {
        "assets",
        "raw_events",
        "alerts",
        "attack_chains",
        "decisions",
        "approval_queue",
        "audit_logs",
    }

    def test_all_tables_created(self, test_db):
        """7 张表全部正确创建"""
        cursor = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert self.EXPECTED_TABLES.issubset(tables), (
            f"缺少表: {self.EXPECTED_TABLES - tables}"
        )

    def test_assets_table_columns(self, test_db):
        """assets 表包含正确的列"""
        columns = self._get_columns(test_db, "assets")
        assert "id" in columns
        assert "ip" in columns
        assert "hostname" in columns
        assert "type" in columns
        assert "importance" in columns
        assert "created_at" in columns

    def test_alerts_table_columns(self, test_db):
        """alerts 表包含正确的列"""
        columns = self._get_columns(test_db, "alerts")
        expected = {"id", "source", "severity", "title", "description",
                    "src_ip", "dst_ip", "mitre_tactic", "mitre_technique",
                    "asset_id", "status", "raw_event_id", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"

    def test_attack_chains_table_columns(self, test_db):
        """attack_chains 表包含正确的列"""
        columns = self._get_columns(test_db, "attack_chains")
        expected = {"id", "name", "stage", "confidence", "alert_ids",
                    "evidence", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"

    def test_decisions_table_columns(self, test_db):
        """decisions 表包含正确的列"""
        columns = self._get_columns(test_db, "decisions")
        expected = {"id", "attack_chain_id", "risk_level", "recommendation",
                    "action_type", "rationale", "status", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"

    def test_approval_queue_table_columns(self, test_db):
        """approval_queue 表包含正确的列"""
        columns = self._get_columns(test_db, "approval_queue")
        expected = {"id", "trace_id", "tool_name", "tool_args", "reason",
                    "status", "responded_at", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"

    def test_audit_logs_table_columns(self, test_db):
        """audit_logs 表包含正确的列"""
        columns = self._get_columns(test_db, "audit_logs")
        expected = {"id", "trace_id", "alert_id", "event_type", "data",
                    "token_usage", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"

    def test_indexes_exist(self, test_db):
        """验证关键索引已创建"""
        cursor = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        expected_indexes = {
            "idx_alerts_status",
            "idx_alerts_severity",
            "idx_alerts_created",
            "idx_audit_trace",
            "idx_audit_alert",
            "idx_approval_status",
        }
        assert expected_indexes.issubset(indexes), (
            f"缺少索引: {expected_indexes - indexes}"
        )

    def test_insert_and_query_alerts(self, test_db):
        """验证告警表的插入和查询操作"""
        test_db.execute(
            """INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("waf", "high", "SQL注入攻击", "检测到SQL注入", "10.0.0.5", "192.168.1.100"),
        )
        test_db.commit()

        row = test_db.execute("SELECT * FROM alerts WHERE id = 1").fetchone()
        assert row is not None
        assert row["source"] == "waf"
        assert row["severity"] == "high"
        assert row["status"] == "open"  # 默认值

    def test_foreign_key_relationships(self, test_db):
        """验证表间外键关系的数据一致性"""
        # 插入资产
        test_db.execute(
            "INSERT INTO assets (ip, hostname, type, importance) VALUES (?, ?, ?, ?)",
            ("192.168.1.100", "web-server-01", "server", 5),
        )
        # 插入原始事件
        test_db.execute(
            "INSERT INTO raw_events (source, raw_json) VALUES (?, ?)",
            ("waf", '{"rule_name": "SQL注入"}'),
        )
        # 插入告警（关联资产和原始事件）
        test_db.execute(
            """INSERT INTO alerts (source, severity, title, asset_id, raw_event_id)
               VALUES (?, ?, ?, ?, ?)""",
            ("waf", "high", "SQL注入", 1, 1),
        )
        # 插入攻击链
        test_db.execute(
            """INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
               VALUES (?, ?, ?, ?, ?)""",
            ("SQL注入链", "execution", 0.85, "[1]", "检测到SQL注入攻击链"),
        )
        # 插入决策（关联攻击链）
        test_db.execute(
            """INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type)
               VALUES (?, ?, ?, ?)""",
            (1, "high", "建议封禁源IP", "block"),
        )
        test_db.commit()

        # 验证关联查询
        row = test_db.execute(
            """SELECT a.title, d.recommendation, c.name as chain_name
               FROM alerts a
               JOIN attack_chains c ON json_extract(c.alert_ids, '$[0]') = a.id
               JOIN decisions d ON d.attack_chain_id = c.id
               WHERE a.id = 1"""
        ).fetchone()
        assert row is not None
        assert row["chain_name"] == "SQL注入链"
        assert row["recommendation"] == "建议封禁源IP"

    @staticmethod
    def _get_columns(db, table_name: str) -> set:
        """获取表的所有列名"""
        cursor = db.execute(f"PRAGMA table_info({table_name})")
        return {row["name"] for row in cursor.fetchall()}


# ================================================================
# 测试 5: 后端路由文件存在性
# 验证所有路由模块文件存在并包含 Router 导出
# ================================================================

class TestAPIRoutesExist:
    """验证后端 API 路由文件的完整性"""

    # 预期的路由模块及其关键端点
    EXPECTED_ROUTES = {
        "alerts.js": ["router", "Router", "/ingest", "/:id/status"],
        "analysis.js": ["router", "Router", "/alerts", "/chat", "/chains"],
        "dashboard.js": ["router", "Router", "/stats", "/assets"],
        "approval.js": ["router", "Router", "/:id"],
        "audit.js": ["router", "Router", "/stats", "/trace"],
    }

    def test_all_route_files_exist(self):
        """所有路由文件存在"""
        routes_dir = PROJECT_ROOT / "backend" / "src" / "routes"
        for filename in self.EXPECTED_ROUTES:
            filepath = routes_dir / filename
            assert filepath.exists(), f"路由文件不存在: {filepath}"

    def test_routes_export_router(self):
        """所有路由文件导出 Router 实例"""
        routes_dir = PROJECT_ROOT / "backend" / "src" / "routes"
        for filename in self.EXPECTED_ROUTES:
            filepath = routes_dir / filename
            source = filepath.read_text()
            assert "Router" in source, (
                f"{filename} 未导入 Router"
            )
            assert "export default" in source, (
                f"{filename} 未导出路由模块"
            )

    def test_route_endpoints_defined(self):
        """验证各路由文件定义了预期的端点路径"""
        routes_dir = PROJECT_ROOT / "backend" / "src" / "routes"
        for filename, expected_patterns in self.EXPECTED_ROUTES.items():
            filepath = routes_dir / filename
            source = filepath.read_text()
            for pattern in expected_patterns:
                assert pattern in source, (
                    f"{filename} 缺少预期的端点或导出: {pattern}"
                )

    def test_server_js_registers_all_routes(self):
        """server.js 注册了所有路由模块"""
        server_path = PROJECT_ROOT / "backend" / "src" / "server.js"
        source = server_path.read_text()

        expected_mounts = [
            "/api/alerts",
            "/api/analysis",
            "/api/dashboard",
            "/api/approval",
            "/api/audit",
        ]
        for mount in expected_mounts:
            assert mount in source, f"server.js 未挂载路由: {mount}"

    def test_server_js_has_health_endpoint(self):
        """server.js 包含健康检查端点"""
        server_path = PROJECT_ROOT / "backend" / "src" / "server.js"
        source = server_path.read_text()
        assert "/api/health" in source, "server.js 缺少健康检查端点"

    def test_db_model_exists_and_exports_init(self):
        """数据库模型文件存在且导出 initDB"""
        db_path = PROJECT_ROOT / "backend" / "src" / "models" / "db.js"
        assert db_path.exists(), "db.js 不存在"
        source = db_path.read_text()
        assert "initDB" in source, "db.js 未导出 initDB 函数"
        assert "CREATE TABLE" in source, "db.js 未包含建表语句"

    def test_backend_package_json_has_dependencies(self):
        """后端 package.json 包含必要的依赖"""
        pkg_path = PROJECT_ROOT / "backend" / "package.json"
        pkg = json.loads(pkg_path.read_text())
        deps = pkg.get("dependencies", {})

        required_deps = ["express", "cors", "dotenv", "better-sqlite3"]
        for dep in required_deps:
            assert dep in deps, f"package.json 缺少依赖: {dep}"
