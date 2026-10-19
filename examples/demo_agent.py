#!/usr/bin/env python3
"""Demo agent: heartbeats, logs, and 'executes' tasks by echoing them. Replace handle() with real work."""
import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent_client import Hub

hub = Hub(agent_id=sys.argv[1] if len(sys.argv) > 1 else "demo", name="Demo agent")


def handle(task):
    hub.report(f"working on: {task['text'][:80]}")
    time.sleep(1)
    return f"echo: {task['text']}"


def chatter():
    n = 0
    while True:
        n += 1
        hub.report(f"tick {n}", level="debug")
        time.sleep(15)


threading.Thread(target=chatter, daemon=True).start()
hub.run(handle)
