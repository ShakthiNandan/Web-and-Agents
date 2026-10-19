"""Cline CLI agent adapter."""
import os
from typing import List, Optional
from .base import (
    BaseAdapter,
    CAP_HEADLESS_TASK,
    CAP_BACKGROUND_TASK,
    CAP_INTERACTIVE_TERMINAL,
    CAP_MODEL_SELECTION,
)


class ClineAdapter(BaseAdapter):
    """Adapter for Cline CLI."""

    @property
    def id(self) -> str:
        return "cline"

    @property
    def name(self) -> str:
        return "Cline CLI"

    @property
    def default_executable(self) -> str:
        return "cline"

    @property
    def env_var_bin(self) -> str:
        return "AGENT_HUB_CLINE_BIN"

    @property
    def description(self) -> str:
        return "Cline CLI: autonomous AI coding agent supporting tool calling and repository modifications."

    @property
    def install_instructions(self) -> str:
        return "Install Cline CLI via npm: `npm install -g cline` (or configure AGENT_HUB_CLINE_BIN)."

    def get_capabilities(self) -> List[str]:
        return [
            CAP_HEADLESS_TASK,
            CAP_BACKGROUND_TASK,
            CAP_INTERACTIVE_TERMINAL,
            CAP_MODEL_SELECTION,
        ]

    def _get_subcommand(self) -> str:
        return os.environ.get("AGENT_HUB_CLINE_SUBCOMMAND", "task")

    def build_run_task_command(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        exe = self.get_executable_path() or self.default_executable
        cmd = [exe, self._get_subcommand()]
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
        cmd = [exe, self._get_subcommand()]
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
            cmd.append(clean_p)
        if extra_flags:
            cmd.extend(extra_flags)
        return cmd
