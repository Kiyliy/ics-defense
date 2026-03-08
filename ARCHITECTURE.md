# AI驱动的工控安全指挥决策一体机 - 核心架构

## 设计原则

- **单 Agent 架构**：一个 AI Agent 通过 MCP 工具完成所有分析与处置，不做多 Agent 编排
- **Plan-then-Act**：Agent 先制定分析计划（Planning），再逐步执行，支持动态调整
- **日志聚簇**：相同日志聚合为 `{日志内容, 出现次数}`，避免重复灌入 AI
- **分级过滤**：只有 error 级别告警进入 Agent 分析，warning/info 仅存储和展示
- **Claude SDK + MCP**：Agent 使用 `anthropic` SDK 直接调用 Claude，MCP 客户端使用官方 `mcp` SDK
- **MCP 微服务化**：每个 MCP Server 是独立微服务，可独立部署和扩展
- **测试驱动**：每个模块必须附带测试，代码和测试同步交付
- **Agent 记忆**：基于 Mem0 实现长期记忆，Agent 可记住历史分析经验并检索相似案例
- **高危操作审批**：阻断/隔离等高危操作需人工确认后才执行
- **可观测性**：所有工具调用、Agent 推理过程、决策依据均有审计日志

## 目录结构

```
ics-defense/
│
├── collector/                       # 模块 A：数据收集 + 聚簇
│   ├── sources/                     # 各数据源采集器
│   │   ├── waf_collector.py         # 雷池 WAF 日志采集
│   │   ├── nids_collector.py        # Suricata NIDS 告警采集
│   │   ├── hids_collector.py        # Wazuh HIDS 告警采集
│   │   ├── pikachu_collector.py     # PIKACHU 靶场日志采集
│   │   └── soc_collector.py         # SOC 通用日志采集
│   ├── normalizer.py                # 事件规范化（字段映射、时间对齐）
│   ├── clusterer.py                 # 日志聚簇（相同日志合并 + 计数）
│   ├── severity_filter.py           # 分级过滤（error → Agent 队列，warning/info → 仅存储）
│   └── producer.py                  # Redis Streams 生产者（推送聚簇后的事件）
│
├── agent/                           # 模块 B：AI Agent（核心）
│   ├── agent.py                     # Agent 主循环（Planning + ReAct Loop）
│   ├── planner.py                   # 规划模块（任务分解 + 计划生成）
│   ├── mcp_client.py                # MCP 客户端（官方 mcp SDK，多 Server 连接管理）
│   ├── memory.py                    # Agent 记忆模块（基于 Mem0）
│   ├── policy.py                    # 权限策略（工具分级 + 审批流）
│   ├── hooks.py                     # 钩子管理（事件触发通知/动作）
│   ├── guard.py                     # 安全守卫（max_steps / 卡死检测 / 重试）
│   ├── audit.py                     # 审计日志（工具调用记录 + token 追踪）
│   ├── service.py                   # Agent Service（FastAPI HTTP 入口，桥接 Express）
│   └── prompts/                     # LLM 提示词模板
│       ├── system.txt               # Agent 系统提示词（角色、能力、输出格式）
│       ├── planning.txt             # 规划阶段提示词（生成分析计划）
│       └── alert_analysis.txt       # 告警分析提示词模板
│
├── mcp-servers/                     # 模块 C：MCP 工具服务（每个独立微服务）
│   ├── log-search/                  # MCP Server：日志查询
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── rule-engine/                 # MCP Server：规则匹配
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── mitre-kb/                    # MCP Server：MITRE ATT&CK 知识库
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── action-executor/             # MCP Server：处置执行（高危，需审批）
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── notifier/                    # MCP Server：消息通知
│   │   ├── server.py
│   │   └── Dockerfile
│   └── memory/                      # MCP Server：Agent 记忆（基于 Mem0）
│       ├── server.py
│       └── Dockerfile
│
├── backend/                         # 模块 D：API 服务层
│   ├── src/
│   │   ├── server.js                # Express 入口
│   │   ├── models/db.js             # SQLite 数据库
│   │   ├── services/
│   │   │   └── normalizer.js        # JS 端规范化（API 直接接入用）
│   │   └── routes/
│   │       ├── alerts.js            # 告警 CRUD + 接入
│   │       ├── analysis.js          # Agent 分析触发 + 结果查询
│   │       ├── approval.js          # 人工审批 API（高危操作确认）
│   │       ├── audit.js             # 审计日志查询 API
│   │       └── dashboard.js         # 统计 + 资产管理
│   └── .env
│
├── frontend/                        # 模块 E：可视化指挥面板
│   ├── src/
│   │   ├── views/
│   │   │   ├── Dashboard.vue        # 指挥总览（统计、告警趋势）
│   │   │   ├── AlertList.vue        # 告警列表（筛选、详情）
│   │   │   ├── AttackChain.vue      # 攻击链视图（阶段可视化）
│   │   │   ├── AIChat.vue           # AI 对话面板（含推理过程展示）
│   │   │   ├── ApprovalQueue.vue    # 待审批队列（高危操作确认）
│   │   │   ├── AuditLog.vue         # 审计日志查看
│   │   │   └── AssetMap.vue         # 资产拓扑图
│   │   ├── components/
│   │   └── App.vue
│   └── package.json
│
├── docker-compose.yml               # 一键部署
└── ARCHITECTURE.md                  # 本文件
```

