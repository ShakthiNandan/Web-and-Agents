#!/usr/bin/env python3
"""Antigravity hook -> agent-hub reporter. Stdlib only. Never blocks or breaks the IDE agent.

Usage (set up by install_antigravity.py):  python agy_hook.py <PreInvocation|PostToolUse|Stop>
Antigravity pipes a JSON payload on stdin; this posts a log line to the hub and prints the
minimal JSON response Antigravity expects. Any error is swallowed: worst case, nothing is reported.

Hub URL: $AGENT_HUB_URL, else "url" in ~/.agent-hub/client.json (written by the installer).
Optional env: AGENT_HUB_AGY_ID (override agent id), AGENT_HUB_AGY_TAIL=1 (attach last transcript lines on Stop).
"""
import json, os, re, sys, urllib.request
from pathlib import Path

HOME = Path(os.environ.get("AGENT_HUB_HOME", Path.home() / ".agent-hub"))
SECRET_KEY = re.compile(r"key|token|secret|passw|auth|cookie|credential", re.I)
SECRET_VAL = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})")
SUMMARY_KEYS = ("toolSummary", "toolAction", "CommandLine", "TargetFile", "AbsolutePath", "SearchPath",
                "Query", "DirectoryPath", "Url", "File", "Path")


def hub_url():
    u = os.environ.get("AGENT_HUB_URL")
    if not u:
        try: u = json.loads((HOME / "client.json").read_text())["url"]
        except Exception: return None
    return u.rstrip("/")


def clean(v, n=400):
    if isinstance(v, str):
        return SECRET_VAL.sub("[redacted]", v)[:n]
    if isinstance(v, dict):
        return {k: ("[redacted]" if SECRET_KEY.search(str(k)) else clean(x, n)) for k, x in list(v.items())[:30]}
    if isinstance(v, list):
        return [clean(x, n) for x in v[:20]]
    return v


def agent_for(p):
    forced = os.environ.get("AGENT_HUB_AGY_ID")
    ws = (p.get("workspacePaths") or [None])[0]
    base = Path(ws).name if ws else ""
    slug = re.sub(r"[^A-Za-z0-9._:-]", "-", base or (p.get("conversationId") or "unknown")[:8]).strip("-")
    return (forced or f"agy-{slug}")[:64], f"Antigravity: {base or 'workspace'}"


def tail(path, n=3, width=1500):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 60_000))
            lines = f.read().decode("utf-8", "replace").splitlines()[-n:]
        return [clean(l, width) for l in lines]
    except Exception:
        return None


def build(event, p):
    """-> (msg, level, status, data) or None to skip."""
    conv = (p.get("conversationId") or "")[:8]
    if event == "PreInvocation":
        n = p.get("invocationNum", 0)
        if n == 0:
            return "Antigravity run started", "info", "busy", {"conv": conv}
        return f"model call #{n}", "debug", "busy", {"conv": conv}
    if event == "PostToolUse":
        tc = p.get("toolCall")
        if not tc:
            return None
        args = tc.get("args") or {}
        summary = next((str(args[k]) for k in SUMMARY_KEYS if args.get(k)), "")
        err = p.get("error") or ""
        msg = f"{tc.get('name', 'tool')}: {clean(summary, 160)}".rstrip(": ")
        if err:
            msg += f" [error: {clean(str(err), 200)}]"
        return msg, ("error" if err else "info"), "busy", {"conv": conv, "step": p.get("stepIdx"), "tool": tc.get("name"), "args": clean(args)}
    if event == "Stop":
        reason, err = p.get("terminationReason", "?"), p.get("error") or ""
        data = {"conv": conv, "reason": reason, "transcript": p.get("transcriptPath")}
        if os.environ.get("AGENT_HUB_AGY_TAIL") == "1" and p.get("transcriptPath"):
            data["transcript_tail"] = tail(p["transcriptPath"])
        return (f"Antigravity run finished ({reason})" + (f" [error: {clean(str(err), 200)}]" if err else ""),
                "error" if err else "info", "idle", data)
    return None


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    try:
        raw = sys.stdin.read()
        p = json.loads(raw) if raw.strip() else {}
        url, r = hub_url(), build(event, p)
        if url and r:
            msg, level, status, data = r
            aid, name = agent_for(p)
            body = json.dumps({"agent_id": aid, "name": name, "status": status, "level": level, "msg": msg,
                               "data": data, "readonly": True}).encode()
            req = urllib.request.Request(url + "/report", data=body, method="POST", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass  # never interfere with the IDE agent
    print('{"decision": "stop"}' if event == "Stop" else "{}")


if __name__ == "__main__":
    main()
