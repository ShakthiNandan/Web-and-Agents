"""Provider-neutral coding agent adapter package for agent-hub."""
from .base import (
    BaseAdapter,
    ExecutionResult,
    ProviderInfo,
    redact_secrets,
    find_executable,
    CAP_HEADLESS_TASK,
    CAP_BACKGROUND_TASK,
    CAP_INTERACTIVE_TERMINAL,
    CAP_SESSION_RESUME,
    CAP_MODEL_SELECTION,
    CAP_AUTO_APPROVE,
    CAP_STRUCTURED_OUTPUT,
    ALL_CAPABILITIES,
)
from .antigravity import AntigravityAdapter
from .opencode import OpenCodeAdapter
from .claude import ClaudeCodeAdapter
from .codex import CodexAdapter
from .cline import ClineAdapter
from .registry import AdapterRegistry, get_registry

__all__ = [
    "BaseAdapter",
    "ExecutionResult",
    "ProviderInfo",
    "redact_secrets",
    "find_executable",
    "AntigravityAdapter",
    "OpenCodeAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "ClineAdapter",
    "AdapterRegistry",
    "get_registry",
    "CAP_HEADLESS_TASK",
    "CAP_BACKGROUND_TASK",
    "CAP_INTERACTIVE_TERMINAL",
    "CAP_SESSION_RESUME",
    "CAP_MODEL_SELECTION",
    "CAP_AUTO_APPROVE",
    "CAP_STRUCTURED_OUTPUT",
    "ALL_CAPABILITIES",
]
