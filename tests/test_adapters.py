"""Unit tests for agent adapters, registry, secret redaction, and safe command building."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from adapters.base import (
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
)
from adapters.antigravity import AntigravityAdapter
from adapters.opencode import OpenCodeAdapter
from adapters.claude import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from adapters.cline import ClineAdapter
from adapters.registry import AdapterRegistry, get_registry


class TestSecretRedaction(unittest.TestCase):
    """Test secret and credential scrubbing."""

    def test_redact_api_keys(self):
        sample = "Here is sk-ant-api03-abcdef1234567890abcdef1234567890 in text"
        redacted = redact_secrets(sample)
        self.assertNotIn("sk-ant-api03", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)

    def test_redact_github_token(self):
        sample = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        redacted = redact_secrets(sample)
        self.assertNotIn("ghp_", redacted)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", redacted)

    def test_redact_bearer_token(self):
        sample = "Authorization: Bearer mysecrettoken1234567890"
        redacted = redact_secrets(sample)
        self.assertNotIn("mysecrettoken1234567890", redacted)
        self.assertIn("[REDACTED_BEARER_TOKEN]", redacted)

    def test_redact_dict_and_list(self):
        data = {
            "api_key": "secret12345678",
            "normal_field": "public_data",
            "nested": ["clean", "ghp_abcdef12345678901234567890"],
        }
        redacted = redact_secrets(data)
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["normal_field"], "public_data")
        self.assertEqual(redacted["nested"][0], "clean")
        self.assertIn("[REDACTED_GITHUB_TOKEN]", redacted["nested"][1])


class TestCommandBuilding(unittest.TestCase):
    """Test argument list construction per provider."""

    def test_antigravity_command_building(self):
        adapter = AntigravityAdapter()
        with patch.object(adapter, "get_executable_path", return_value="agy"):
            cmd = adapter.build_run_task_command("run tests", model="gpt-4o", auto_approve=True)
            self.assertEqual(cmd, ["agy", "-p", "run tests", "--dangerously-skip-permissions", "--model", "gpt-4o"])

            bg_cmd = adapter.build_background_command("fix bug", auto_approve=False)
            self.assertEqual(bg_cmd, ["agy", "-p", "fix bug"])

            term_cmd = adapter.build_terminal_command(prompt="inspect repo")
            self.assertEqual(term_cmd, ["agy", "-i", "inspect repo"])

    def test_opencode_command_building(self):
        adapter = OpenCodeAdapter()
        with patch.object(adapter, "get_executable_path", return_value="opencode"):
            cmd = adapter.build_run_task_command("review PR", model="claude-3-5-sonnet", auto_approve=True)
            self.assertEqual(cmd, ["opencode", "run", "--auto", "--model", "claude-3-5-sonnet", "review PR"])

            term_cmd = adapter.build_terminal_command(prompt="start coding")
            self.assertEqual(term_cmd, ["opencode", "--prompt", "start coding"])

    def test_claude_command_building(self):
        adapter = ClaudeCodeAdapter()
        with patch.object(adapter, "get_executable_path", return_value="claude"):
            cmd = adapter.build_run_task_command("write docs", model="claude-3-5-sonnet", auto_approve=True)
            self.assertEqual(cmd, ["claude", "-p", "write docs", "--dangerously-skip-permissions", "--model", "claude-3-5-sonnet"])

            term_cmd = adapter.build_terminal_command(prompt="refactor")
            self.assertEqual(term_cmd, ["claude", "refactor"])

    def test_codex_command_building(self):
        adapter = CodexAdapter()
        with patch.object(adapter, "get_executable_path", return_value="codex"):
            cmd = adapter.build_run_task_command("generate unit tests", model="o1-preview")
            self.assertEqual(cmd, ["codex", "exec", "--model", "o1-preview", "generate unit tests"])

            term_cmd = adapter.build_terminal_command()
            self.assertEqual(term_cmd, ["codex"])

    def test_cline_command_building(self):
        adapter = ClineAdapter()
        with patch.object(adapter, "get_executable_path", return_value="cline"):
            cmd = adapter.build_run_task_command("build app", model="gemini-1.5-pro")
            self.assertEqual(cmd, ["cline", "task", "--model", "gemini-1.5-pro", "build app"])

            term_cmd = adapter.build_terminal_command()
            self.assertEqual(term_cmd, ["cline"])


class TestCapabilitiesAndAvailability(unittest.TestCase):
    """Test explicit capability definitions and unavailable handling."""

    def test_capabilities_explicit(self):
        reg = AdapterRegistry()
        agy = reg.get("agy")
        self.assertIn(CAP_HEADLESS_TASK, agy.get_capabilities())
        self.assertIn(CAP_BACKGROUND_TASK, agy.get_capabilities())
        self.assertIn(CAP_INTERACTIVE_TERMINAL, agy.get_capabilities())
        self.assertIn(CAP_SESSION_RESUME, agy.get_capabilities())
        self.assertIn(CAP_MODEL_SELECTION, agy.get_capabilities())
        self.assertIn(CAP_AUTO_APPROVE, agy.get_capabilities())

        opencode = reg.get("opencode")
        self.assertIn(CAP_STRUCTURED_OUTPUT, opencode.get_capabilities())
        self.assertIn(CAP_AUTO_APPROVE, opencode.get_capabilities())

    def test_graceful_unavailable_handling(self):
        adapter = ClaudeCodeAdapter()
        with patch.object(adapter, "get_executable_path", return_value=None):
            self.assertFalse(adapter.is_available())
            info = adapter.get_provider_info()
            self.assertFalse(info.is_available)
            self.assertIn("not found", info.unavailability_reason)

            # Execution attempt on unavailable provider returns graceful result without crashing
            res = adapter.run_task("do task")
            self.assertEqual(res.status, "unavailable")
            self.assertEqual(res.returncode, -1)
            self.assertIn("not available", res.error)

            bg_res = adapter.launch_background("do task")
            self.assertEqual(bg_res.status, "unavailable")

            term_res = adapter.open_terminal()
            self.assertEqual(term_res.status, "unavailable")


class TestExecutionMocking(unittest.TestCase):
    """Test execution lifecycle with mocked subprocess calls."""

    def test_successful_run_task(self):
        adapter = AntigravityAdapter()
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "Task output line 1\nTask output line 2"
        fake_proc.stderr = ""

        with patch.object(adapter, "get_executable_path", return_value="fake_agy"), \
             patch("subprocess.run", return_value=fake_proc) as mock_run:
            res = adapter.run_task("run tests", workspace=".")
            self.assertEqual(res.status, "completed")
            self.assertEqual(res.returncode, 0)
            self.assertIn("Task output line 1", res.output)
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            # Verify safe argument list is passed, never shell=True
            self.assertIsInstance(args[0], list)
            self.assertFalse(kwargs.get("shell", False))

    def test_run_task_secret_redaction_in_output(self):
        adapter = OpenCodeAdapter()
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "Found key sk-ant-api03-123456789012345678901234 in file"
        fake_proc.stderr = ""

        with patch.object(adapter, "get_executable_path", return_value="opencode"), \
             patch("subprocess.run", return_value=fake_proc):
            res = adapter.run_task("check repo")
            self.assertNotIn("sk-ant-api03-123456789012345678901234", res.output)
            self.assertIn("[REDACTED_API_KEY]", res.output)

    def test_run_task_timeout(self):
        adapter = AntigravityAdapter()
        with patch.object(adapter, "get_executable_path", return_value="fake_agy"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["fake_agy"], timeout=5)):
            res = adapter.run_task("long task", timeout=5)
            self.assertEqual(res.status, "timeout")
            self.assertIn("timeout", res.error)

    def test_run_task_error(self):
        adapter = AntigravityAdapter()
        fake_proc = MagicMock()
        fake_proc.returncode = 2
        fake_proc.stdout = ""
        fake_proc.stderr = "SyntaxError: invalid syntax"

        with patch.object(adapter, "get_executable_path", return_value="fake_agy"), \
             patch("subprocess.run", return_value=fake_proc):
            res = adapter.run_task("bad script")
            self.assertEqual(res.status, "error")
            self.assertEqual(res.returncode, 2)
            self.assertIn("SyntaxError", res.output)

    def test_launch_background_mock(self):
        adapter = AntigravityAdapter()
        fake_proc = MagicMock()
        fake_proc.pid = 4321

        with patch.object(adapter, "get_executable_path", return_value="fake_agy"), \
             patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
            res = adapter.launch_background("background prompt")
            self.assertEqual(res.status, "started")
            self.assertEqual(res.pid, 4321)
            mock_popen.assert_called_once()
            args, _ = mock_popen.call_args
            self.assertIsInstance(args[0], list)


class TestRegistry(unittest.TestCase):
    """Test registry discovery, lookups, and default provider selection."""

    def setUp(self):
        self.reg = AdapterRegistry()

    def test_all_five_adapters_registered(self):
        providers = [p.provider_id for p in self.reg.list_providers()]
        for expected in ["agy", "opencode", "claude", "codex", "cline"]:
            self.assertIn(expected, providers)

    def test_case_insensitive_lookup(self):
        self.assertIsNotNone(self.reg.get("AGY"))
        self.assertIsNotNone(self.reg.get("OpenCode"))
        self.assertIsNotNone(self.reg.get("CLAUDE"))

    def test_unknown_provider_dispatch(self):
        res = self.reg.run_task("nonexistent_agent", "hello")
        self.assertEqual(res.status, "error")
        self.assertIn("Unknown agent provider", res.error)

    def test_default_provider_override_env(self):
        with patch.dict(os.environ, {"AGENT_HUB_DEFAULT_PROVIDER": "opencode"}):
            self.assertEqual(self.reg.get_default_provider().id, "opencode")

    def test_custom_binary_path_env(self):
        with patch.dict(os.environ, {"AGENT_HUB_CLAUDE_BIN": "/custom/bin/claude"}):
            adapter = ClaudeCodeAdapter()
            with patch("shutil.which", return_value="/custom/bin/claude"):
                self.assertEqual(adapter.get_executable_path(), "/custom/bin/claude")


if __name__ == "__main__":
    unittest.main()