## 数据流

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      数据收集层 (collector/)                              │
│                                                                         │
│  WAF ──┐                                                                │
│  NIDS ─┤                                                                │
│  HIDS ─┼→ normalizer → clusterer → producer → Redis Streams            │
│  靶场 ─┤   (字段标准化)  (聚簇去重)  (推送队列)                           │
│  SOC ──┘                                                                │
│                                                                         │
│  聚簇示例：                                                              │
│  原始: 同一条 SQL注入告警 × 10000次                                      │
│  聚簇后: { alert: "SQL注入 from 10.0.0.5", count: 10000,               │
│            first_seen: "...", last_seen: "..." }                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      分级过滤 (severity_filter)                          │
│                                                                         │
│  error/critical  ──→  进入 Agent 分析                                    │
│  warning         ──→  仅存储 + 前端展示（不消耗 AI 资源）                  │
│  info            ──→  仅存储                                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ (仅 error/critical)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  AI Agent (agent/) - Claude SDK                          │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  Phase 1: Planning（规划）                                      │     │
│  │                                                                  │     │
│  │  收到聚簇告警 → 检索记忆(相似案例) → Claude 生成分析计划:        │     │
│  │    plan = [                                                      │     │
│  │      { step: 1, action: "查询源IP历史告警", tool: "log-search" },│     │
│  │      { step: 2, action: "匹配关联规则", tool: "rule-engine" },   │     │
│  │      { step: 3, action: "映射ATT&CK技术", tool: "mitre-kb" },   │     │
│  │      { step: 4, action: "生成处置建议", tool: null },            │     │
│  │    ]                                                             │     │
│  └──────────────────────┬───────────────────────────────────────────┘     │
│                         ▼                                                │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  Phase 2: Execution（执行 - ReAct 循环）                       │     │
│  │                                                                  │     │
│  │  for step in plan:                            ┌─────────────┐   │     │
│  │    Claude 思考 → 调用 MCP 工具 → 获取结果      │  guard.py   │   │     │
│  │    ├─ 普通工具 → 直接执行                      │  max_steps  │   │     │
│  │    ├─ 高危工具 → policy.py 检查 → 需审批？     │  卡死检测   │   │     │
│  │    │   ├─ 是 → 暂停，等待人工确认               │  失败重试   │   │     │
│  │    │   └─ 否 → 执行                            │  超时控制   │   │     │
│  │    └─ 根据结果，Claude 可动态调整后续计划       └─────────────┘   │     │
│  │                                                                  │     │
│  │  每次工具调用 → audit.py 记录审计日志                            │     │
│  │  触发 hooks → 检查是否需要发送通知                                │     │
│  └──────────────────────┬───────────────────────────────────────────┘     │
│                         ▼                                                │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  Phase 3: Conclusion（总结）                                    │     │
│  │                                                                  │     │
│  │  Agent 输出结构化结论 → 存储记忆 → 写入数据库                    │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                          │                                              │
│              通过 MCP Client 调用工具                                    │
│                          │                                              │
│    ┌──────────┬──────────┼──────────┬───────────────┐                   │
│    ▼          ▼          ▼          ▼               ▼                   │
│  ┌────────┐┌────────┐┌────────┐┌───────────────┐┌────────┐            │
│  │  log-  ││ rule-  ││ mitre- ││   action-     ││notifier│            │
│  │ search ││ engine ││   kb   ││  executor ⚠️  ││        │            │
│  │        ││        ││        ││  (需审批)      ││        │            │
│  └────────┘└────────┘└────────┘└───────────────┘└────────┘            │
│                          │                                              │
│                          ▼                                              │
│                    ┌──────────┐                                         │
│                    │  memory  │  ← Mem0 (向量检索 + 自动提取关键事实)     │
│                    │  (记忆)   │                                         │
│                    └──────────┘                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────┐    ┌───────────────────────────────────┐
│   存储层                    │    │   展示层 (frontend/ Vue3)          │
│                            │    │                                   │
│  SQLite                    │    │   Dashboard ──→ 统计总览          │
│  ├─ alerts (聚簇后告警)     │    │   AlertList ──→ 告警管理          │
│  ├─ attack_chains          │    │   AttackChain ──→ 攻击链可视化    │
│  ├─ decisions              │───→│   AIChat ──→ AI 对话 + 推理链     │
│  ├─ assets                 │    │   ApprovalQueue ──→ 待审批操作    │
│  ├─ raw_events             │    │   AuditLog ──→ 审计日志           │
│  ├─ audit_logs             │    │   AssetMap ──→ 资产拓扑           │
│  └─ approval_queue         │    │                                   │
└────────────────────────────┘    └───────────────────────────────────┘
```

---

## 模块详细设计与验收标准

### 模块 B1：Planning 规划模块 (`agent/planner.py`)

Agent 收到告警后，先制定分析计划再执行，而非直接进入 ReAct 循环盲目分析。

**工作方式：**

```
输入: 聚簇告警 + 历史记忆
  ↓
Claude 生成分析计划 (JSON):
  {
    "goal": "分析来自 10.0.0.5 的 SQL 注入攻击",
    "steps": [
      { "id": 1, "action": "查询该IP最近24h所有告警", "tool": "search_alerts" },
      { "id": 2, "action": "检查是否匹配已知攻击链规则", "tool": "match_rules" },
      { "id": 3, "action": "映射到MITRE ATT&CK技术", "tool": "map_alert_to_mitre" },
      { "id": 4, "action": "综合研判，生成处置建议", "tool": null }
    ],
    "estimated_risk": "high"
  }
  ↓
逐步执行，每步完成后 Claude 可动态调整后续步骤
  ↓
例如：步骤1发现该IP还有端口扫描行为
  → Claude 动态插入新步骤："查询该IP的端口扫描详情"
```

**动态调整机制：**
- 每个步骤执行完毕后，Agent 重新评估剩余计划
- 可以插入新步骤（发现新线索）、跳过步骤（已有足够信息）、修改步骤参数
- 计划调整记录在审计日志中，保证可追溯

**攻击链推理：**
- 当多个告警涉及同一 IP 或同一时间窗口时，Agent 在规划阶段就将它们作为整体分析
- 计划中包含"关联分析"步骤，尝试将多个独立告警串联成攻击链
- 输出攻击链时标注各阶段和置信度，存入 `attack_chains` 表

**验收脚本：**
```bash
# B1-T1: 规划阶段能生成有效的分析计划
python -m pytest tests/test_planner.py::test_generate_plan -v
# 输入: 一条 SQL 注入聚簇告警
# 期望: 返回 JSON 计划，包含 steps 数组，每个 step 有 id/action/tool 字段

# B1-T2: 动态调整计划
python -m pytest tests/test_planner.py::test_dynamic_replan -v
# 输入: 执行步骤1后发现新线索
# 期望: 计划自动插入新步骤，steps 数量变化

# B1-T3: 多告警攻击链规划
python -m pytest tests/test_planner.py::test_attack_chain_planning -v
# 输入: 3条不同类型但来自同一IP的告警
# 期望: 计划中包含关联分析步骤，最终输出攻击链

