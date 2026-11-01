#!/usr/bin/env python3
"""sales_loop.py — warm sales follow-up only.

Cold outbound is retired. This lane no longer selects cold leads or queues
unsolicited email. It watches for people who already replied / showed intent,
records the warm lead for a human follow-up, and leaves the automated selling
to sales_content (which uses the live scorecard and platform caps).
"""
import argparse
import datetime
import json
import os
import sqlite3

B = "/home/ubuntu/braxis-2.0"
DB = os.path.join(B, "data", "dashboard.db")
OUT = os.path.join(B, "data", "world", "warm_sales.jsonl")


def _warm(limit=10):
    c = sqlite3.connect(DB, timeout=20)
    c.execute("PRAGMA busy_timeout=20000")
    rows = c.execute(
        "SELECT r.id, r.from_email, r.subject, r.snippet, r.purchase_intent "
        "FROM replies r WHERE r.kind NOT IN ('auto','bounce') "
        "AND (r.purchase_intent=1 OR r.handled_by_human=0) "
        "ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    rows = _warm()
    if not rows:
        print("sales_loop: no warm replies; live selling is sales_content")
        return 0
    for rid, email, subject, snippet, intent in rows:
        rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "reply_id": rid, "email": email, "subject": subject,
               "snippet": str(snippet or "")[:500], "purchase_intent": intent,
               "status": "warm_needs_human"}
        print("WARM", rid, email, subject)
        if not a.dry:
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("sales_loop: %d warm lead(s); no cold email sent" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
