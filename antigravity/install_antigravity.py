#!/usr/bin/env python3
"""Wire Antigravity (IDE / CLI / app) to agent-hub via hooks. Stdlib only, idempotent.

  python install_antigravity.py                  # global: ~/.gemini/config/hooks.json (all workspaces)
  python install_antigravity.py --workspace .    # only this workspace: ./.agents/hooks.json
  python install_antigravity.py --uninstall      # remove the "agent-hub" entry
  python install_antigravity.py --test           # send a test event to the hub

Hooks post to the LOCAL hub (127.0.0.1), not through Funnel. Existing hooks.json entries are preserved
(a .bak copy is written first). Restart Antigravity afterwards, then ask it: "Which hooks are installed?"
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

HOME = Path(os.environ.get("AGENT_HUB_HOME", Path.home() / ".agent-hub"))
KEY = "agent-hub"


SYS_PY = f'"{sys.executable}"' if " " in sys.executable else sys.executable


def local_url(port):
    tok = os.environ.get("AGENT_HUB_TOKEN") or (HOME / "token").read_text().strip()
    return f"http://127.0.0.1:{port}/{tok}"


def entry(hook):
    cmd = lambda ev: f'{SYS_PY} "{hook}" {ev}'
    return {"enabled": True,
            "PreInvocation": [{"type": "command", "command": cmd("PreInvocation"), "timeout": 5}],
            "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd("PostToolUse"), "timeout": 5}]}],
            "Stop": [{"type": "command", "command": cmd("Stop"), "timeout": 5}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", help="install into <dir>/.agents/hooks.json instead of the global file")
    ap.add_argument("--port", type=int, default=8080, help="local hub port (default 8080)")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    target = (Path(a.workspace).resolve() / ".agents" / "hooks.json") if a.workspace else (Path.home() / ".gemini" / "config" / "hooks.json")
    HOME.mkdir(parents=True, exist_ok=True)
    hook = HOME / "agy_hook.py"

    if a.test:
        p = subprocess.run([sys.executable, str(hook), "PostToolUse"], text=True, capture_output=True, timeout=15,
                           input=json.dumps({"conversationId": "test-0000", "workspacePaths": [str(Path.cwd())],
                                             "toolCall": {"name": "install_test", "args": {"toolSummary": "hello from install_antigravity --test"}}}))
        print("hook stdout:", p.stdout.strip() or "(none)", "\nNow check the dashboard / list_agents for an 'agy-*' agent.")
        return

    data = {}
    if target.exists():
        try: data = json.loads(target.read_text() or "{}")
        except Exception: sys.exit(f"{target} is not valid JSON; fix or move it first")
        shutil.copy2(target, str(target) + ".bak")

    if a.uninstall:
        if data.pop(KEY, None) is not None:
            target.write_text(json.dumps(data, indent=2)); print(f"removed '{KEY}' from {target}")
        else:
            print(f"nothing to remove in {target}")
        return

    shutil.copy2(Path(__file__).with_name("agy_hook.py"), hook)
    client = HOME / "client.json"
    client.write_text(json.dumps({"url": local_url(a.port)}))
    try: os.chmod(client, 0o600)
    except OSError: pass
    data[KEY] = entry(hook)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2))
    print(f"installed hooks -> {target}\nhook script     -> {hook}\nhub url saved   -> {client} (contains your token; keep private)")
    print("Next: restart Antigravity, run any agent task, then open the dashboard. Test now with: python install_antigravity.py --test")


if __name__ == "__main__":
    main()