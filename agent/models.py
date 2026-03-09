"""
Pydantic models for all ICS Defense database tables.

These models serve as the canonical Python type definitions for rows stored
in SQLite.  They are used for validation, serialization, and documentation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC-agnostic timestamp in ISO 8601 format."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Table models
# ---------------------------------------------------------------------------

class AssetModel(BaseModel):
    """Row in the ``assets`` table."""

    id: Optional[int] = None
    ip: str
    hostname: Optional[str] = None
    type: str = Field(default="host", description="host / network_device / server")
    importance: int = Field(default=3, ge=1, le=5, description="1-5, 5 = most important")
    created_at: str = Field(default_factory=_now_iso)


class RawEventModel(BaseModel):
    """Row in the ``raw_events`` table."""

    id: Optional[int] = None
    source: str = Field(..., description="waf / nids / hids / pikachu / soc")
    raw_json: str = Field(..., description="Original JSON payload as string")
    received_at: str = Field(default_factory=_now_iso)


class AlertModel(BaseModel):
    """Row in the ``alerts`` table."""

    id: Optional[int] = None
    source: str
    severity: str = Field(default="medium", description="low / medium / high / critical")
    title: str
    description: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    raw_json: Optional[str] = Field(default=None, description="Original raw event JSON")
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    asset_id: Optional[int] = None
    status: str = Field(default="open", description="open / analyzing / analyzed / resolved")
    raw_event_id: Optional[int] = None
    event_count: int = Field(default=1, description="Number of raw events in this cluster")
    cluster_signature: Optional[str] = Field(default=None, description="Cluster dedup signature")
    cluster_count: int = Field(default=1, description="Number of events in this cluster")
    created_at: str = Field(default_factory=_now_iso)
    updated_at: Optional[str] = Field(default_factory=_now_iso)


class AttackChainModel(BaseModel):
    """Row in the ``attack_chains`` table."""

    id: Optional[int] = None
    name: Optional[str] = None
    stage: Optional[str] = Field(
        default=None,
        description="reconnaissance / initial_access / execution / ...",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alert_ids: Optional[str] = Field(default=None, description="JSON array of alert IDs")
    evidence: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


class DecisionModel(BaseModel):
    """Row in the ``decisions`` table."""

    id: Optional[int] = None
    attack_chain_id: Optional[int] = None
    risk_level: str = Field(default="medium", description="low / medium / high / critical")
    recommendation: str
    action_type: Optional[str] = Field(
        default=None,
        description="block / isolate / monitor / investigate",
    )
    rationale: Optional[str] = None
    status: str = Field(default="pending", description="pending / accepted / rejected")
    created_at: str = Field(default_factory=_now_iso)


class ApprovalModel(BaseModel):
    """Row in the ``approval_queue`` table."""

    id: Optional[int] = None
    trace_id: str
    tool_name: str
    tool_args: Optional[str] = None
    reason: Optional[str] = None
    status: str = Field(default="pending", description="pending / approved / rejected")
    responded_at: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


class AuditLogModel(BaseModel):
    """Row in the ``audit_logs`` table."""

    id: Optional[int] = None
    trace_id: str
    alert_id: Optional[str] = None
    event_type: str
    data: Optional[Any] = Field(default=None, description="JSON-serializable dict")
    token_usage: Optional[Any] = Field(default=None, description="JSON-serializable dict")
    created_at: str = Field(default_factory=_now_iso)


class SystemConfigModel(BaseModel):
    """Row in the ``system_config`` table."""

    key: str
    value: str
    description: Optional[str] = None
    updated_at: str = Field(default_factory=_now_iso)


class AnalysisTaskModel(BaseModel):
    """Row in the ``analysis_tasks`` table."""

    trace_id: str
    status: str = Field(default="started", description="started / running / completed / error")
    alert_ids: Optional[str] = Field(default=None, description="JSON array of alert IDs")
    result: Optional[str] = Field(default=None, description="JSON-serialized result dict")
    error: Optional[str] = None
    started_at: str = Field(default_factory=_now_iso)
    completed_at: Optional[str] = None
