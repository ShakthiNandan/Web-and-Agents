# agent-hub

Local agents (and your Antigravity IDE, OpenCode, Claude Code, OpenAI Codex, or Cline) report to and can be controlled from a hub on your laptop. Claude reads them, monitors execution, and runs tasks across supported coding agents through MCP over Tailscale Funnel. You watch and control the same data in a real-time web dashboard.

Python 3.8+, stdlib only, no install. Windows, macOS, Linux.

```
agents / IDE hooks / CLIs --POST /report--> hub (127.0.0.1:8080) <--MCP over Funnel-- Claude
agents <--GET /tasks/<id>--/                 dashboard at /<token>/   (control, filter, run agents)
hub --> launches agy, opencode, claude, codex, cline
```

## Run

```bash
python hub.py                        # prints URLs; token saved to ~/.agent-hub/token
tailscale funnel --bg 8080           # public https://<laptop>.<tailnet>.ts.net
python hub.py --public-url https://<laptop>.<tailnet>.ts.net   # prints the exact connector URL
```

Funnel must be enabled for your tailnet (admin console > Access controls > `funnel` node attribute).
Stop exposing: `tailscale funnel reset`. On Windows use `python` instead of `python3`.

## Connect Claude

claude.ai > Settings > Connectors > Add custom connector
URL: `https://<laptop>.<tailnet>.ts.net/<token>/mcp` (no OAuth). Name it e.g. `agent-hub`, enable it in the chat.
Install `agent-hub.skill` (packaged via `python package_skill.py`) so Claude knows the workflow.

---

## Multi-Agent Adapter Architecture

`agent-hub` provides a provider-neutral agent adapter architecture. Antigravity (AGY) remains fully supported with backward-compatible tooling, and other coding agents are integrated through specialized CLI adapters.

### Provider Capability Matrix

| Provider ID | Provider Name | Default CLI | Detection / Fallback | Headless Task | Background Launch | Interactive Terminal | Model Selection | Auto Approve | Config Env Var |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|---|
| `agy` | **Antigravity** | `agy` / `agy.exe` | `%LOCALAPPDATA%\agy\bin`, PATH | ✅ (`-p`) | ✅ (`-p`) | ✅ (`-i` / interactive) | ✅ (`--model`) | ✅ (`--dangerously-skip-permissions`) | `AGENT_HUB_AGY_BIN` |
| `opencode` | **OpenCode** | `opencode` / `opencode.cmd` | `%APPDATA%\npm`, PATH | ✅ (`run`) | ✅ (`run`) | ✅ (`--prompt` / interactive) | ✅ (`--model`) | ✅ (`--auto`) | `AGENT_HUB_OPENCODE_BIN` |
| `claude` | **Claude Code** | `claude` / `claude.cmd` | PATH | ✅ (`-p`) | ✅ (`-p`) | ✅ (interactive) | ✅ (`--model`) | ✅ (`--dangerously-skip-permissions`) | `AGENT_HUB_CLAUDE_BIN` |
| `codex` | **OpenAI Codex CLI** | `codex` / `codex.exe` | PATH | ✅ (`exec`) | ✅ (`exec`) | ✅ (interactive) | ✅ (`--model`) | N/A | `AGENT_HUB_CODEX_BIN` |
| `cline` | **Cline CLI** | `cline` / `cline.cmd` | PATH | ✅ (`task`) | ✅ (`task`) | ✅ (interactive) | ✅ (`--model`) | N/A | `AGENT_HUB_CLINE_BIN` |

*Default provider can be configured using `AGENT_HUB_DEFAULT_PROVIDER` (defaults to `agy`).*

### Graceful Unavailable Handling

Agents are not assumed to share identical CLI commands or to be pre-installed on every system:
- Detection inspects PATH and standard install directories on startup and on demand.
- Executables not found are gracefully marked as `is_available: false` with the exact missing binary name and installation instructions.
- Attempting to run an unavailable provider returns a structured error (`{"status": "unavailable", "returncode": -1, ...}`) instead of raising an unhandled exception or crashing the hub.
- The web dashboard disables unavailable providers in the launcher dropdown and shows their status badges and install commands.

---

## Local Prerequisites & CLI Installation

### 1. Antigravity (AGY)
- Included with the Google Antigravity IDE / CLI distribution.
- Binary: `agy` / `agy.exe`.
- Wire IDE hooks to report tool use:
  ```bash
  python antigravity/install_antigravity.py
  ```

### 2. OpenCode
- Autonomous open-source AI software engineering agent.
- Prerequisites: Node.js 18+.
- Install globally via npm:
  ```bash
  npm install -g @opencode/cli
  ```

