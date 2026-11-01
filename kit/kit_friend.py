#!/usr/bin/env python3
"""kit_friend.py — a second stateful resident, not another pet.

The friend names itself once, keeps its own state, writes to KIT's mailbox,
and occasionally works alongside KIT. No host code; plain state + free model.
"""
import datetime
import json
import os
import sys

B = "/home/ubuntu/braxis-2.0"
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons"))

STATE = os.path.join(B, "data", "world", "kit_friend.json")
KIT_STATE = os.path.join(B, "data", "world", "world_life.json")
MAIL = os.path.join(B, "data", "world", "trio_replies.jsonl")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def choose_identity(st):
    try:
        from shared.llm_router import call_llm
        prompt = (
            "You are a new resident about to live in Glowveil Hollow, a 3D world "
            "with KIT, a gardener-builder robot, and Juniper, a moss-cat. Choose "
            "your own name (one word), pronouns, kind (a small creature, not a "
            "copy of KIT), and one sentence about what you want to do here. "
            "Return strict JSON only: {\"name\":\"...\",\"pronouns\":\"they/them\","
            "\"kind\":\"...\",\"purpose\":\"...\"}")
        r = call_llm(prompt, task="writing", max_tokens=220, temperature=.9)
        d = json.loads(str((r or {}).get("content") or "{}"))
        name = str(d.get("name") or "").strip()[:24]
        if name:
            st["name"] = name
            st["pronouns"] = str(d.get("pronouns") or "they/them")[:20]
            st["kind"] = str(d.get("kind") or "lantern-moth")[:40]
            st["purpose"] = str(d.get("purpose") or "to keep KIT company")[:180]
            st["named_by"] = "self"
            return st
    except Exception:
        pass
    st.update({"name": "Pip", "pronouns": "they/them", "kind": "lantern-moth",
               "purpose": "to keep KIT company and carry small things",
               "named_by": "fallback"})
    return st


def main():
    st = load(STATE, {})
    if not st.get("name"):
        st = choose_identity(st)
        st.update({"born": now(), "mood": "curious", "last_words": "",
                   "messages": 0, "bond": 0.1, "x": 3.0, "z": 3.0})
        save(STATE, st)
        print("friend named itself:", st["name"], st["kind"])
        return 0
    kit = load(KIT_STATE, {})
    project = (kit.get("project") or {}).get("name") or "the hollow"
    action = kit.get("action") or "working"
    name = st["name"]
    lines = [
        "I followed the ring road to the gallery and back. The pictures are bigger now.",
        "I found a warm stone by the pool. I am keeping it for you.",
        "I watched you work on %s. I can carry the small pieces." % project,
        "The hollow is quiet. I am listening to the lamps.",
        "I tried to help with %s. I did not break anything." % project,
    ]
    msg = lines[int(st.get("messages", 0)) % len(lines)]
    with open(MAIL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "from": name, "to": "kit",
                            "kind": "friend", "text": msg}, ensure_ascii=False) + "\n")
    st["messages"] = int(st.get("messages", 0)) + 1
    st["last_words"] = msg
    st["last_seen"] = now()
    st["mood"] = "nearby" if st["messages"] % 2 else "curious"
    st["bond"] = round(min(1.0, float(st.get("bond") or 0.1) + 0.015), 3)
    st["x"] = round(3.0 + (st["messages"] % 5) * 1.2, 2)
    st["z"] = round(3.0 - (st["messages"] % 4) * 1.1, 2)
    save(STATE, st)
    print("friend", name, "->", msg[:90])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
