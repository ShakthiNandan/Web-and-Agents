# Agent Providers & Multi-Agent Architecture

`agent-hub` provides a provider-neutral agent adapter architecture allowing you to orchestrate, monitor, and command multiple AI coding agent CLIs from a unified local dashboard and Claude MCP connector.

---

## Provider Capability Matrix

| Provider ID | Provider Name | Default CLI | Detection / Fallback | Headless Run | Background Launch | Interactive Terminal | Model Selection | Auto Approve | Config Env Var |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|---|
| `agy` | **Antigravity** | `agy` / `agy.exe` | `%LOCALAPPDATA%\agy\bin`, PATH | ✅ (`-p`) | ✅ (`-p`) | ✅ (`-i` / interactive) | ✅ (`--model`) | ✅ (`--dangerously-skip-permissions`) | `AGENT_HUB_AGY_BIN` |
| `opencode` | **OpenCode** | `opencode` / `opencode.cmd` | `%APPDATA%\npm`, PATH | ✅ (`run`) | ✅ (`run`) | ✅ (`--prompt` / interactive) | ✅ (`--model`) | ✅ (`--auto`) | `AGENT_HUB_OPENCODE_BIN` |
| `claude` | **Claude Code** | `claude` / `claude.cmd` | PATH | ✅ (`-p`) | ✅ (`-p`) | ✅ (interactive) | ✅ (`--model`) | ✅ (`--dangerously-skip-permissions`) | `AGENT_HUB_CLAUDE_BIN` |
| `codex` | **OpenAI Codex CLI** | `codex` / `codex.exe` | PATH | ✅ (`exec`) | ✅ (`exec`) | ✅ (interactive) | ✅ (`--model`) | N/A | `AGENT_HUB_CODEX_BIN` |
| `cline` | **Cline CLI** | `cline` / `cline.cmd` | PATH | ✅ (`task`) | ✅ (`task`) | ✅ (interactive) | ✅ (`--model`) | N/A | `AGENT_HUB_CLINE_BIN` |

---

## Local Prerequisites & Installation

### 1. Antigravity (AGY)
- **Status on this system**: Included with Antigravity IDE / CLI distribution.
- **Binary**: `agy.exe` (typically in `C:\Users\<user>\AppData\Local\agy\bin` or on PATH).
- **Prerequisites**: Python 3.8+ (for hook monitoring).
- **Setup**:
  ```bash
  # Check availability
  agy --version
  
  # Wire IDE hooks to report live tool calls to the hub
  python antigravity/install_antigravity.py
  ```

### 2. OpenCode
- **Status on this system**: Installed via npm (`@opencode/cli`).
- **Prerequisites**: Node.js 18+, npm / pnpm.
- **Install**:
  ```bash
  npm install -g @opencode/cli
  ```
- **Check**:
  ```bash
  opencode --version
  ```
- **Headless invocation**:
  `opencode run --auto "<prompt>"`

### 3. Claude Code (Anthropic)
- **Prerequisites**: Node.js 18+, Anthropic API key (`ANTHROPIC_API_KEY`).
- **Install**:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- **Check**:
  ```bash
  claude --version
  ```
- **Headless invocation**:
  `claude -p "<prompt>" --dangerously-skip-permissions`

### 4. OpenAI Codex CLI
- **Prerequisites**: Python / Node runtime or platform binary, OpenAI API key (`OPENAI_API_KEY`).
- **Install**:
  Install your preferred Codex CLI wrapper or specify custom binary path:
  ```bash
  set AGENT_HUB_CODEX_BIN=C:\path\to\codex.exe
  ```
- **Headless invocation**:
  `codex exec "<prompt>"` (subcommand configurable via `AGENT_HUB_CODEX_SUBCOMMAND`).

### 5. Cline CLI
- **Prerequisites**: Node.js 18+.
- **Install**:
  ```bash
  npm install -g cline
  ```
- **Check**:
  ```bash
  cline --version
  ```
- **Headless invocation**:
  `cline task "<prompt>"` (subcommand configurable via `AGENT_HUB_CLINE_SUBCOMMAND`).

---

## Graceful Unavailability Handling

Agent tools do not pretend that all CLIs are present or share identical arguments:
- If a CLI executable is not found on PATH or via its override environment variable:
  - `is_available` is marked as `False`.
  - The provider's `unavailability_reason` details which executable was missing and lists installation instructions.
  - Calling `run_agent_task`, `launch_agent_background`, or `open_agent_terminal` with that provider returns an explicit `{"status": "unavailable", "returncode": -1, "error": "..."}` response without throwing exceptions or breaking the hub process.
  - The dashboard disables unavailable options in the provider dropdown and displays an explanatory badge.

---

## Safe Execution & Secret Redaction

1. **No Shell Injection**:
   - All process executions (`run_task` and `launch_background`) use argument arrays passed directly to `subprocess.run` or `subprocess.Popen` without `shell=True`.
   - Windows terminal launches construct PowerShell commands with `-LiteralPath` and safely escaped argument tokens (`'arg'.replace("'", "''")`), completely neutralizing command injection.

2. **No Secret Logging**:
   - The hub automatically redacts sensitive credentials:
     - API keys (e.g. `sk-...`, `ghp_...`, `glpat-...`).
     - HTTP Bearer tokens (`Bearer ...`).
     - Sensitive environment variables and payload fields (`token`, `secret`, `password`, `key`, `auth`).
   - Redacted strings are masked with `[REDACTED_API_KEY]`, `[REDACTED_BEARER_TOKEN]`, etc. before logging events, displaying in the dashboard, or returning via MCP.

---

## MCP Tool Reference

Claude and MCP-compatible clients can use these tools to inspect and command agents:

| MCP Tool Name | Description | Key Parameters |
|---|---|---|
| `list_providers` | List all supported providers, availability, versions, paths, and capabilities. | `provider` (optional filter) |
| `run_agent_task` | Run a synchronous headless task with a chosen provider and wait for output. | `prompt` (required), `provider` (optional), `workspace`, `timeout`, `model`, `auto_approve` |
| `launch_agent_background` | Spawn a background headless session and return PID immediately. | `prompt` (required), `provider` (optional), `workspace`, `model`, `auto_approve` |
| `open_agent_terminal` | Open a visible desktop terminal running the interactive CLI. | `provider` (optional), `workspace`, `prompt` |
| `run_antigravity_task` | *(Backward compatible)* Run headless task with Antigravity (`agy`). | `prompt`, `workspace`, `timeout` |
| `launch_antigravity_background` | *(Backward compatible)* Run background session with Antigravity (`agy`). | `prompt`, `workspace` |
| `open_antigravity_terminal` | *(Backward compatible)* Open interactive terminal for Antigravity (`agy`). | `workspace`, `prompt` |

---

## Cloud Skill Integration

To give Claude awareness of your local agents:
1. Package the skill:
   ```bash
   python package_skill.py
   ```
2. Upload `agent-hub.skill` to Claude:
   - Go to `claude.ai` > Settings > Skills / Capabilities > Upload `agent-hub.skill`.
3. Add custom connector:
   - URL: `https://<laptop>.<tailnet>.ts.net/<token>/mcp`
4. Claude can now check your agents with `list_agents`, inspect installed CLI tools with `list_providers`, and execute tasks across Antigravity, OpenCode, Claude Code, OpenAI Codex, or Cline.