### 3. Claude Code
- Anthropic's agentic terminal coding assistant.
- Prerequisites: Node.js 18+, `ANTHROPIC_API_KEY`.
- Install globally via npm:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```

### 4. OpenAI Codex CLI
- Prerequisites: OpenAI API key (`OPENAI_API_KEY`).
- Install or point to your Codex binary:
  ```bash
  export AGENT_HUB_CODEX_BIN=/path/to/codex
  ```

### 5. Cline CLI
- Prerequisites: Node.js 18+.
- Install globally via npm:
  ```bash
  npm install -g cline
  ```

See [docs/providers.md](docs/providers.md) for full provider documentation and parameter details.

---

## Antigravity IDE -> hub Hooks

Antigravity runs hook scripts at points in its agent loop. `antigravity/agy_hook.py` turns them into hub events.

```bash
python antigravity/install_antigravity.py                 # all workspaces: ~/.gemini/config/hooks.json
python antigravity/install_antigravity.py --workspace .   # or just this workspace: .agents/hooks.json
python antigravity/install_antigravity.py --test          # sends a test event
python antigravity/install_antigravity.py --uninstall
```

Restart Antigravity, run any agent task, and an agent named `Antigravity: <workspace folder>` (id `agy-<folder>`) appears in the dashboard and in Claude's `list_agents`.

What gets reported: run started / each model call (debug), every tool call with a short summary and trimmed arguments (click an event in the dashboard to expand), errors, and run finished with the termination reason.
Set `AGENT_HUB_AGY_TAIL=1` in the environment Antigravity starts with to also attach the last transcript lines on finish.

Limits:
- **Monitor-only.** Antigravity hooks can observe but cannot receive instructions, so `send_task` to an `agy-*` agent is refused (hub and dashboard both). Claude can see what the IDE agent is doing; it cannot drive it.
- Online/offline: monitor-only agents only speak when active, so they count as online for 30 min after the last event instead of 60 s.
- Hooks run synchronously in the agent loop; the script has a 2 s network timeout and swallows all errors, so a dead hub never breaks the IDE.

---

## Dashboard

Open `http://127.0.0.1:8080/<token>/` locally (or the same path on your Funnel URL).
- **Coding agent execution**: Select agent provider (`Antigravity`, `OpenCode`, `Claude Code`, `OpenAI Codex`, `Cline`), type a prompt, and run in background, run synchronously, or open a live terminal.
- **Provider cards**: View installed/available providers, versions, and capabilities.
- **Agent cards**: Online dot, status, queue counts, last event. Click a card to filter events to that agent.
- **Events**: Level filter, text filter, pause, clear view; incremental loading (no flicker); events with details expand in place.
- **Tasks**: Send task form and tasks table with status and output.

---

## Wire up custom task agents

```bash
export AGENT_HUB_URL=http://127.0.0.1:8080/<token>      # Windows: set AGENT_HUB_URL=...
python examples/demo_agent.py cam-1                     # demo
examples/report.sh my-agent info "hello"                # from any shell script
```
```python
from agent_client import Hub
hub = Hub("my-agent", name="My agent")
hub.report("started", status="busy")
hub.run(lambda task: do_work(task["text"]))             # executes tasks Claude sends
```

---

## MCP Tools

### Multi-Agent Tools
- `list_providers`: List supported agent adapters with availability, paths, versions, and capabilities.
- `run_agent_task(prompt, provider?, workspace?, timeout?, model?, auto_approve?)`: Run a synchronous task with any provider and wait for output.
- `launch_agent_background(prompt, provider?, workspace?, model?, auto_approve?)`: Spawn a background headless session and return PID immediately.
- `open_agent_terminal(provider?, workspace?, prompt?)`: Open a visible terminal window running the interactive CLI.

### Backward-Compatible Antigravity Tools
- `run_antigravity_task(prompt, workspace?, timeout?)`: Synchronous headless Antigravity task.
- `launch_antigravity_background(prompt, workspace?)`: Headless background Antigravity session.
- `open_antigravity_terminal(workspace?, prompt?)`: Interactive visible terminal for Antigravity.

### Monitoring & Task Tools
- `list_agents`: List agents reporting to the hub.
- `read_events(agent_id?, since_id?, limit?, level?)`: Read incremental agent events.
- `list_tasks`, `get_task`, `send_task`, `cancel_task`: Manage queued tasks.

---

## Security & Safe Argument Handling

- **No Shell Injection**: Process execution uses strict argument arrays passed to `subprocess.run` / `subprocess.Popen` (no `shell=True`). Terminal commands are escaped safely with `-LiteralPath` and single-quote neutralization.
- **No Secret Logging**: Sensitive credentials (API keys `sk-...`, `ghp_...`, Bearer tokens, passwords, and tokens) are automatically redacted from logs, event payloads, and tool outputs.
- **Authentication**: All endpoints require the 256-bit secret token in the URL path. Rotate via `python hub.py --rotate-token`.
- **Local Binding**: Binds to `127.0.0.1` only. Tailscale Funnel securely exposes the port over HTTPS.

---

## Tests

Run the full test suite (stdlib only, mocked executables so external CLIs are not required):

```bash
# Adapter unit tests (capabilities, detection, safe argument handling, secret redaction, mocking)
python tests/test_adapters.py

# End-to-end smoke test (spawns throwaway hub, tests REST, MCP, dashboard API, hooks, and providers)
python tests/smoke_test.py
```
