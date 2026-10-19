"""Tiny client for agent-hub. Stdlib only. Copy this file next to your agent.

    from agent_client import Hub
    hub = Hub(agent_id="cam-tester", name="Camera tester")     # reads AGENT_HUB_URL
    hub.report("starting", status="busy")
    hub.run(lambda task: do_work(task["text"]))                # polls, executes, posts results
"""
import json, os, time, urllib.request, urllib.error


class Hub:
    def __init__(self, agent_id, name=None, url=None, timeout=10):
        self.url = (url or os.environ["AGENT_HUB_URL"]).rstrip("/")
        self.agent_id, self.name, self.timeout = agent_id, name, timeout

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read() or b"{}")

    def report(self, msg=None, level="info", status=None, readonly=None, **data):
        """Send a log line and/or heartbeat. level: debug|info|warn|error. readonly=True marks a monitor-only agent."""
        return self._req("POST", "/report", {"agent_id": self.agent_id, "name": self.name, "status": status,
                                              "level": level, "msg": msg, "data": data or None,
                                              "readonly": readonly})

    def poll(self):
        """Claim pending tasks for this agent (also acts as a heartbeat)."""
        return self._req("GET", f"/tasks/{self.agent_id}")["tasks"]

    def finish(self, task_id, output="", ok=True):
        return self._req("POST", f"/tasks/{task_id}/result", {"status": "done" if ok else "failed", "output": output})

    def run(self, handler, interval=3.0):
        """Loop forever: poll for tasks, call handler(task)->str, post result. Survives hub restarts."""
        self.report("agent online", status="idle")
        while True:
            try:
                for t in self.poll():
                    self.report(f"running task #{t['id']}", status="busy")
                    try:
                        self.finish(t["id"], handler(t), ok=True)
                    except Exception as e:
                        self.finish(t["id"], f"{type(e).__name__}: {e}", ok=False)
                    self.report(status="idle")
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(interval)