# B1-T4: 计划输出格式校验
python -m pytest tests/test_planner.py::test_plan_schema -v
# 期望: 计划 JSON 通过 schema 校验（goal, steps, estimated_risk 必填）
```

---

### 模块 B2：Permission / RBAC 权限模块 (`agent/policy.py`)

工具按危险等级分级，高危操作需要人工审批后才执行。

**工具权限分级：**

| 等级 | 说明 | 工具 | 行为 |
|------|------|------|------|
| `auto` | 只读/无害，自动执行 | `search_alerts`, `search_raw_events`, `get_alert_context`, `match_rules`, `get_rules`, `lookup_technique`, `lookup_tactic`, `map_alert_to_mitre`, `recall`, `memorize`, `list_memories` | 直接执行，无需确认 |
| `notify` | 有外部影响，执行后通知 | `send_webhook`, `send_email`, `push_websocket`, `add_watch` | 直接执行，但通过 hook 发送通知告知操作员 |
| `approve` | 高危操作，必须人工审批 | `block_ip`, `isolate_host` | 暂停执行 → 写入 `approval_queue` → 等待人工确认 → 确认后继续 |

**审批流程：**

```
Agent 调用 block_ip("10.0.0.5")
  ↓
policy.py 检查权限等级 → "approve"
  ↓
写入 approval_queue 表:
  { id, tool: "block_ip", args: {"ip": "10.0.0.5"},
    reason: "Agent分析认为该IP正在进行SQL注入攻击",
    status: "pending", created_at }
  ↓
通知操作员（WebSocket推送到前端 ApprovalQueue 页面）
  ↓
操作员在前端点击 "批准" 或 "拒绝"
  ↓
PATCH /api/approval/:id  { status: "approved" | "rejected" }
  ↓
Agent 收到结果:
  approved → 执行 block_ip，继续循环
  rejected → Agent 得知被拒绝，调整后续决策
```

**配置文件 (`agent/tool_policy.yaml`)：**

```yaml
tool_levels:
  # auto: 只读查询，自动执行
  auto:
    - search_alerts
    - search_raw_events
    - get_alert_context
    - match_rules
    - get_rules
    - lookup_technique
    - lookup_tactic
    - map_alert_to_mitre
    - recall
    - memorize
    - list_memories

  # notify: 执行后通知操作员
  notify:
    - send_webhook
    - send_email
    - push_websocket
    - add_watch

  # approve: 高危操作，需人工审批
  approve:
    - block_ip
    - isolate_host

# 审批超时（秒），超时自动拒绝
approval_timeout: 300
```

**验收脚本：**

```bash
# B2-T1: auto 级别工具直接执行
python -m pytest tests/test_policy.py::test_auto_tool_direct_exec -v
# 输入: 调用 search_alerts
# 期望: 直接返回结果，无审批流程

# B2-T2: approve 级别工具触发审批
python -m pytest tests/test_policy.py::test_approve_tool_triggers_approval -v
# 输入: Agent 调用 block_ip
# 期望: 不立即执行，而是写入 approval_queue 表，状态为 pending

# B2-T3: 审批通过后执行
python -m pytest tests/test_policy.py::test_approved_then_execute -v
# 输入: approval_queue 中 pending 记录被更新为 approved
# 期望: block_ip 实际执行，Agent 继续后续步骤

# B2-T4: 审批拒绝后 Agent 调整
python -m pytest tests/test_policy.py::test_rejected_then_agent_adapts -v
# 输入: 审批被 rejected
# 期望: Agent 收到拒绝结果，不执行 block_ip，后续决策做出调整

# B2-T5: 审批超时自动拒绝
python -m pytest tests/test_policy.py::test_approval_timeout -v
# 输入: approval_queue 记录超过 300s 无响应
# 期望: 自动标记为 rejected

# B2-T6: notify 级别工具执行后发通知
python -m pytest tests/test_policy.py::test_notify_tool_sends_notification -v
# 输入: 调用 send_webhook
# 期望: 工具执行成功，同时触发 hook 通知操作员
```

---

### 模块 B3：Hooks 钩子系统 (`agent/hooks.py`)

轻量级事件钩子，在 Agent 生命周期的关键节点触发动作。不是独立模块/微服务，而是 Agent Loop 内的配置驱动逻辑。

**钩子触发点：**

| 钩子 | 触发时机 | 典型动作 |
|------|---------|---------|
| `on_alert_received` | Agent 收到新的聚簇告警 | 如果 severity=critical，立即 WebSocket 推送前端 |
| `on_plan_generated` | 分析计划生成后 | 日志记录计划内容 |
| `on_tool_called` | 每次 MCP 工具调用前 | 审计日志记录 |
| `on_tool_result` | 每次 MCP 工具调用后 | 审计日志记录结果 |
| `on_approval_needed` | 高危工具触发审批时 | WebSocket 推送到前端 ApprovalQueue |
| `on_decision_made` | Agent 生成最终处置决策 | 通知操作员（Webhook/邮件） |
| `on_error` | 工具调用失败或异常 | 记录错误日志，触发告警 |
| `on_loop_finished` | Agent 循环结束 | 记录 token 用量、总耗时 |

**配置文件 (`agent/hooks.yaml`)：**

```yaml
hooks:
  on_alert_received:
    - condition: "severity == 'critical'"
      action: push_websocket
      params: { channel: "critical_alerts" }

  on_decision_made:
    - condition: "risk_level >= 'high'"
      action: send_webhook
      params: { url: "${WEBHOOK_URL}" }
    - condition: "always"
      action: push_websocket
      params: { channel: "decisions" }

  on_error:
    - condition: "always"
      action: log_error
    - condition: "consecutive_errors >= 3"
      action: send_email
      params: { to: "${ADMIN_EMAIL}", subject: "Agent 连续失败告警" }
```

**验收脚本：**

```bash
# B3-T1: critical 告警触发 WebSocket 推送
python -m pytest tests/test_hooks.py::test_critical_alert_triggers_ws -v
# 输入: severity=critical 的告警进入 Agent
# 期望: on_alert_received hook 触发，WebSocket 消息发送

# B3-T2: 决策生成后触发 Webhook 通知
python -m pytest tests/test_hooks.py::test_decision_triggers_webhook -v
# 输入: Agent 生成 risk_level=high 的决策
# 期望: on_decision_made hook 触发，Webhook 请求发送

# B3-T3: 条件不满足时不触发
python -m pytest tests/test_hooks.py::test_condition_not_met_skips -v
# 输入: severity=warning 的告警（不应进入 Agent，但测试 hook 条件）
# 期望: on_alert_received 的 condition 不满足，不触发动作

