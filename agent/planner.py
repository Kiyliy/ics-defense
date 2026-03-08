import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PlanStep:
    id: int
    action: str           # 描述要做什么
    tool: Optional[str]   # 要调用的 MCP 工具名，null 表示纯推理步骤
    status: str = "pending"  # pending | running | completed | skipped
    result_summary: str = ""


@dataclass
class AnalysisPlan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    estimated_risk: str = "unknown"  # low | medium | high | critical
    adjustments: list[dict] = field(default_factory=list)  # 记录计划调整历史

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_llm_response(cls, response_text: str) -> 'AnalysisPlan':
        """从 Claude 的 JSON 响应解析出计划
        期望格式:
        {
            "goal": "...",
            "steps": [{"id": 1, "action": "...", "tool": "search_alerts"}, ...],
            "estimated_risk": "high"
        }
        容错：如果解析失败，返回一个默认计划（单步：直接分析）
        """
        try:
            data = json.loads(response_text)
            goal = data.get("goal", "分析告警")
            estimated_risk = data.get("estimated_risk", "unknown")
            steps = []
            for s in data.get("steps", []):
                steps.append(PlanStep(
                    id=s.get("id", len(steps) + 1),
                    action=s.get("action", ""),
                    tool=s.get("tool"),
                    status=s.get("status", "pending"),
                    result_summary=s.get("result_summary", ""),
                ))
            if not steps:
                steps = [PlanStep(id=1, action="直接分析告警并给出结论", tool=None)]
            return cls(goal=goal, steps=steps, estimated_risk=estimated_risk)
        except (json.JSONDecodeError, TypeError, KeyError):
            return cls(
                goal="分析告警",
                steps=[PlanStep(id=1, action="直接分析告警并给出结论", tool=None)],
                estimated_risk="unknown",
            )

    def mark_step(self, step_id: int, status: str, result_summary: str = ""):
        """更新某步骤的状态"""
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                if result_summary:
                    step.result_summary = result_summary
                return
        raise ValueError(f"Step {step_id} not found")

    def insert_step(self, after_step_id: int, action: str, tool: str = None):
        """在指定步骤后插入新步骤（动态调整）
        记录调整历史到 self.adjustments
        """
        insert_index = None
        for i, step in enumerate(self.steps):
            if step.id == after_step_id:
                insert_index = i + 1
                break
        if insert_index is None:
            raise ValueError(f"Step {after_step_id} not found")

        # 计算新 ID：取当前最大 ID + 1
        max_id = max(s.id for s in self.steps) if self.steps else 0
        new_step = PlanStep(id=max_id + 1, action=action, tool=tool)
        self.steps.insert(insert_index, new_step)

        self.adjustments.append({
            "type": "insert",
            "after_step_id": after_step_id,
            "new_step_id": new_step.id,
            "action": action,
            "tool": tool,
        })

    def skip_step(self, step_id: int, reason: str):
        """跳过某步骤"""
        for step in self.steps:
            if step.id == step_id:
                step.status = "skipped"
                step.result_summary = reason
                self.adjustments.append({
                    "type": "skip",
                    "step_id": step_id,
                    "reason": reason,
                })
                return
        raise ValueError(f"Step {step_id} not found")

    def get_next_pending(self) -> Optional[PlanStep]:
        """获取下一个待执行的步骤"""
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    def is_complete(self) -> bool:
        """所有步骤都完成/跳过"""
        return all(s.status in ("completed", "skipped") for s in self.steps)

    def get_progress_summary(self) -> str:
        """返回当前进度的文本摘要（给 Claude 看的）"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == "completed")
        skipped = sum(1 for s in self.steps if s.status == "skipped")
        pending = sum(1 for s in self.steps if s.status == "pending")
        running = sum(1 for s in self.steps if s.status == "running")

        lines = [f"计划目标: {self.goal}"]
        lines.append(f"预估风险: {self.estimated_risk}")
        lines.append(f"进度: {completed + skipped}/{total} (完成={completed}, 跳过={skipped}, 待执行={pending}, 执行中={running})")
        lines.append("")
        for step in self.steps:
            status_icon = {
                "pending": "[ ]",
                "running": "[>]",
                "completed": "[x]",
                "skipped": "[-]",
            }.get(step.status, "[?]")
            tool_info = f" (工具: {step.tool})" if step.tool else ""
            line = f"  {status_icon} 步骤{step.id}: {step.action}{tool_info}"
            if step.result_summary:
                line += f" -> {step.result_summary}"
            lines.append(line)

        if self.adjustments:
            lines.append("")
            lines.append(f"计划已调整 {len(self.adjustments)} 次")

        return "\n".join(lines)


def format_planning_prompt(clustered_alerts: list, memories: list = None) -> str:
    """生成规划阶段的 user prompt
    包含：告警数据 + 历史记忆（如果有）
    要求 Claude 输出 JSON 格式的分析计划
    """
    alerts_json = json.dumps(clustered_alerts, ensure_ascii=False, indent=2)

    parts = []
    parts.append("以下是需要分析的聚簇告警：")
    parts.append("")
    parts.append(alerts_json)
    parts.append("")

    if memories:
        parts.append("以下是相关的历史分析记忆：")
        parts.append("")
        for mem in memories:
            content = mem.get("content", "")
            score = mem.get("score", "N/A")
            parts.append(f"- [相关度: {score}] {content}")
        parts.append("")

    parts.append("请根据以上信息，制定一个分析计划。以 JSON 格式输出：")
    parts.append(json.dumps({
        "goal": "用一句话描述分析目标",
        "steps": [
            {"id": 1, "action": "具体要做什么", "tool": "要用的工具名或null"}
        ],
        "estimated_risk": "low|medium|high|critical"
    }, ensure_ascii=False, indent=2))

    return "\n".join(parts)


def format_execution_prompt(clustered_alerts: list, plan: AnalysisPlan) -> str:
    """生成执行阶段的 user prompt
    包含：告警数据 + 分析计划 + 当前进度
    """
    alerts_json = json.dumps(clustered_alerts, ensure_ascii=False, indent=2)

    parts = []
    parts.append("以下是需要分析的聚簇告警：")
    parts.append("")
    parts.append(alerts_json)
    parts.append("")
    parts.append("当前分析计划及进度：")
    parts.append("")
    parts.append(plan.get_progress_summary())
    parts.append("")

    next_step = plan.get_next_pending()
    if next_step:
        parts.append(f"请执行下一步: 步骤{next_step.id} - {next_step.action}")
        if next_step.tool:
            parts.append(f"建议使用工具: {next_step.tool}")
    else:
        parts.append("所有步骤已完成，请给出最终分析结论。")

    return "\n".join(parts)
