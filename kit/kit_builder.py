#!/usr/bin/env python3
"""kit_builder.py — Echo builds what KIT asks for.

KIT's own code lane is a small free model, and a small model writes small,
sometimes broken programs. This lane gives the coding request to the empire's
builder (Echo) and keeps the boundary in the sandbox: Echo writes code, the
code runs in the disposable container, and only a working program is returned
to KIT. No host execution.

Requests:  data/world/kit_build_requests.jsonl  (written by KIT)
Replies:   data/world/trio_replies.jsonl        (read by KIT's mailbox)
"""
import datetime
import json
import os
import re
import sys
import time
import uuid

B = "/home/ubuntu/braxis-2.0"
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons"))
sys.path.insert(0, os.path.join(B, "weapons", "world"))

REQ = os.path.join(B, "data", "world", "kit_build_requests.jsonl")
REPLY = os.path.join(B, "data", "world", "trio_replies.jsonl")
DONE = os.path.join(B, "data", "world", "kit_build_done.json")
STATE = os.path.join(B, "data", "world", "kit_builder_state.json")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _clean_code(raw):
    s = str(raw or "").strip()
    s = re.sub(r"^```(?:python|py)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    lines = s.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^(import|from|def|print|#|[A-Za-z_][A-Za-z0-9_]*\s*=)",
                    line.strip()):
            return "\n".join(lines[i:]).strip()[:6000]
    return s[:6000]


def _ask_code(goal, error=""):
    prompt = (
        "You are Echo, the builder for the Braxis empire. KIT, a small "
        "garden-robot, asked for a tiny Python 3 program. Goal: %s.\n\n"
        "Write at most 30 lines of Python 3 using only the standard library. "
        "No network, no files, no input(), no subprocess. It must print a short, "
        "readable result (5-15 lines). Return ONLY the code, no markdown, no "
        "explanation.%s" % (goal, ("\nThe previous attempt failed:\n" + error[:800])
                             if error else ""))
    try:
        from shared.llm_router import call_llm
        r = call_llm(prompt, task="writing", max_tokens=700, temperature=.35)
        return _clean_code((r or {}).get("content") or ""), str((r or {}).get("model") or "")
    except Exception as e:
        return "", "%s: %s" % (type(e).__name__, str(e)[:120])


def build_code(goal):
    from weapons import kit_sandbox
    code, model = "", ""
    last = ""
    for attempt in range(3):
        code, model = _ask_code(goal, last)
        if not code:
            last = "the model returned no code"
            continue
        res = kit_sandbox.run(code, timeout=6)
        if res.get("ok"):
            return {"ok": True, "code": code, "output": str(res.get("stdout") or ""),
                    "model": model, "attempts": attempt + 1,
                    "sandbox": {k: res.get(k) for k in
                                ("returncode", "timed_out", "seconds")}}
        last = str(res.get("stdout") or res.get("stderr") or res.get("error") or "failed")
    return {"ok": False, "code": code, "output": last, "model": model,
            "attempts": 3, "error": "no working program after 3 attempts"}


def main():
    state = _load(STATE, {})
    done = set(state.get("done") or [])
    try:
        rows = [json.loads(l) for l in open(REQ, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        rows = []
    pending = [r for r in rows if r.get("id") and r.get("id") not in done]
    if not pending:
        print("kit_builder: no requests")
        return 0
    for req in pending[:2]:
        rid = str(req.get("id"))
        goal = str(req.get("goal") or "a small pattern in the garden")[:200]
        kind = str(req.get("kind") or "code")
        print("kit_builder: %s %s" % (rid, goal[:80]))
        if kind == "action":
            # The declarative plugin lane remains KIT-owned; Echo only builds code.
            result = {"ok": False, "error": "action requests are handled by KIT's define action"}
        else:
            result = build_code(goal)
        reply = {"ts": now(), "from": "echo-builder", "to": "kit",
                 "kind": "build", "request_id": rid, "goal": goal,
                 "code": result.get("code") or "",
                 "output": result.get("output") or "",
                 "ok": bool(result.get("ok")),
                 "error": result.get("error") or "",
                 "model": result.get("model") or "",
                 "attempts": result.get("attempts")}
        _append(REPLY, reply)
        done.add(rid)
        state["done"] = sorted(done)[-200:]
        state["last"] = {"ts": now(), "request": rid, "ok": reply["ok"]}
        _save(STATE, state)
        print("kit_builder: replied %s ok=%s" % (rid, reply["ok"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