# B3-T4: hooks.yaml 配置热加载
python -m pytest tests/test_hooks.py::test_config_hot_reload -v
# 期望: 修改 hooks.yaml 后，不重启 Agent 即可生效
```

---

### 模块 B4：Error Handling / Guard 安全守卫 (`agent/guard.py`)

防止 Agent 循环卡死、工具调用失败导致流程中断。

**保护机制：**

| 机制 | 说明 | 默认值 |
|------|------|--------|
| `max_steps` | 单次分析最大步数（工具调用次数） | 20 |
| `max_retries` | 单个工具调用失败重试次数 | 2 |
| `step_timeout` | 单步执行超时 | 30s |
| `total_timeout` | 整个分析流程超时 | 300s (5min) |
| `stuck_detection` | 连续 N 次调用相同工具+相同参数视为卡死 | 3 |
| `fallback` | MCP Server 不可用时的降级策略 | 跳过该工具，告知 Agent |

**Guard 伪代码：**

```python
class AgentGuard:
    def __init__(self, config):
        self.max_steps = config.get("max_steps", 20)
        self.max_retries = config.get("max_retries", 2)
        self.step_timeout = config.get("step_timeout", 30)
        self.total_timeout = config.get("total_timeout", 300)
        self.stuck_threshold = config.get("stuck_threshold", 3)
        self.step_count = 0
        self.call_history = []  # [(tool_name, args_hash), ...]

    def check_before_step(self):
        """每步执行前检查"""
        if self.step_count >= self.max_steps:
            raise MaxStepsExceeded(f"已达最大步数 {self.max_steps}")
        if time.time() - self.start_time > self.total_timeout:
            raise TotalTimeoutExceeded(f"总超时 {self.total_timeout}s")

    def check_stuck(self, tool_name, args):
        """检测是否陷入死循环"""
        key = (tool_name, hash(json.dumps(args, sort_keys=True)))
        recent = self.call_history[-self.stuck_threshold:]
        if len(recent) == self.stuck_threshold and all(c == key for c in recent):
            raise AgentStuck(f"连续 {self.stuck_threshold} 次调用 {tool_name} 相同参数")
        self.call_history.append(key)

    def execute_with_retry(self, tool_call_fn, tool_name, args):
        """带重试的工具调用"""
        self.step_count += 1
        for attempt in range(self.max_retries + 1):
            try:
                result = asyncio.wait_for(
                    tool_call_fn(tool_name, args),
                    timeout=self.step_timeout
                )
                return result
            except TimeoutError:
                if attempt == self.max_retries:
                    return {"error": f"{tool_name} 超时 ({self.step_timeout}s)，已重试 {self.max_retries} 次"}
            except ConnectionError:
                if attempt == self.max_retries:
                    return {"error": f"{tool_name} 服务不可用，已跳过"}
```

**降级策略：**
- MCP Server 连接失败 → 返回错误信息给 Agent，Agent 自行决定跳过或用其他方式
- LLM API 调用失败 → 重试 2 次，仍失败则暂停该告警分析，标记为 `analysis_failed`
- 所有异常均记录审计日志

**验收脚本：**

```bash
# B4-T1: 超过 max_steps 自动终止
python -m pytest tests/test_guard.py::test_max_steps_exceeded -v
# 模拟: Agent 循环超过 20 步
# 期望: 抛出 MaxStepsExceeded，Agent 输出当前已有的部分结论

# B4-T2: 卡死检测
python -m pytest tests/test_guard.py::test_stuck_detection -v
# 模拟: Agent 连续 3 次调用 search_alerts(ip="10.0.0.5")
# 期望: 抛出 AgentStuck，终止循环

# B4-T3: 工具调用失败重试
python -m pytest tests/test_guard.py::test_tool_retry -v
# 模拟: log-search MCP Server 第1次超时，第2次成功
# 期望: 重试后成功返回结果，审计日志记录重试次数

# B4-T4: MCP Server 不可用降级
python -m pytest tests/test_guard.py::test_mcp_fallback -v
# 模拟: rule-engine MCP Server 完全宕机
# 期望: 返回错误信息给 Agent，Agent 跳过规则匹配继续分析

# B4-T5: 总超时控制
python -m pytest tests/test_guard.py::test_total_timeout -v
# 模拟: 分析流程超过 300s
# 期望: 强制终止，输出部分结论，标记状态为 timeout
```

---

### 模块 B5：Audit 审计与可观测性 (`agent/audit.py`)

记录 Agent 的所有行为，支持事后审计和前端可视化。

**审计日志结构：**

```json
{
  "trace_id": "uuid-v4",
  "alert_id": "关联的告警ID",
  "timestamp": "2026-03-08T10:30:00Z",
  "event_type": "tool_call | tool_result | plan_generated | plan_adjusted | decision_made | error | approval_requested | approval_result",
  "data": {
    "tool_name": "search_alerts",
    "tool_args": { "ip": "10.0.0.5", "hours": 24 },
    "tool_result_summary": "找到 15 条相关告警",
    "duration_ms": 230,
    "step_number": 2,
    "plan_step_id": 1
  },
  "token_usage": {
    "input_tokens": 1500,
    "output_tokens": 350
  }
}
```

**审计日志存储：** `audit_logs` 表（SQLite），字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增ID |
| `trace_id` | TEXT | 整次分析的追踪ID（一次 agent_loop = 一个 trace_id） |
| `alert_id` | TEXT | 关联的告警ID |
| `event_type` | TEXT | 事件类型 |
| `data` | TEXT (JSON) | 事件详情 |
| `token_usage` | TEXT (JSON) | 本次 LLM 调用的 token 用量 |
| `created_at` | DATETIME | 时间戳 |

**决策溯源：**
每个 `decisions` 表记录增加 `evidence` 字段（JSON），记录 Agent 做出该决策时参考了哪些信息：

```json
{
  "evidence": {
    "logs_queried": ["alert-001", "alert-002", "alert-003"],
    "rules_matched": ["rule-sql-injection-chain"],
    "mitre_techniques": ["T0890", "T0807"],
    "memories_recalled": ["mem-2026-03-01-sqli-similar"],
    "plan_steps_executed": 4,
    "total_tool_calls": 6,
    "reasoning_chain": "该IP在24h内触发了端口扫描+SQL注入+命令注入，符合典型的侦察→渗透→执行攻击链..."
  }
}
```

**验收脚本：**

```bash
# B5-T1: 工具调用产生审计日志
python -m pytest tests/test_audit.py::test_tool_call_logged -v
# 期望: Agent 每次调用 MCP 工具后，audit_logs 表新增一条 event_type=tool_call 记录

# B5-T2: 完整 trace 可追溯
python -m pytest tests/test_audit.py::test_full_trace -v
# 期望: 一次完整分析结束后，按 trace_id 查询可获取所有步骤的审计记录
# 包括 plan_generated, tool_call, tool_result, decision_made

