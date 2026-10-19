# agent-hub

Local agents (and your Antigravity IDE) report to a hub on your laptop. Claude reads them, and queues tasks for the ones that can take them, through MCP over Tailscale Funnel. You watch and control the same data in a web dashboard.
Python 3.8+, stdlib only, no install. Windows, macOS, Linux.

```
agents / Antigravity hooks --POST /report--> hub (127.0.0.1:8080) <--MCP over Funnel-- Claude
agents <--GET /tasks/<id>--/                 dashboard at /<token>/   (read, filter, send tasks)
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
Install `agent-hub.skill` so Claude knows the workflow.

## Antigravity IDE -> hub (new)

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

Limits, read these:
- **Monitor-only.** Antigravity hooks can observe but cannot receive instructions, so `send_task` to an `agy-*` agent is refused (hub and dashboard both). Claude can see what the IDE agent is doing; it cannot drive it.
- Online/offline: monitor-only agents only speak when active, so they count as online for 30 min after the last event instead of 60 s.
- Hooks run synchronously in the agent loop; the script has a 2 s network timeout and swallows all errors, so a dead hub never breaks the IDE.
- Hooks are installed for `PreInvocation`, `PostToolUse` and `Stop` only. `PreToolUse` is deliberately skipped: its response can allow/deny a tool, and a logger should not be in that path.
- Obvious secrets (keys named like key/token/secret/password, and common API-key patterns) are redacted from tool args, but file paths, commands and code snippets are sent as-is. Treat the hub DB (`~/.agent-hub/hub.db`) as sensitive.
- Hook format follows Antigravity's public docs and community write-ups (global `~/.gemini/config/hooks.json`, workspace `.agents/hooks.json`). It was tested here with simulated payloads, not inside a live Antigravity. After installing, ask Antigravity "Which hooks are installed?" to confirm it sees `agent-hub`.

## Dashboard

Open `http://127.0.0.1:8080/<token>/` locally (or the same path on your Funnel URL).
- Agent cards: online dot, status, queue counts, last event. Click a card to filter events to that agent.
- Events: level filter, text filter, pause, clear view; incremental loading (no flicker); events with details expand in place.
- Send task form (hidden with `--read-only` or when only monitor-only agents exist); tasks table with output and cancel for pending tasks.

## Wire up other agents

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
Any language works: it is two HTTP calls (`POST /report`, `GET /tasks/<id>` + `POST /tasks/<n>/result`).
Pass `"readonly": true` in a report to mark an agent monitor-only.
Agent is "online" if it reported or polled in the last 60 s.

## MCP tools

`list_agents`, `read_events(agent_id?, since_id?, limit?, level?)`, `list_tasks`, `get_task`,
`send_task(agent_id, text)`, `cancel_task`. `--read-only` removes the last two (and disables the dashboard send form).

## Security

- Funnel is public internet. The secret path (256-bit token) is the only gate: treat the URL like a password.
  Rotate: `python hub.py --rotate-token`, then update the connector URL, `AGENT_HUB_URL`, and re-run `install_antigravity.py` (it stores the token in `~/.agent-hub/client.json`).
- Hub never executes anything. `send_task` only queues text; your agent decides what to do with it.
  Do not wire `handler` to `subprocess(shell=True)` without an allowlist.
- Agent log text is untrusted input to Claude (prompt-injection surface); the skill tells Claude to treat it as data. This matters more for Antigravity: its tool args can contain text from web pages or files it read.
- Binds 127.0.0.1 only. Tokens appear in URLs, so keep proxy/access logs private.

## Upgrading from 0.1.0

Drop in the new files. The existing `~/.agent-hub/hub.db` is migrated automatically; token unchanged.

## Test

`python tests/smoke_test.py` (starts a throwaway hub; covers REST, MCP, dashboard API, the Antigravity hook and the monitor-only rules).
