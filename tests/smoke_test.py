#!/usr/bin/env python3
"""End-to-end smoke test: starts a hub on a free port with a temp DB and exercises REST, MCP, dashboard API and the Antigravity hook."""
import json, os, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "t" * 64
tmp = tempfile.mkdtemp()
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
BASE = f"http://127.0.0.1:{PORT}/{TOKEN}"
env = dict(os.environ, AGENT_HUB_HOME=tmp, AGENT_HUB_TOKEN=TOKEN)
hub = subprocess.Popen([sys.executable, str(ROOT / "hub.py"), "--port", str(PORT)], env=env, stdout=subprocess.DEVNULL)
fails = []


def call(method, path, body=None, base=BASE):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read(); return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)


def mcp(method, params=None, i=1):
    return call("POST", "/mcp", {"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})[1]


def tool(name, args=None):
    r = mcp("tools/call", {"name": name, "arguments": args or {}})["result"]
    return r["isError"], r["content"][0]["text"]


try:
    for _ in range(50):
        try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
        except urllib.error.HTTPError: break
        except Exception: time.sleep(0.1)
    check("wrong token -> 404", call("GET", "/api/state", base=f"http://127.0.0.1:{PORT}/nope")[0] == 404)
    check("dashboard html", b"agent-hub" in urllib.request.urlopen(BASE + "/").read())

    # regular agent: report, task round trip
    check("report", call("POST", "/report", {"agent_id": "cam-1", "msg": "hi", "status": "idle"})[1]["ok"])
    check("bad agent_id rejected", call("POST", "/report", {"agent_id": "bad id!"})[0] == 400)
    err, txt = tool("send_task", {"agent_id": "cam-1", "text": "run tests"}); tid = json.loads(txt)["task_id"]
    check("send_task via MCP", not err and tid)
    tasks = call("GET", "/tasks/cam-1")[1]["tasks"]
    check("agent claims task", len(tasks) == 1 and tasks[0]["status"] == "running")
    check("finish task", call("POST", f"/tasks/{tid}/result", {"status": "done", "output": "ok"})[1]["ok"])
    check("get_task output", json.loads(tool("get_task", {"task_id": tid})[1])["task"]["output"] == "ok")

    # dashboard API
    st, j = call("POST", "/api/task", {"agent_id": "cam-1", "text": "from dashboard"}); check("dashboard queues task", st == 200)
    check("dashboard cancels task", call("POST", "/api/cancel", {"task_id": j["task_id"]})[1]["ok"])
    check("dashboard rejects unknown agent", call("POST", "/api/task", {"agent_id": "zzz", "text": "x"})[0] == 400)
    check("api/events filters", all(e["agent_id"] == "cam-1" for e in call("GET", "/api/events?agent_id=cam-1&limit=5")[1]["events"]))
    check("api/state events=0", "events" not in call("GET", "/api/state?events=0")[1])

    # Antigravity hook (simulated payloads from the documented shape)
    hook = str(ROOT / "antigravity" / "agy_hook.py")
    ws = "/home/u/projects/my app"
    base_p = {"conversationId": "8591815f-ddcd-42e2-a41f-4d5a7a03091b", "workspacePaths": [ws], "transcriptPath": "/nonexistent"}
    def fire(ev, extra):
        p = subprocess.run([sys.executable, hook, ev], input=json.dumps({**base_p, **extra}), text=True, capture_output=True,
                           env=dict(env, AGENT_HUB_URL=BASE), timeout=15)
        return p.returncode, p.stdout.strip()
    check("hook PreInvocation", fire("PreInvocation", {"invocationNum": 0}) == (0, "{}"))
    check("hook PostToolUse", fire("PostToolUse", {"stepIdx": 4, "toolCall": {"name": "run_command", "args": {"CommandLine": "ls -la", "ApiKey": "sk-abcdefabcdefabcdefabcdef"}}}) == (0, "{}"))
    check("hook PostToolUse null toolCall skipped", fire("PostToolUse", {"toolCall": None}) == (0, "{}"))
    check("hook PostToolUse error", fire("PostToolUse", {"error": "boom", "toolCall": {"name": "write_to_file", "args": {"TargetFile": "/x.py"}}}) == (0, "{}"))
    check("hook Stop", fire("Stop", {"terminationReason": "NO_TOOL_CALL"}) == (0, '{"decision": "stop"}'))
    bad = subprocess.run([sys.executable, hook, "PostToolUse"], input="not json", text=True, capture_output=True, env=dict(env, AGENT_HUB_URL="http://127.0.0.1:1/x"))
    check("hook survives garbage + dead hub", bad.returncode == 0 and bad.stdout.strip() == "{}")

    agents = {a["id"]: a for a in json.loads(tool("list_agents")[1])["agents"]}
    agy = agents.get("agy-my-app")
    check("agy agent created, monitor_only", bool(agy) and agy["monitor_only"] and agy["online"] and agy["status"] == "idle")
    ev = json.loads(tool("read_events", {"agent_id": "agy-my-app"})[1])["events"]
    msgs = [e["msg"] for e in ev]
    check("agy events recorded", any("run_command: ls -la" in m for m in msgs) and any("finished" in m for m in msgs))
    check("secrets redacted", "sk-abcdef" not in json.dumps(ev) and any(e["level"] == "error" for e in ev))
    err, txt = tool("send_task", {"agent_id": "agy-my-app", "text": "do stuff"})
    check("send_task to monitor-only agent refused", err and "monitor-only" in txt)
    check("dashboard also refuses monitor-only", call("POST", "/api/task", {"agent_id": "agy-my-app", "text": "x"})[0] == 400)

    # MCP basics
    check("mcp initialize", mcp("initialize", {"protocolVersion": "2025-06-18"})["result"]["serverInfo"]["name"] == "agent-hub")
    check("mcp tools/list", {t["name"] for t in mcp("tools/list")["result"]["tools"]} >= {"list_agents", "read_events", "send_task"})
finally:
    hub.terminate()

print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