# B5-T3: token 用量统计
python -m pytest tests/test_audit.py::test_token_tracking -v
# 期望: 每次 LLM 调用记录 input_tokens + output_tokens
# 分析结束后可按 trace_id 汇总总 token 消耗

# B5-T4: 决策溯源 evidence 完整性
python -m pytest tests/test_audit.py::test_decision_evidence -v
# 期望: decisions 表的 evidence JSON 包含 logs_queried, rules_matched,
# mitre_techniques, reasoning_chain 字段

# B5-T5: 审计日志 API 查询
curl http://localhost:3000/api/audit?trace_id=xxx
# 期望: 返回该 trace 的所有审计事件，按时间排序

# B5-T6: 前端推理链展示
# 期望: AIChat.vue 中展示 Agent 的推理过程（哪些工具被调用、每步结论）
# 手动验收: 打开前端 → 触发分析 → 查看推理链是否完整展示
```

---

### 模块 B6：Memory 记忆模块 (`agent/memory.py` + `mcp-servers/memory/`)

基于 [Mem0](https://github.com/mem0ai/mem0)（GitHub 41k+ stars，Apache 2.0）实现 Agent 长期记忆。

**为什么需要记忆：**
- Agent 每次分析都是独立会话，无法记住"上周也出现过类似的 SQL 注入攻击"
- 有了记忆后，Agent 可以检索历史相似案例，做出更准确的判断
- 例如：某 IP 历史上多次触发告警 → Agent 可以判断为持续性威胁而非误报

**记忆类型：**

| 类型 | 内容 | 示例 |
|------|------|------|
| **分析经验** | 历史告警的分析结论和处置结果 | "10.0.0.5 的 SQL 注入告警经确认为真实攻击，已阻断" |
| **误报记录** | 被标记为误报的告警模式 | "Wazuh 规则 5501 对 192.168.1.0/24 频繁误报" |
| **攻击模式** | 已识别的攻击链和战术 | "该攻击者惯用 T0866(端口扫描) → T0807(命令注入) 路径" |
| **资产上下文** | 资产的历史安全状态 | "192.168.1.100 是 SCADA 主站，重要度 5，历史无告警" |

**作为 MCP Server 暴露：** 记忆模块封装为独立 MCP Server，Agent 通过标准 MCP 工具调用。

**Mem0 工作原理：**
```
存储记忆 (memorize):
  Agent 分析结论文本 → Mem0 LLM 自动提取关键事实 → 向量化 → 存入 Qdrant

检索记忆 (recall):
  当前告警描述 → 向量化 → Qdrant 语义相似度搜索 → 返回相关历史经验

底层存储:
  Qdrant (向量数据库，可内嵌运行，无需外部服务)
```

**验收脚本：**

```bash
# B6-T1: 存储记忆
python -m pytest tests/test_memory.py::test_memorize -v
# 输入: "10.0.0.5 的 SQL 注入告警经确认为真实攻击，已执行阻断"
# 期望: Mem0 成功存储，返回 memory_id

# B6-T2: 检索相似记忆
python -m pytest tests/test_memory.py::test_recall -v
# 输入: "发现来自 10.0.0.5 的新 SQL 注入告警"
# 期望: 返回之前存储的相关记忆，相似度 > 0.7

# B6-T3: MCP Server 工具可发现
python -m pytest tests/test_memory.py::test_mcp_tool_discovery -v
# 期望: MCP Client list_tools() 返回 recall, memorize, list_memories

# B6-T4: Agent 集成测试 — 记忆影响决策
python -m pytest tests/test_memory.py::test_memory_influences_decision -v
# 模拟: 先存储 "10.0.0.5 是已知攻击源" 的记忆
# 然后 Agent 分析新的 10.0.0.5 告警
# 期望: Agent 在推理中引用了记忆内容，决策置信度更高
```

---

### 模块 A：数据收集 + 聚簇 (`collector/`)

**日志聚簇机制：**

```
原始日志流（10000条相同SQL注入告警）:
  [SQLi from 10.0.0.5] × 10000

         ↓ clusterer.py

聚簇后（1条 + 计数）:
  {
    "signature": "hash(normalized_fields)",  // 聚簇键：去掉时间戳等变量字段后的哈希
    "sample": { ... },                       // 一条完整的样本日志
    "count": 10000,                          // 出现次数
    "first_seen": "2026-03-08T10:00:00Z",
    "last_seen": "2026-03-08T10:35:00Z",
    "severity": "error",
    "source_ips": ["10.0.0.5"],              // 去重后的源IP列表
    "target_ips": ["192.168.1.100"]          // 去重后的目标IP列表
  }

         ↓ severity_filter

error/critical → 进入 Agent 分析
warning/info   → 仅写入数据库
```

**验收脚本：**

```bash
# A-T1: 日志规范化
python -m pytest tests/test_collector.py::test_normalize_waf -v
python -m pytest tests/test_collector.py::test_normalize_nids -v
python -m pytest tests/test_collector.py::test_normalize_hids -v
# 期望: 各数据源的原始日志被转换为统一格式

# A-T2: 聚簇去重
python -m pytest tests/test_collector.py::test_cluster_same_alerts -v
# 输入: 100条相同的 SQL 注入告警
# 期望: 聚簇为 1 条，count=100，保留 first_seen/last_seen

# A-T3: 不同告警不聚簇
python -m pytest tests/test_collector.py::test_cluster_different_alerts -v
# 输入: 3条不同类型的告警
# 期望: 保持 3 条独立记录

# A-T4: 分级过滤
python -m pytest tests/test_collector.py::test_severity_filter -v
# 输入: error + warning + info 各一条
# 期望: 只有 error 进入 Redis Streams 的 agent 队列

# A-T5: Redis Streams 推送
python -m pytest tests/test_collector.py::test_redis_publish -v
# 期望: 聚簇后的告警成功写入 Redis Streams
```

---

### 模块 C：MCP Server 微服务 (`mcp-servers/`)

每个 MCP Server 是一个独立的进程/容器。本地开发用 stdio 通信，生产部署用 Streamable HTTP：

```
┌─────────────┐     MCP Protocol      ┌──────────────────┐
│             │ ◄──────────────────── │  log-search       │ :5001
│             │     MCP Protocol      ├──────────────────┤
│  Agent      │ ◄──────────────────── │  rule-engine      │ :5002
│  (MCP Client│     MCP Protocol      ├──────────────────┤
│  官方 mcp   │ ◄──────────────────── │  mitre-kb         │ :5003
│   SDK)      │     MCP Protocol      ├──────────────────┤
│             │ ◄──────────────────── │  action-executor  │ :5004
│             │     MCP Protocol      ├──────────────────┤
│             │ ◄──────────────────── │  notifier         │ :5005
│             │     MCP Protocol      ├──────────────────┤
│             │ ◄──────────────────── │  memory (Mem0)    │ :5006
└─────────────┘                       └──────────────────┘
```

**验收脚本（每个 MCP Server 独立验收）：**

```bash
# C-T1: log-search MCP Server
python -m pytest tests/test_mcp_log_search.py -v
# 测试: search_alerts, search_raw_events, get_alert_context 三个工具
# 期望: 通过 MCP 协议调用，返回正确查询结果

