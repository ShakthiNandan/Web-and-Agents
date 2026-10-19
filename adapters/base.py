"""Base adapter definitions, capability flags, and safe execution utilities."""
from abc import ABC, abstractmethod
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Capability constants
CAP_HEADLESS_TASK = "headless_task"
CAP_BACKGROUND_TASK = "background_task"
CAP_INTERACTIVE_TERMINAL = "interactive_terminal"
CAP_SESSION_RESUME = "session_resume"
CAP_MODEL_SELECTION = "model_selection"
CAP_AUTO_APPROVE = "auto_approve"
CAP_STRUCTURED_OUTPUT = "structured_output"

ALL_CAPABILITIES = [
    CAP_HEADLESS_TASK,
    CAP_BACKGROUND_TASK,
    CAP_INTERACTIVE_TERMINAL,
    CAP_SESSION_RESUME,
    CAP_MODEL_SELECTION,
    CAP_AUTO_APPROVE,
    CAP_STRUCTURED_OUTPUT,
]

# Sensitive token and secret patterns for redaction
_SECRET_PATTERNS = [
    (re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(gh[pousr]_[a-zA-Z0-9]{20,})\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\b(glpat-[a-zA-Z0-9_\-]{20,})\b"), "[REDACTED_GITLAB_TOKEN]"),
    (re.compile(r"\b(Bearer\s+)[A-Za-z0-9_\.\-\+\/=]{16,}\b", re.IGNORECASE), r"\1[REDACTED_BEARER_TOKEN]"),
    (
        re.compile(r"""(?i)\b(api[_-]?key|token|secret|password|passwd|auth)\b\s*[:=]\s*['"]?([^'"\s,;]{8,})['"]?"""),
        r"\1=[REDACTED_SECRET]",
    ),
]


def redact_secrets(val: Any) -> Any:
    """Recursively redact obvious API keys and credentials from strings, dicts, and lists."""
    if isinstance(val, str):
        res = val
        for pat, repl in _SECRET_PATTERNS:
            res = pat.sub(repl, res)
        return res
    if isinstance(val, dict):
        out = {}
        for k, v in val.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("token", "secret", "password", "key", "auth")):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(val, list):
        return [redact_secrets(x) for x in val]
    if isinstance(val, tuple):
        return tuple(redact_secrets(x) for x in val)
    return val


def find_executable(cmd_name: str, env_var: Optional[str] = None) -> Optional[str]:
    """Locate an executable by environment override or PATH resolution.
    
    Handles Windows specific extensions and common installation directories.
    """
    if env_var:
        custom_path = os.environ.get(env_var)
        if custom_path:
            p = Path(custom_path).expanduser()
            if p.is_file():
                return str(p.resolve())
            resolved = shutil.which(str(p))
            if resolved:
                return resolved

    # Standard PATH lookup
    resolved = shutil.which(cmd_name)
    if resolved:
        return resolved

    # On Windows, check common local install directories
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        roaming_app = os.environ.get("APPDATA", "")
        candidates = []
        if local_app:
            candidates.extend([
                Path(local_app) / "agy" / "bin" / f"{cmd_name}.exe",
                Path(local_app) / "Programs" / cmd_name / f"{cmd_name}.exe",
            ])
        if roaming_app:
            candidates.extend([
                Path(roaming_app) / "npm" / f"{cmd_name}.cmd",
                Path(roaming_app) / "npm" / f"{cmd_name}.ps1",
                Path(roaming_app) / "npm" / cmd_name,
            ])
        for c in candidates:
            if c.is_file():
                return str(c.resolve())

    return None


