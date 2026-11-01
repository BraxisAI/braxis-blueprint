#!/usr/bin/env python3
"""sales_scorecard.py — rank live offers by measured page traffic.

No invented conversion numbers. The only signals are the site's own 24h page
counts and whether the offer is deliverable. The sales director uses this to
pick what to promote instead of rotating blindly.
"""
import datetime
import json
import os
import re

B = "/home/ubuntu/braxis-2.0"
OFFERS = os.path.join(B, "data", "offers.json")
TRAFFIC = os.path.join(B, "data", "traffic.json")
GUIDES = os.path.join(B, "data", "world", "digital_guides")
OUT = os.path.join(B, "data", "world", "sales_scorecard.json")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:60]


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def main():
    d = _load(OFFERS, {})
    rows = d.get("live") if isinstance(d, dict) else []
    traffic = _load(TRAFFIC, {})
    pages = dict(traffic.get("top_pages") or [])
    guides = {}
    try:
        for f in os.listdir(GUIDES):
            if not f.endswith(".json"):
                continue
            g = _load(os.path.join(GUIDES, f), {})
            if g.get("name"):
                guides[g["name"]] = g.get("slug") or slug(g["name"])
    except Exception:
        pass
    ranked = []
    for o in rows or []:
        if not isinstance(o, dict):
            continue
        name = str(o.get("name") or "").strip()
        if not name:
            continue
        s = guides.get(name) or slug(name)
        hits = int(pages.get("/builds/%s/" % s, 0) or 0)
        hits += int(pages.get("/kit/guides/%s/" % s, 0) or 0)
        # deliverable products matter even before traffic; page hits lead.
        score = hits + (5 if hits else 0) + (2 if o.get("kind") == "digital_guide" else 0)
        ranked.append({
            "name": name, "price": o.get("price"), "url": o.get("url"),
            "kind": o.get("kind"), "page_hits": hits, "score": score,
            "slug": s,
        })
    ranked.sort(key=lambda x: (-x["score"], x["name"]))
    out = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "window": traffic.get("window") or "24h",
           "ranking": ranked, "source": "site 24h page counts; no fabricated rates"}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, OUT)
    print("sales scorecard: %d offers, top=%s (%d hits)"
          % (len(ranked), ranked[0]["name"] if ranked else "none",
             ranked[0]["page_hits"] if ranked else 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