# C-T2: rule-engine MCP Server
python -m pytest tests/test_mcp_rule_engine.py -v
# 测试: match_rules, get_rules
# 期望: 输入告警集 → 返回匹配的关联规则

# C-T3: mitre-kb MCP Server
python -m pytest tests/test_mcp_mitre_kb.py -v
# 测试: lookup_technique, lookup_tactic, map_alert_to_mitre
# 期望: 返回正确的 ATT&CK for ICS 映射

# C-T4: action-executor MCP Server
python -m pytest tests/test_mcp_action_executor.py -v
# 测试: block_ip, isolate_host, add_watch
# 注意: 测试环境使用 mock，不实际执行阻断
# 期望: 返回执行结果（成功/失败），记录审计日志

# C-T5: notifier MCP Server
python -m pytest tests/test_mcp_notifier.py -v
# 测试: send_webhook, send_email, push_websocket
# 期望: 成功发送通知（测试环境用 mock endpoint）

# C-T6: memory MCP Server
# (见模块 B6 验收脚本)

# C-T7: MCP Server 健康检查
python -m pytest tests/test_mcp_health.py -v
# 期望: 所有 MCP Server 的 /health 端点返回 200

# C-T8: MCP 工具发现
python -m pytest tests/test_mcp_discovery.py -v
# 期望: MCP Client list_tools() 返回所有 16 个工具
```

---

### 模块 D：API 服务层 (`backend/`)

**新增 API：**

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/approval` | GET | 查询待审批列表（支持 status 筛选） |
| `/api/approval/:id` | PATCH | 审批操作（approve / reject） |
| `/api/audit` | GET | 查询审计日志（支持 trace_id, alert_id 筛选） |
| `/api/audit/stats` | GET | token 用量统计（按天/按分析任务） |

**验收脚本：**

```bash
# D-T1: 审批 API
curl -X GET http://localhost:3000/api/approval?status=pending
# 期望: 返回待审批列表

curl -X PATCH http://localhost:3000/api/approval/1 -d '{"status":"approved"}'
# 期望: 更新审批状态，触发 Agent 继续执行

# D-T2: 审计日志 API
curl http://localhost:3000/api/audit?trace_id=xxx
# 期望: 返回该 trace 的完整审计链

curl http://localhost:3000/api/audit/stats?days=7
# 期望: 返回最近7天的 token 用量统计
```

---

### 模块 E：前端 (`frontend/`)

**新增页面：**

| 页面 | 功能 |
|------|------|
| `ApprovalQueue.vue` | 展示待审批的高危操作，支持一键批准/拒绝 |
| `AuditLog.vue` | 展示 Agent 审计日志，按 trace 展开推理链 |

**AIChat.vue 增强：** 展示 Agent 推理过程（计划 → 工具调用 → 中间结论 → 最终决策）。

**验收标准（手动）：**

```
# E-T1: ApprovalQueue 页面
1. 打开 /approval 页面
2. 触发一次含 block_ip 的分析
3. 页面实时显示待审批项（WebSocket 推送）
4. 点击"批准"后，Agent 继续执行

# E-T2: AuditLog 页面
1. 打开 /audit 页面
2. 选择一个历史分析 trace
3. 展开显示完整推理链：计划 → 各步骤工具调用和结果 → 最终决策

# E-T3: AIChat 推理过程展示
1. 打开 AI 对话面板
2. 触发分析
3. 实时展示 Agent 正在执行的步骤（"正在查询历史告警..."、"匹配到 2 条规则..."）
```

---

## Agent 核心架构

### 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| **AI 引擎** | `anthropic` Python SDK | Agent 主循环，直接调用 Claude API，支持 tool_use |
| **MCP 客户端** | `mcp` Python SDK (官方) | 连接各 MCP Server，管理多 Server 会话 |
| **MCP 服务端** | `mcp` Python SDK (FastMCP) | 每个工具用 `@mcp.tool()` 装饰器暴露 |
| **Agent 记忆** | Mem0 (mem0ai) | 长期记忆存储与语义检索，自动提取关键事实 |
| **消息队列** | Redis Streams | 收集层与 Agent 层解耦 |
| **存储** | SQLite | 告警、攻击链、决策、审计日志持久化 |

### Agent Loop 完整伪代码