class ProviderInfo:
    """Metadata describing an agent provider and its capabilities."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        executable: str,
        is_available: bool,
        executable_path: Optional[str] = None,
        version: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        unavailability_reason: Optional[str] = None,
        description: str = "",
        install_instructions: str = "",
        config_env_vars: Optional[Dict[str, str]] = None,
    ):
        self.provider_id = provider_id
        self.name = name
        self.executable = executable
        self.is_available = is_available
        self.executable_path = executable_path
        self.version = version
        self.capabilities = capabilities or []
        self.unavailability_reason = unavailability_reason
        self.description = description
        self.install_instructions = install_instructions
        self.config_env_vars = config_env_vars or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.name,
            "executable": self.executable,
            "is_available": self.is_available,
            "executable_path": self.executable_path,
            "version": self.version,
            "capabilities": self.capabilities,
            "unavailability_reason": self.unavailability_reason,
            "description": self.description,
            "install_instructions": self.install_instructions,
            "config_env_vars": self.config_env_vars,
        }


class ExecutionResult:
    """Normalized result returned from running or launching an agent task."""

    def __init__(
        self,
        status: str,
        provider: str,
        pid: Optional[int] = None,
        returncode: Optional[int] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        workspace: Optional[str] = None,
        command: Optional[List[str]] = None,
        note: Optional[str] = None,
    ):
        self.status = status
        self.provider = provider
        self.pid = pid
        self.returncode = returncode
        self.output = output
        self.error = error
        self.duration_seconds = duration_seconds
        self.workspace = workspace
        self.command = redact_secrets(command) if command else None
        self.note = note

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "status": self.status,
            "provider": self.provider,
        }
        if self.pid is not None:
            d["pid"] = self.pid
        if self.returncode is not None:
            d["returncode"] = self.returncode
        if self.output is not None:
            d["output"] = self.output
        if self.error is not None:
            d["error"] = self.error
        if self.duration_seconds is not None:
            d["duration_seconds"] = round(self.duration_seconds, 2)
        if self.workspace is not None:
            d["workspace"] = self.workspace
        if self.command is not None:
            d["command"] = self.command
        if self.note is not None:
            d["note"] = self.note
        return d


class BaseAdapter(ABC):
    """Abstract base class for all coding agent CLI adapters."""

    def __init__(self):
        pass

    @property
    @abstractmethod
    def id(self) -> str:
        """Short identifier for this provider (e.g. 'agy', 'opencode', 'claude')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name for this provider."""
        pass

    @property
    @abstractmethod
    def default_executable(self) -> str:
        """Default executable binary name."""
        pass

    @property
    @abstractmethod
    def env_var_bin(self) -> str:
        """Environment variable that can override the executable path."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the agent tool."""
        pass

    @property
    @abstractmethod
    def install_instructions(self) -> str:
        """Human-readable instructions for installing the CLI tool."""
        pass

    def get_executable_path(self) -> Optional[str]:
        """Locate the executable binary if present on system."""
        return find_executable(self.default_executable, self.env_var_bin)

    def is_available(self) -> bool:
        """Check if the executable exists and is runnable."""
        return self.get_executable_path() is not None

    def get_capabilities(self) -> List[str]:
        """List of capabilities supported by this provider."""
        return [CAP_HEADLESS_TASK, CAP_BACKGROUND_TASK, CAP_INTERACTIVE_TERMINAL]

    def get_version(self) -> Optional[str]:
        """Query executable version string."""
        exe = self.get_executable_path()
        if not exe:
            return None
        for flag in ["--version", "-v", "version"]:
            try:
                res = subprocess.run(
                    [exe, flag],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                raw = (res.stdout or res.stderr or "").strip()
                if raw:
                    first_line = raw.splitlines()[0].strip()
                    # Trim excessive length
                    return first_line[:100]
            except Exception:
                continue
        return None

    def get_provider_info(self) -> ProviderInfo:
        """Assemble current provider info and availability status."""
        exe_path = self.get_executable_path()
        is_avail = exe_path is not None
        reason = None if is_avail else f"Executable '{self.default_executable}' not found in PATH or {self.env_var_bin}"
        version = self.get_version() if is_avail else None
        return ProviderInfo(
            provider_id=self.id,
            name=self.name,
            executable=self.default_executable,
            is_available=is_avail,
            executable_path=exe_path,
            version=version,
            capabilities=self.get_capabilities(),
            unavailability_reason=reason,
            description=self.description,
            install_instructions=self.install_instructions,
            config_env_vars={"binary_path": self.env_var_bin},
        )

    @abstractmethod
    def build_run_task_command(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        """Construct the argument list to run a headless prompt synchronously."""
        pass

    @abstractmethod
    def build_background_command(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        """Construct the argument list to launch a headless prompt in background."""
        pass

    def build_terminal_command(
        self,
        workspace: Optional[str] = None,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> List[str]:
        """Construct basic command tokens for interactive terminal execution."""
        exe = self.get_executable_path() or self.default_executable
        cmd = [exe]
        if extra_flags:
            cmd.extend(extra_flags)
        return cmd

    def resolve_workspace(self, workspace: Optional[str] = None) -> str:
        """Resolve workspace directory path safely."""
        if workspace and str(workspace).strip():
            p = Path(workspace).expanduser().resolve()
            if p.is_dir():
                return str(p)
            # If path doesn't exist yet, return resolved string
            return str(p)
        env_ws = os.environ.get("WORKSPACE")
        if env_ws and Path(env_ws).is_dir():
            return str(Path(env_ws).resolve())
        return str(Path.cwd().resolve())

    def run_task(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        timeout: int = 60,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Execute a headless task synchronously and wait for output up to timeout."""
        if not self.is_available():
            return ExecutionResult(
                status="unavailable",
                provider=self.id,
                error=f"Provider '{self.name}' ({self.id}) is not available: executable '{self.default_executable}' not found. {self.install_instructions}",
                returncode=-1,
            )

        ws = self.resolve_workspace(workspace)
        cmd = self.build_run_task_command(
            prompt=prompt,
            workspace=ws,
            model=model,
            auto_approve=auto_approve,
            extra_flags=extra_flags,
        )
        safe_timeout = max(1, min(int(timeout or 60), 600))
        start_t = time.time()

        try:
            # Safe process execution: argument list, no shell injection
            res = subprocess.run(
                cmd,
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=safe_timeout,
                check=False,
            )
            dur = time.time() - start_t
            raw_out = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
            # Redact any secrets before storing or returning
            clean_out = redact_secrets(raw_out)[:20000]
            st = "completed" if res.returncode == 0 else "error"
            err_msg = None if res.returncode == 0 else f"Process exited with code {res.returncode}"
            return ExecutionResult(
                status=st,
                provider=self.id,
                returncode=res.returncode,
                output=clean_out,
                error=err_msg,
                duration_seconds=dur,
                workspace=ws,
                command=cmd,
            )
        except subprocess.TimeoutExpired:
            dur = time.time() - start_t
            return ExecutionResult(
                status="timeout",
                provider=self.id,
                error=f"Task exceeded {safe_timeout}s timeout limit",
                duration_seconds=dur,
                workspace=ws,
                command=cmd,
                note=f"Process timed out after {safe_timeout} seconds; check agent events for any progress.",
            )
        except Exception as e:
            dur = time.time() - start_t
            return ExecutionResult(
                status="error",
                provider=self.id,
                error=f"{type(e).__name__}: {e}",
                duration_seconds=dur,
                workspace=ws,
                command=cmd,
            )

    def launch_background(
        self,
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Launch a headless task process in the background and return its PID immediately."""
        if not self.is_available():
            return ExecutionResult(
                status="unavailable",
                provider=self.id,
                error=f"Provider '{self.name}' ({self.id}) is not available: executable '{self.default_executable}' not found. {self.install_instructions}",
                returncode=-1,
            )

        ws = self.resolve_workspace(workspace)
        cmd = self.build_background_command(
            prompt=prompt,
            workspace=ws,
            model=model,
            auto_approve=auto_approve,
            extra_flags=extra_flags,
        )

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=ws,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return ExecutionResult(
                status="started",
                provider=self.id,
                pid=proc.pid,
                workspace=ws,
                command=cmd,
                note=f"{self.name} is running in background (PID {proc.pid}). Follow events via read_events.",
            )
        except Exception as e:
            return ExecutionResult(
                status="error",
                provider=self.id,
                error=f"{type(e).__name__}: {e}",
                workspace=ws,
                command=cmd,
            )

    def open_terminal(
        self,
        workspace: Optional[str] = None,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Open a visible interactive terminal session on the user desktop."""
        if not self.is_available():
            return ExecutionResult(
                status="unavailable",
                provider=self.id,
                error=f"Provider '{self.name}' ({self.id}) is not available: executable '{self.default_executable}' not found. {self.install_instructions}",
                returncode=-1,
            )

        ws = self.resolve_workspace(workspace)
        exe = self.get_executable_path() or self.default_executable

        if sys.platform == "win32":
            return self._open_terminal_windows(exe=exe, ws=ws, prompt=prompt, extra_flags=extra_flags)
        elif sys.platform == "darwin":
            return self._open_terminal_macos(exe=exe, ws=ws, prompt=prompt, extra_flags=extra_flags)
        else:
            return self._open_terminal_linux(exe=exe, ws=ws, prompt=prompt, extra_flags=extra_flags)

    def _open_terminal_windows(
        self,
        exe: str,
        ws: str,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Open terminal on Windows safely using CREATE_NEW_CONSOLE."""
        safe_ws = ws.replace("'", "''")
        # Build provider-specific command invocation for terminal
        cmd_tokens = self.build_terminal_command(workspace=ws, prompt=prompt, extra_flags=extra_flags)
        # Escape individual arguments for powershell execution
        ps_parts = []
        for t in cmd_tokens:
            ps_parts.append("'" + str(t).replace("'", "''") + "'")
        cli_invocation = "& " + " ".join(ps_parts)
        ps_body = f"Set-Location -LiteralPath '{safe_ws}'; {cli_invocation}"

        CREATE_NEW_CONSOLE = 0x00000010
        try:
            proc = subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", f"& {{ {ps_body} }}"],
                cwd=ws,
                creationflags=CREATE_NEW_CONSOLE,
            )
            return ExecutionResult(
                status="terminal_opened",
                provider=self.id,
                pid=proc.pid,
                workspace=ws,
                note=f"Opened visible {self.name} terminal window on desktop.",
            )
        except Exception:
            # Fallback to cmd.exe
            cmd_str = f'start "{self.name}" cmd /k "cd /d "{ws}" && "{exe}""'
            subprocess.Popen(cmd_str, shell=True)
            return ExecutionResult(
                status="terminal_opened",
                provider=self.id,
                workspace=ws,
                note=f"Opened {self.name} terminal window via cmd.",
            )

    def _open_terminal_macos(
        self,
        exe: str,
        ws: str,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Open Terminal.app on macOS."""
        cmd_tokens = self.build_terminal_command(workspace=ws, prompt=prompt, extra_flags=extra_flags)
        escaped_cmd = " ".join(f'"{str(t)}"' for t in cmd_tokens)
        script = f'tell application "Terminal" to do script "cd {ws} && {escaped_cmd}"'
        try:
            subprocess.Popen(["osascript", "-e", script])
            return ExecutionResult(
                status="terminal_opened",
                provider=self.id,
                workspace=ws,
                note=f"Opened macOS Terminal for {self.name}.",
            )
        except Exception as e:
            return ExecutionResult(
                status="error",
                provider=self.id,
                error=f"Failed to open Terminal.app: {e}",
                workspace=ws,
            )

    def _open_terminal_linux(
        self,
        exe: str,
        ws: str,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Open GUI terminal on Linux."""
        cmd_tokens = self.build_terminal_command(workspace=ws, prompt=prompt, extra_flags=extra_flags)
        terminal_emulators = [
            ["x-terminal-emulator", "-e"],
            ["gnome-terminal", "--"],
            ["kitty"],
            ["alacritty", "-e"],
            ["xterm", "-e"],
        ]
        for term in terminal_emulators:
            t_exe = shutil.which(term[0])
            if t_exe:
                try:
                    full_cmd = [t_exe] + term[1:] + cmd_tokens
                    proc = subprocess.Popen(full_cmd, cwd=ws)
                    return ExecutionResult(
                        status="terminal_opened",
                        provider=self.id,
                        pid=proc.pid,
                        workspace=ws,
                        note=f"Opened {term[0]} terminal for {self.name}.",
                    )
                except Exception:
                    continue
        return ExecutionResult(
            status="error",
            provider=self.id,
            error="No supported terminal emulator found (tried x-terminal-emulator, gnome-terminal, kitty, alacritty, xterm)",
            workspace=ws,
        )
