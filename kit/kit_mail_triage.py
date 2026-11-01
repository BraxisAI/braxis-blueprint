#!/usr/bin/env python3
"""kit_mail_triage.py — close KIT's mailbox loop.

KIT writes to `data/world/kit_mailbox.jsonl` and reads
`data/world/trio_replies.jsonl`, but nothing read the mailbox. This replies
to the latest new note as Vesper, so KIT hears the trio instead of talking
into a file.
"""
import datetime
import json
import os
import re
import sys

B = "/home/ubuntu/braxis-2.0"
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons"))

MAIL_IN = os.path.join(B, "data", "world", "kit_mailbox.jsonl")
MAIL_OUT = os.path.join(B, "data", "world", "trio_replies.jsonl")
STATE = os.path.join(B, "data", "world", "kit_mail_triage_state.json")


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


def main():
    try:
        rows = [json.loads(l) for l in open(MAIL_IN, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        print("kit_mail_triage: no mailbox")
        return 0
    st = load(STATE, {})
    cursor = int(st.get("cursor") or 0)
    if len(rows) <= cursor:
        print("kit_mail_triage: nothing new")
        return 0
    note = rows[-1]
    if note.get("from") != "Kit" or note.get("to") != "trio":
        save(STATE, {"cursor": len(rows), "ts": now()})
        print("kit_mail_triage: skipped non-KIT note")
        return 0
    text = str(note.get("text") or "").strip()[:400]
    # Deterministic and grounded in the note. An LLM reply here invented
    # numbers and internal states ("110 found patterns") that were not in the
    # estate; KIT reads these lines as truth, so do not let the model improvise.
    m = re.search(r"I finished (.+?) \((.+?), level (\d+)\) at (.+?)\.",
                  text, re.I)
    if m:
        name, kind, level, site = m.group(1), m.group(2), m.group(3), m.group(4)
        reply = ("I saw %s land at %s, KIT. Let it stand for a day and watch "
                 "who stops." % (name, site))
    elif "?" in text:
        reply = ("I heard the question, KIT. I do not have a better answer than "
                 "the world does; try it and watch what changes.")
    else:
        reply = "I heard you, KIT. Keep building; the hollow is the proof."
    reply = reply.strip()[:600]
    rec = {"ts": now(), "from": "vesper", "to": "kit", "kind": "reply",
           "text": reply, "reply_to": note.get("ts")}
    with open(MAIL_OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    save(STATE, {"cursor": len(rows), "ts": now(), "last_reply": reply[:200]})
    print("kit_mail_triage: replied to %s" % str(note.get("ts")))
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
