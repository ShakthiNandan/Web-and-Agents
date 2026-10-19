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


def inspect_transcript(path):
    if not path:
        return None, None, None
    candidates = [path.replace("transcript_full.jsonl", "transcript.jsonl"), path]
    target = next((c for c in candidates if os.path.exists(c)), None)
    if not target:
        return None, None, None
    try:
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        goal, last_action, thought = "", "", ""
        for item in reversed(lines):
            if not goal and item.get("type") == "USER_INPUT":
                c = str(item.get("content", ""))
                if "<USER_REQUEST>" in c:
                    c = c.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0]
                goal = re.sub(r"\s+", " ", c).strip()[:140]
            if not last_action and item.get("tool_calls"):
                tc = item["tool_calls"][0]
                name = tc.get("name", "")
                args = tc.get("args", {})
                t_arg = args.get("toolSummary") or args.get("TargetFile") or args.get("AbsolutePath") or args.get("CommandLine") or ""
                if t_arg:
                    t_arg = str(t_arg).replace("\\", "/").split("/")[-1][:40]
                last_action = f"{name} {t_arg}".strip()
            if not thought and item.get("thinking"):
                thought = re.sub(r"\s+", " ", str(item["thinking"])).strip()[:120]
            if goal and last_action:
                break
        return goal or None, last_action or None, thought or None
    except Exception:
        return None, None, None


def build(event, p):
    """-> (msg, level, status, data) or None to skip."""
    conv = (p.get("conversationId") or "")[:8]
    tpath = p.get("transcriptPath")
    goal, last_action, thought = inspect_transcript(tpath)

    if event == "PreInvocation":
        n = p.get("invocationNum", 0)
        model = p.get("modelName", "")
        parts = []
        if last_action:
            parts.append(last_action)
        elif n == 0:
            parts.append("Run started")
        else:
            parts.append(f"Turn #{n}")
        if goal:
            parts.append(f"Task: {goal}")
        msg = " | ".join(parts) if parts else f"model call #{n}"
        data = {"conv": conv, "step": n, "goal": goal, "action": last_action, "thought": thought, "model": model, "transcript": tpath}
        return msg, "info", "busy", data

    if event == "PostToolUse":
        tc = p.get("toolCall")
        if not tc:
            if last_action:
                return last_action, "info", "busy", {"conv": conv, "goal": goal, "action": last_action}
            return None
        args = tc.get("args") or {}
        summary = next((str(args[k]) for k in SUMMARY_KEYS if args.get(k)), "")
        err = p.get("error") or ""
        msg = f"{tc.get('name', 'tool')}: {clean(summary, 160)}".rstrip(": ")
        if err:
            msg += f" [error: {clean(str(err), 200)}]"
        if goal:
            msg += f" | Task: {goal[:60]}"
        return msg, ("error" if err else "info"), "busy", {"conv": conv, "step": p.get("stepIdx"), "tool": tc.get("name"), "args": clean(args), "goal": goal}

    if event == "Stop":
        reason, err = p.get("terminationReason", "?"), p.get("error") or ""
        data = {"conv": conv, "reason": reason, "transcript": tpath, "goal": goal, "last_action": last_action}
        stop_msg = f"Antigravity run finished ({reason})"
        if err:
            stop_msg += f" [error: {clean(str(err), 200)}]"
        if goal:
            stop_msg += f" | Task: {goal[:60]}"
        return stop_msg, ("error" if err else "info"), "idle", data

    return None


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    try:
        raw = sys.stdin.read()
        try:
            with open(HOME / f"payload_{event}.json", "w", encoding="utf-8") as _df:
                _df.write(raw)
        except Exception: pass
        p = json.loads(raw) if raw.strip() else {}
        url, r = hub_url(), build(event, p)
        if url and r:
            msg, level, status, data = r
            aid, name = agent_for(p)
            body = json.dumps({"agent_id": aid, "name": name, "status": status, "level": level, "msg": msg,
                               "data": data, "readonly": True}).encode()
            req = urllib.request.Request(url + "/report", data=body, method="POST", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2).read()
    except Exception as e:
        try:
            with open(HOME / "hook-errors.log", "a", encoding="utf-8") as _ef:
                _ef.write(f"{type(e).__name__}: {e}\n")
        except Exception:
            pass  # never interfere with the IDE agent
    print('{"decision": "stop"}' if event == "Stop" else "{}")


if __name__ == "__main__":
    main()
