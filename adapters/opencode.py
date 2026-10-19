"""OpenCode agent adapter."""
from typing import List, Optional
from .base import (
    BaseAdapter,
    CAP_HEADLESS_TASK,
    CAP_BACKGROUND_TASK,
    CAP_INTERACTIVE_TERMINAL,
    CAP_SESSION_RESUME,
    CAP_MODEL_SELECTION,
    CAP_AUTO_APPROVE,
    CAP_STRUCTURED_OUTPUT,
)


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode CLI (@opencode/cli)."""

    @property
    def id(self) -> str:
        return "opencode"

    @property
    def name(self) -> str:
        return "OpenCode"

    @property
    def default_executable(self) -> str:
        return "opencode"

    @property
    def env_var_bin(self) -> str:
        return "AGENT_HUB_OPENCODE_BIN"

    @property
    def description(self) -> str:
        return "OpenCode CLI: autonomous software engineering agent with session management."

    @property
    def install_instructions(self) -> str:
        return "Install OpenCode CLI via npm: `npm install -g @opencode/cli` (or configure AGENT_HUB_OPENCODE_BIN)."

    def get_capabilities(self) -> List[str]:
        return [
            CAP_HEADLESS_TASK,
            CAP_BACKGROUND_TASK,
            CAP_INTERACTIVE_TERMINAL,
            CAP_SESSION_RESUME,
            CAP_MODEL_SELECTION,
            CAP_AUTO_APPROVE,
            CAP_STRUCTURED_OUTPUT,
        ]

    def build_run_task_command(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        exe = self.get_executable_path() or self.default_executable
        cmd = [exe, "run"]
        if auto_approve:
            cmd.append("--auto")
        if model:
            cmd.extend(["--model", model])
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.append(prompt)
        return cmd

    def build_background_command(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        exe = self.get_executable_path() or self.default_executable
        cmd = [exe, "run"]
        if auto_approve:
            cmd.append("--auto")
        if model:
            cmd.extend(["--model", model])
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.append(prompt)
        return cmd

    def build_terminal_command(
        self,
        workspace: Optional[str] = None,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        exe = self.get_executable_path() or self.default_executable
        cmd = [exe]
        clean_p = (prompt or "").strip()
        if clean_p:
            cmd.extend(["--prompt", clean_p])
        if extra_flags:
            cmd.extend(extra_flags)
        return cmd
