"""
Unified configuration loader for ICS Defense Platform.

Loads settings from ``config.yaml`` at project root, with environment variable
interpolation and override support.

Usage::

    from agent.config import cfg

    print(cfg.server.port)        # 8002
    print(cfg.database.path)      # "data/ics_defense.db"
    print(cfg.llm.api_key)        # resolved from $XAI_API_KEY
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import yaml

# ---------------------------------------------------------------------------
# Project root: two levels up from this file (agent/config.py -> project root)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"

# Regex for ${ENV_VAR} interpolation
_ENV_RE = re.compile(r"\$\{(\w+)\}")


# ---------------------------------------------------------------------------
# Dataclasses — typed access to configuration sections
# ---------------------------------------------------------------------------

@dataclass
class ServerConfig:
    port: int = 8002
    host: str = "0.0.0.0"
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:80"])


@dataclass
class DatabaseConfig:
    path: str = "data/ics_defense.db"


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379"
    enabled: bool = False


@dataclass
class LLMConfig:
    provider: str = "xai"
    api_key: str = ""
    base_url: str = "https://api.x.ai/v1"
    model: str = "grok-3-mini-fast"


@dataclass
class AuthConfig:
    token: str = ""
    enabled: bool = True


@dataclass
class GuardConfig:
    max_steps: int = 20
    total_timeout: int = 300
    max_retries: int = 2
    step_timeout: int = 30
    stuck_threshold: int = 3


@dataclass
class MemoryConfig:
    provider: str = "simple"


@dataclass
class FeishuConfig:
    bot_webhook_url: str = ""
    bot_secret: str = ""
    app_id: str = ""
    app_secret: str = ""
    app_receive_id: str = ""
    app_receive_id_type: str = "chat_id"


@dataclass
class NotificationsConfig:
    provider: str = "noop"
    redis_stream_key: str = "ics:notifications"
    redis_consumer_group: str = "notification-workers"
    max_retries: int = 5
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    feishu: FeishuConfig = field(default_factory=FeishuConfig)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)

    # Paths to auxiliary YAML configs (relative to project root)
    mcp_servers_path: str = "agent/mcp_servers.yaml"
    tool_policy_path: str = "agent/tool_policy.yaml"
    hooks_path: str = "agent/hooks.yaml"

    # Resolved absolute project root (not serialised)
    _project_root: Path = field(default=_PROJECT_ROOT, repr=False, compare=False)

    # -- convenience helpers ------------------------------------------------

    @property
    def db_path(self) -> str:
        """Return the database path, resolved relative to project root."""
        p = Path(self.database.path)
        if p.is_absolute():
            return str(p)
        return str(self._project_root / p)

    @property
    def mcp_servers_abs(self) -> str:
        p = Path(self.mcp_servers_path)
        if p.is_absolute():
            return str(p)
        return str(self._project_root / p)

    @property
    def tool_policy_abs(self) -> str:
        p = Path(self.tool_policy_path)
        if p.is_absolute():
            return str(p)
        return str(self._project_root / p)

    @property
    def hooks_abs(self) -> str:
        p = Path(self.hooks_path)
        if p.is_absolute():
            return str(p)
        return str(self._project_root / p)

    def guard_dict(self) -> dict:
        """Return guard settings as a plain dict (for AgentGuard ctor)."""
        return {
            "max_steps": self.guard.max_steps,
            "total_timeout": self.guard.total_timeout,
            "max_retries": self.guard.max_retries,
            "step_timeout": self.guard.step_timeout,
            "stuck_threshold": self.guard.stuck_threshold,
        }


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------

def _interpolate_env(value: Any) -> Any:
    """Recursively resolve ``${ENV_VAR}`` placeholders in strings.

    If the entire value is a single ``${VAR}`` reference and the variable is
    not set, the key is dropped (returns ``None``) so that the dataclass
    default takes effect.
    """
    if isinstance(value, str):
        # Fast path: entire value is a single placeholder
        m_full = re.fullmatch(r"\$\{(\w+)\}", value.strip())
        if m_full:
            env_val = os.environ.get(m_full.group(1))
            return env_val  # None when unset → dataclass default wins

        # General case: replace inline placeholders, keep unset as empty
        def _replacer(m: re.Match) -> str:
            return os.environ.get(m.group(1), "")
        result = _ENV_RE.sub(_replacer, value)
        return result
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value


def _apply_env_overrides(raw: dict) -> dict:
    """Override specific YAML keys with well-known environment variables.

    Environment variables take precedence over anything in config.yaml.
    """
    overrides = {
        # server
        ("server", "port"): ("PORT", int),
        ("server", "host"): ("HOST", str),
        # database
        ("database", "path"): ("DB_PATH", str),
        # redis
        ("redis", "url"): ("REDIS_URL", str),
        # llm
        ("llm", "api_key"): ("XAI_API_KEY", str),
        ("llm", "base_url"): ("XAI_BASE_URL", str),
        ("llm", "model"): ("XAI_MODEL", str),
        # auth
        ("auth", "token"): ("API_TOKEN", str),
        # paths
        ("mcp_servers_path",): ("MCP_CONFIG_PATH", str),
    }

    for key_path, (env_name, cast) in overrides.items():
        env_val = os.environ.get(env_name)
        if env_val is None:
            continue
        # Navigate into nested dict and set value
        d = raw
        for part in key_path[:-1]:
            d = d.setdefault(part, {})
        d[key_path[-1]] = cast(env_val)

    return raw


def _dict_to_dataclass(section_cls, data: dict):
    """Construct a dataclass from a dict, ignoring unknown keys and handling
    nested dataclasses.
    """
    if data is None:
        return section_cls()
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(section_cls)}
    kwargs = {}
    for name, fld in fields.items():
        if name.startswith("_"):
            continue
        if name not in data:
            continue
        val = data[name]
        if val is None:
            continue  # Let the dataclass default take effect
        # Check if the field type is itself a dataclass
        if dataclasses.is_dataclass(fld.type if isinstance(fld.type, type) else None):
            val = _dict_to_dataclass(fld.type, val if isinstance(val, dict) else {})
        kwargs[name] = val
    return section_cls(**kwargs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML, interpolate env vars, apply overrides.

    Parameters
    ----------
    config_path : str | Path | None
        Path to ``config.yaml``. Defaults to ``<project_root>/config.yaml``.

    Returns
    -------
    AppConfig
        Fully resolved configuration object.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    # Step 1: interpolate ${ENV_VAR} placeholders in YAML values
    raw = _interpolate_env(raw)

    # Step 2: override with explicit environment variables
    raw = _apply_env_overrides(raw)

    # Step 3: build typed dataclass tree
    cfg = AppConfig(
        server=_dict_to_dataclass(ServerConfig, raw.get("server")),
        database=_dict_to_dataclass(DatabaseConfig, raw.get("database")),
        redis=_dict_to_dataclass(RedisConfig, raw.get("redis")),
        llm=_dict_to_dataclass(LLMConfig, raw.get("llm")),
        auth=_dict_to_dataclass(AuthConfig, raw.get("auth")),
        guard=_dict_to_dataclass(GuardConfig, raw.get("guard")),
        memory=_dict_to_dataclass(MemoryConfig, raw.get("memory")),
        notifications=_dict_to_dataclass(NotificationsConfig, raw.get("notifications")),
        mcp_servers_path=raw.get("mcp_servers_path", "agent/mcp_servers.yaml"),
        tool_policy_path=raw.get("tool_policy_path", "agent/tool_policy.yaml"),
        hooks_path=raw.get("hooks_path", "agent/hooks.yaml"),
    )

    return cfg


# Module-level singleton — import ``cfg`` anywhere.
cfg: AppConfig = load_config()
