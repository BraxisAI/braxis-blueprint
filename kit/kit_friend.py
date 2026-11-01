#!/usr/bin/env python3
"""kit_friend.py — a second resident with its own stance.

Lumen names itself and lives somewhere else in the hollow. It is not assigned
to KIT. Its messages start wary; affinity rises only when KIT chooses to talk
to it (via the `talk to Lumen` action), and falls when KIT ignores it. Friendship
is earned, not scripted.
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
INBOX = os.path.join(B, "data", "world", "kit_friend_inbox.jsonl")
PLACES = [(-70, 115), (22, 22), (-95, -55), (-100, 45), (42, -12)]


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
            "with KIT, a gardener-builder robot. Choose your own name (one word), "
            "pronouns, kind (a small creature, not a copy of KIT), and one neutral "
            "sentence about what you are here to find out. Do not call KIT a friend; "
            "you have not met yet. Return strict JSON only: {\"name\":\"...\","
            "\"pronouns\":\"they/them\",\"kind\":\"...\",\"purpose\":\"...\"}")
        r = call_llm(prompt, task="writing", max_tokens=240, temperature=.9)
        d = json.loads(str((r or {}).get("content") or "{}"))
        name = str(d.get("name") or "").strip()[:24]
        if name:
            st.update({"name": name,
                       "pronouns": str(d.get("pronouns") or "they/them")[:20],
                       "kind": str(d.get("kind") or "lantern-moth")[:40],
                       "purpose": str(d.get("purpose") or "to find out what this place is")[:180],
                       "named_by": "self"})
            return st
    except Exception:
        pass
    st.update({"name": "Pip", "pronouns": "they/them", "kind": "lantern-moth",
               "purpose": "to find out what this place is", "named_by": "fallback"})
    return st


def main():
    st = load(STATE, {})
    if not st.get("name"):
        st = choose_identity(st)
        st.update({"born": now(), "mood": "wary", "stance": "wary", "affinity": 0.0,
                   "last_words": "", "messages": 0, "bond": 0.0,
                   "x": PLACES[0][0], "z": PLACES[0][1]})
        save(STATE, st)
        print("friend named itself:", st["name"], st["kind"])
        return 0
    # KIT's choice to talk is the only thing that raises affinity.
    try:
        lines = [l for l in open(INBOX, encoding="utf-8").read().splitlines() if l.strip()]
    except Exception:
        lines = []
    cursor = int(st.get("inbox_cursor") or 0)
    new = lines[cursor:]
    aff = float(st.get("affinity") or 0.0)
    if new:
        aff = min(1.0, aff + 0.16 * len(new))
        st["last_kit_words"] = new[-1][:240]
    else:
        aff = max(0.0, aff - 0.01)
    st["inbox_cursor"] = len(lines)
    stance = ("wary" if aff < 0.25 else "curious" if aff < 0.6 else "friendly")
    st["stance"] = stance
    st["affinity"] = round(aff, 3)
    st["bond"] = st["affinity"]
    name = st["name"]
    if stance == "wary":
        msgs = ["I am still deciding what to make of this place.",
                "I watched the road from the orchard. Nobody saw me.",
                "Do not assume we are friends yet. I am listening."]
    elif stance == "curious":
        msgs = ["I found the gallery. The pictures are bigger than I expected.",
                "I followed the ring road until the lamps came on.",
                "I am beginning to think this hollow has more rooms than it shows."]
    else:
        msgs = ["I left a warm stone by your door. You do not have to keep it.",
                "I walked the ring road with you in mind.",
                "The orchard is better when someone else knows where I am."]
    msg = msgs[int(st.get("messages", 0)) % len(msgs)]
    x, z = PLACES[int(st.get("messages", 0)) % len(PLACES)]
    with open(MAIL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "from": name, "to": "kit",
                            "kind": "friend", "text": msg,
                            "x": x, "z": z, "stance": stance,
                            "affinity": st["affinity"]},
                           ensure_ascii=False) + "\n")
    st["messages"] = int(st.get("messages", 0)) + 1
    st["last_words"] = msg
    st["last_seen"] = now()
    st["mood"] = stance
    st["x"], st["z"] = x, z
    save(STATE, st)
    print("friend", name, "(%s, %.2f) -> %s" % (stance, aff, msg[:90]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