```python
import anthropic
from mcp_client import MCPClient
from guard import AgentGuard
from policy import ToolPolicy
from audit import AuditLogger
from hooks import HookManager

client = anthropic.Anthropic()
mcp = MCPClient()
guard = AgentGuard(config)
policy = ToolPolicy("tool_policy.yaml")
audit = AuditLogger(db)
hooks = HookManager("hooks.yaml")

def agent_loop(clustered_alerts):
    """完整 Agent 循环: Planning → Execution → Conclusion"""
    trace_id = uuid4()
    tools = mcp.list_tools()

    # --- Hook: on_alert_received ---
    hooks.trigger("on_alert_received", clustered_alerts)

    # --- Phase 1: Planning ---
    plan_prompt = format_planning_prompt(clustered_alerts)
    messages = [{"role": "user", "content": plan_prompt}]

    plan_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        system=PLANNING_SYSTEM_PROMPT,
        messages=messages,
        tools=tools,  # Agent 在规划阶段也可调用 recall 检索历史经验
        max_tokens=4096
    )
    # planning 阶段也走 ReAct 循环（Agent 可能先 recall 记忆再制定计划）
    # ...省略循环细节，和执行阶段结构相同...

    plan = parse_plan(plan_response)
    audit.log(trace_id, "plan_generated", plan)
    hooks.trigger("on_plan_generated", plan)

    # --- Phase 2: Execution (ReAct Loop) ---
    messages = [{"role": "user", "content": format_execution_prompt(clustered_alerts, plan)}]
    guard.reset()

    while True:
        guard.check_before_step()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            system=EXECUTION_SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
            max_tokens=4096
        )
        audit.log(trace_id, "llm_call", {
            "token_usage": response.usage
        })

        messages.append({"role": "assistant", "content": response.content})
        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            break  # Agent 分析完毕

        tool_results = []
        for tc in tool_calls:
            # --- 权限检查 ---
            level = policy.get_level(tc.name)

            if level == "approve":
                # 高危操作 → 写入 approval_queue → 轮询等待人工审批
                hooks.trigger("on_approval_needed", tc)
                approval_id = db.insert_approval(tc, trace_id)
                approval = await poll_approval(approval_id, timeout=policy.approval_timeout)
                # poll_approval: 每秒查询 approval_queue 表状态，直到 approved/rejected/超时
                audit.log(trace_id, "approval_result", approval)
                if approval["status"] == "rejected":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": f"操作被拒绝: {approval.get('reason', '操作员拒绝')}"
                    })
                    continue

            # --- 卡死检测 ---
            guard.check_stuck(tc.name, tc.input)

            # --- 执行工具（带重试） ---
            hooks.trigger("on_tool_called", tc)
            result = guard.execute_with_retry(mcp.call_tool, tc.name, tc.input)
            hooks.trigger("on_tool_result", tc, result)

            audit.log(trace_id, "tool_call", {
                "tool": tc.name, "args": tc.input,
                "result_summary": summarize(result),
                "duration_ms": elapsed
            })

            if level == "notify":
                hooks.trigger("on_decision_made", {
                    "action": tc.name, "args": tc.input
                })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result
            })

        messages.append({"role": "user", "content": tool_results})

    # --- Phase 3: Conclusion ---
    decision = parse_decision(response)
    audit.log(trace_id, "decision_made", decision)
    hooks.trigger("on_decision_made", decision)
    hooks.trigger("on_loop_finished", {
        "trace_id": trace_id,
        "steps": guard.step_count,
        "total_tokens": audit.get_total_tokens(trace_id)
    })

    return decision
```

---

## 模块职责汇总

| 模块 | 职责 | 技术选型 |
|------|------|----------|
| **collector (A)** | 多源日志采集、字段标准化、聚簇去重、推送消息队列 | Python + Redis Streams |
| **agent (B)** | Agent 主循环 + Planning + 权限 + 守卫 + 审计 + 钩子 + 记忆 | Python + `anthropic` SDK + `mcp` SDK |
| **mcp-servers (C)** | 工具微服务：日志查询、规则匹配、知识库、处置执行、通知、记忆 | Python (每个独立微服务) |
| **backend (D)** | REST API、数据持久化、审批流、审计查询、前后端桥接 | Node.js + Express + SQLite |
| **frontend (E)** | 指挥面板、告警列表、攻击链可视化、AI对话、审批队列、审计日志 | Vue3 |

## 核心数据表

| 表 | 作用 |
|----|------|
| `assets` | 资产信息（IP、主机名、类型、重要度） |
| `raw_events` | 原始事件（保留多源原始JSON） |
| `alerts` | 聚簇后告警（统一格式 + 出现次数 + 时间窗口 + MITRE映射 + 状态） |
| `attack_chains` | 攻击链（Agent推断的阶段、置信度、证据） |
| `decisions` | 处置建议（Agent建议 + evidence 溯源 + 人工反馈） |
| `approval_queue` | 高危操作审批队列（pending / approved / rejected） |
| `audit_logs` | 审计日志（trace_id + 工具调用 + token 用量 + 推理链） |

## MCP 工具清单

| MCP Server | 工具名 | 功能 | 权限等级 |
|------------|--------|------|---------|
| **log-search** | `search_alerts` | 按条件查询历史告警 | auto |
| | `search_raw_events` | 查询原始日志 | auto |
| | `get_alert_context` | 获取某告警的上下文 | auto |
| **rule-engine** | `match_rules` | 对告警执行关联规则匹配 | auto |
| | `get_rules` | 查询当前规则库 | auto |
| **mitre-kb** | `lookup_technique` | 查询 ATT&CK for ICS 技术详情 | auto |
| | `lookup_tactic` | 查询战术阶段 | auto |
| | `map_alert_to_mitre` | 将告警特征映射到 ATT&CK 技术 | auto |
| **action-executor** | `block_ip` | 下发防火墙规则阻断 IP | **approve** |
| | `isolate_host` | 网络隔离主机 | **approve** |
| | `add_watch` | 添加监控/告警规则 | notify |
| **notifier** | `send_webhook` | 发送企微/钉钉/飞书通知 | notify |
| | `send_email` | 发送邮件告警 | notify |
| | `push_websocket` | WebSocket 实时推送到前端 | notify |
| **memory** | `recall` | 语义检索历史相似案例和经验 | auto |
| | `memorize` | 存储本次分析结论到长期记忆 | auto |
| | `list_memories` | 列出所有记忆 | auto |

---

## 测试规范

每个模块交付时必须同步交付测试，测试与代码放在同一次提交中。

### 目录结构

```
ics-defense/
├── tests/
│   ├── conftest.py                  # pytest 公共 fixtures（mock LLM、mock MCP、测试DB）
│   ├── test_collector.py            # 模块 A 测试（规范化、聚簇、分级、Redis推送）
│   ├── test_planner.py              # 模块 B1 测试（计划生成、动态调整、攻击链规划）
│   ├── test_policy.py               # 模块 B2 测试（权限分级、审批流、超时）
│   ├── test_hooks.py                # 模块 B3 测试（钩子触发、条件判断、热加载）
│   ├── test_guard.py                # 模块 B4 测试（max_steps、卡死、重试、超时）
│   ├── test_audit.py                # 模块 B5 测试（日志记录、trace、token统计）
│   ├── test_memory.py               # 模块 B6 测试（存储、检索、MCP暴露）
│   ├── test_agent.py                # 模块 B 集成测试（完整 agent_loop 端到端）
│   ├── test_mcp_log_search.py       # MCP Server 单元测试
│   ├── test_mcp_rule_engine.py
│   ├── test_mcp_mitre_kb.py
│   ├── test_mcp_action_executor.py
│   ├── test_mcp_notifier.py
│   ├── test_mcp_memory.py
│   ├── test_mcp_discovery.py        # MCP 工具发现测试
│   └── test_mcp_health.py           # MCP 健康检查测试
├── pytest.ini                       # pytest 配置
└── requirements-dev.txt             # 测试依赖（pytest, pytest-asyncio, respx 等）
```

### 测试原则

