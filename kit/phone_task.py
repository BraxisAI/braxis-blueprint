#!/usr/bin/env python3
"""phone_task.py — the empire's queue for ARTEMIS phone jobs.

ARTEMIS runs on the PC because that is where the USB phone lives. The empire
runs on the VM, so this file lives on the VM and is the hand-off point:

  enqueue  -> a pending job (from Vesper, MAYA, a cron, or the founder)
  claim    -> the PC runner atomically takes the oldest pending job
  complete -> the PC runner writes the outcome back
  status   -> anybody can inspect the queue

The queue is a single JSON file with an flock, so a claim cannot double-run a
job. Tasks are deliberately small and human-readable; credentials and banking
are refused here, before they reach the phone.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import uuid
import fcntl

B = "/home/ubuntu/braxis-2.0"
QUEUE = os.path.join(B, "data", "world", "phone_tasks.json")
LOCK = QUEUE + ".lock"
MAX_GOAL = 400

# The spare phone is not an identity or a bank. Refuse these before ARTEMIS
# ever sees them. This is a safety rail, not a content filter.
FORBIDDEN = re.compile(
    r"\b(bank|banking|password|passcode|seed phrase|private key|wallet|"
    r"credit card|debit card|social security|ssn|payment|paypal|venmo|"
    r"gmail|outlook|email|mail app|factory reset|wipe|uninstall|"
    r"delete account|change password)\b", re.I)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _empty():
    return {"next_id": 1, "tasks": []}


def _load():
    try:
        with open(QUEUE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("tasks"), list):
            return d
    except Exception:
        pass
    return _empty()


def _save(d):
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    tmp = QUEUE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    os.replace(tmp, QUEUE)


def _locked():
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    f = open(LOCK, "a+")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def enqueue(goal, source="empire", kind="task"):
    goal = " ".join(str(goal or "").split())
    if not goal:
        raise SystemExit("empty goal")
    if len(goal) > MAX_GOAL:
        raise SystemExit("goal is longer than %d chars" % MAX_GOAL)
    m = FORBIDDEN.search(goal)
    if m:
        raise SystemExit("refused: %r is off-limits on the spare phone" % m.group(0))
    with _locked() as lock:
        d = _load()
        tid = str(d.get("next_id") or 1)
        d["next_id"] = int(tid) + 1
        task = {"id": tid, "goal": goal, "source": str(source or "empire")[:80],
                "kind": str(kind or "task")[:20], "status": "pending",
                "created": _now(), "started": None, "finished": None,
                "worker": None, "result": None, "log": None,
                "image_url": None, "private_path": None}
        d["tasks"].append(task)
        _save(d)
    print(tid)
    return int(tid)


def claim(worker="pc"):
    with _locked() as lock:
        d = _load()
        for task in d["tasks"]:
            if task.get("status") == "pending":
                task.update(status="running", worker=str(worker)[:80], started=_now())
                _save(d)
                print(json.dumps(task, ensure_ascii=False))
                return 0
    print("{}")
    return 0


def complete(task_id, status, result, log, image_url=None, private_path=None):
    status = "done" if str(status).lower() in ("done", "ok", "success") else "error"
    payload = {"status": status, "result": str(result or "")[:4000],
               "log": str(log or "")[:2000], "finished": _now(),
               "image_url": image_url, "private_path": private_path}
    with _locked() as lock:
        d = _load()
        for task in d["tasks"]:
            if str(task.get("id")) == str(task_id):
                task.update(payload)
                _save(d)
                print(json.dumps(task, ensure_ascii=False))
                return 0
        raise SystemExit("task not found: %s" % task_id)


def status():
    d = _load()
    tasks = d.get("tasks") or []
    counts = {}
    for t in tasks:
        counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
    print(json.dumps({"queue": QUEUE, "next_id": d.get("next_id"), "counts": counts,
                      "tasks": tasks[-20:]}, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enqueue", metavar="GOAL")
    ap.add_argument("--source", default="empire")
    ap.add_argument("--kind", default="task")
    ap.add_argument("--claim", action="store_true")
    ap.add_argument("--worker", default="pc")
    ap.add_argument("--complete-json", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.enqueue:
        return enqueue(a.enqueue, a.source, a.kind)
    if a.claim:
        return claim(a.worker)
    if a.complete_json:
        payload = json.load(sys.stdin)
        return complete(payload.get("id"), payload.get("status", "error"),
                        payload.get("result"), payload.get("log"),
                        payload.get("image_url"), payload.get("private_path"))
    if a.status:
        return status()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