| 原则 | 说明 |
|------|------|
| **LLM 调用必须 mock** | 测试不能真正调用 Claude API，用 `respx` 或 `unittest.mock` 模拟 |
| **MCP Server 测试用 stdio** | 每个 MCP Server 的测试直接启动 stdio 进程，不需要 Docker |
| **数据库用内存 SQLite** | `conftest.py` 提供 `:memory:` 的测试数据库 fixture |
| **每个验收脚本对应一个 test 函数** | 架构文档中的 B1-T1 ~ E-T3 全部有对应的 pytest 用例 |
| **测试覆盖率 > 80%** | 核心模块（agent, guard, policy）要求 > 90% |

### conftest.py 公共 Fixtures

```python
# tests/conftest.py
import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def test_db():
    """内存 SQLite 测试数据库，自动建表"""
    conn = sqlite3.connect(":memory:")
    # 执行 db.js 中相同的建表 SQL
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()

@pytest.fixture
def mock_llm():
    """模拟 Claude API 响应"""
    client = MagicMock()
    # 默认返回一个不调用工具的文本响应
    client.messages.create.return_value = mock_text_response("分析完毕")
    return client

@pytest.fixture
def mock_mcp():
    """模拟 MCP Client，所有工具返回预设结果"""
    mcp = AsyncMock()
    mcp.list_tools.return_value = MOCK_TOOL_DEFINITIONS
    mcp.call_tool.return_value = '{"results": []}'
    return mcp

@pytest.fixture
def sample_alerts():
    """测试用聚簇告警样本"""
    return [
        {
            "signature": "abc123",
            "sample": {"title": "SQL注入攻击", "src_ip": "10.0.0.5", "dst_ip": "192.168.1.100"},
            "count": 150,
            "severity": "error",
            "first_seen": "2026-03-08T10:00:00Z",
            "last_seen": "2026-03-08T10:35:00Z"
        }
    ]
```

---

## Python ↔ Node.js 桥接

现有 backend 是 Node.js (Express)，新增的 Agent 和 MCP Servers 是 Python。两者通过 HTTP API 通信：

```
┌──────────────────┐       HTTP        ┌──────────────────┐
│  frontend (Vue3) │ ◄──────────────── │  backend (Express)│
│                  │                   │  :3002            │
└──────────────────┘                   └────────┬─────────┘
                                                │ HTTP
                                                ▼
                                       ┌──────────────────┐
                                       │  Agent Service   │
                                       │  (Python/FastAPI) │
                                       │  :8000            │
                                       │                  │
                                       │  POST /analyze   │
                                       │  POST /chat      │
                                       │  GET  /status    │
                                       └────────┬─────────┘
                                                │ MCP (stdio)
                                       ┌────────┼────────┐
                                       ▼        ▼        ▼
                                    MCP Servers (各独立进程)
```

**Agent Service** 是一个轻量 FastAPI 服务，作为 Express backend 和 Python Agent 之间的桥梁：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/analyze` | POST | 接收告警ID列表，启动 agent_loop，返回 trace_id |
| `/analyze/{trace_id}` | GET | 查询分析进度和结果 |
| `/chat` | POST | AI 对话（直接调用 Claude） |
| `/status` | GET | Agent 服务健康检查 |
| `/approval/{id}/respond` | POST | 接收审批结果，唤醒等待中的 Agent |

Express backend 调用示例：
```javascript
// backend/src/routes/analysis.js
const response = await fetch('http://localhost:8000/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ alert_ids: [1, 2, 3] })
});
const { trace_id } = await response.json();
```

---

## Python 依赖

```
# requirements.txt
anthropic>=0.50.0          # Claude SDK
mcp>=1.20.0                # MCP 客户端 + 服务端 (FastMCP)
mem0ai>=0.1.0              # Agent 记忆
redis>=5.0.0               # Redis Streams 消费者
fastapi>=0.110.0           # Agent Service HTTP API
uvicorn>=0.30.0            # ASGI 服务器
pyyaml>=6.0                # hooks.yaml / tool_policy.yaml 配置

# requirements-dev.txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0              # mock HTTP 请求（Claude API）
httpx>=0.27.0              # 测试 FastAPI
```

---

## 实施计划（sub-agent 并行分工）

### 第 1 轮：全部基础模块（9 个 sub-agent 并行）

所有模块互不依赖，可完全并行。每个 sub-agent 交付代码 + 测试。

| SA# | 模块 | 交付物 | 文件数 |
|-----|------|--------|--------|
| 1 | Guard + Policy | `agent/guard.py` + `agent/policy.py` + `agent/tool_policy.yaml` + `tests/test_guard.py` + `tests/test_policy.py` | 5 |
| 2 | Hooks + Audit | `agent/hooks.py` + `agent/audit.py` + `agent/hooks.yaml` + `tests/test_hooks.py` + `tests/test_audit.py` | 5 |
| 3 | Planner + Memory + Prompts | `agent/planner.py` + `agent/memory.py` + `agent/prompts/*.txt` + `tests/test_planner.py` + `tests/test_memory.py` | 6 |
| 4 | Collector | `collector/normalizer.py` + `collector/clusterer.py` + `collector/severity_filter.py` + `collector/producer.py` + `tests/test_collector.py` | 5 |
| 5 | MCP: log-search + rule-engine | `mcp-servers/log-search/server.py` + `mcp-servers/rule-engine/server.py` + 测试 | 4 |
| 6 | MCP: mitre-kb + action-executor | `mcp-servers/mitre-kb/server.py` + `mcp-servers/action-executor/server.py` + 测试 | 4 |
| 7 | MCP: notifier + memory | `mcp-servers/notifier/server.py` + `mcp-servers/memory/server.py` + 测试 | 4 |
| 8 | MCP Client + 项目基础设施 | `agent/mcp_client.py` + `conftest.py` + `pytest.ini` + `requirements.txt` + `requirements-dev.txt` | 5 |
| 9 | Backend 更新 | `backend/src/routes/approval.js` + `backend/src/routes/audit.js` + `backend/src/models/db.js`(更新schema) | 3 |

### 第 2 轮：集成 + 前端（3 个 sub-agent 并行）

依赖第 1 轮全部完成。

| SA# | 模块 | 交付物 | 文件数 |
|-----|------|--------|--------|
| 10 | Agent 主循环 + Service | `agent/agent.py` + `agent/service.py` (FastAPI) + `tests/test_agent.py` | 3 |
| 11 | Frontend | `frontend/` Vue3 项目初始化 + 所有页面 | ~10 |
| 12 | Docker + 集成测试 | `docker-compose.yml` + `tests/test_mcp_discovery.py` + `tests/test_mcp_health.py` | 3 |
