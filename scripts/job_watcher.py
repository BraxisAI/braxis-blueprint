#!/usr/bin/env python3
"""08-22: JOB WATCHER — the founder's job-hunt machine.
Scans free job sources (HN Who's Hiring via Algolia, Remotive API, We Work
Remotely), regex-filters candidates, then LLM-matches each against his resume
(data/job/resume.json) → data/job_leads.json (the /ops/jobs.html desk).
Categories: ai_remote · pm_winhall · pm_beach · other
The PC leg (poster_agent/job_search.py) covers LinkedIn/Indeed via the
logged-in browser — this VM file covers the API-accessible boards.
Run: hourly :45 cron (cronwrap). Free-only — no paid APIs.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from shared import llm_router  # noqa: E402

LEADS = BASE / "data" / "job_leads.json"
RESUME = BASE / "data" / "job" / "resume.json"
LOG = BASE / "logs" / "job_watcher.log"
MAX_NEW_PER_RUN = 36
MAX_NEW_PER_SOURCE = 12
WINDOW_DAYS = 14
CAP_ROWS = 200

AI_RE = re.compile(r"\b(ai|llm|ml|machine learning|agent|automation|python|developer|engineer|gpt|chatbot|rag)\b", re.I)
PM_RE = re.compile(r"\b(property manager|property management|vacation rental|apartment manager|leasing)\b", re.I)
WINHALL_RE = re.compile(r"\b(winhall|manchester|stratton|londonderry|bondville)\b", re.I)
BEACH_RE = re.compile(r"\b(naples|sarasota|fort myers|st\.? pete|myrtle beach|charleston|savannah|hilton head|florida|south carolina|georgia)\b", re.I)
REMOTE_RE = re.compile(r"\b(remote|distributed|work from home|wfh|anywhere)\b", re.I)


def log(*a):
    try:
        with open(LOG, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] " + " ".join(map(str, a)) + "\n")
    except Exception:
        pass


def http_get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (braxis-job-watcher)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ---------------- sources ----------------

def hn_whois_hiring():
    """Newest 'Who is hiring?' thread → child comments, regex-filtered."""
    try:
        s = http_get("https://hn.algolia.com/api/v1/search?query=%22Who%20is%20hiring%3F%22&tags=story&hitsPerPage=5")
        stories = [h for h in s.get("hits", []) if (h.get("num_comments") or 0) > 100]
        if not stories:
            return []
        thread = http_get(f"https://hn.algolia.com/api/v1/items/{stories[0]['objectID']}")
        jobs = []
        for c in (thread.get("children") or []):
            text = (c.get("text") or "")
            txt = re.sub(r"<[^>]+>", " ", text)
            txt = re.sub(r"&#x27;|&quot;|&amp;", "'", txt)
            if AI_RE.search(txt) and REMOTE_RE.search(txt):
                jobs.append({
                    "source": "hn",
                    "title": txt.strip()[:160],
                    "company": "",
                    "location": "HN (remote)",
                    "url": f"https://news.ycombinator.com/item?id={c.get('id')}",
                    "body_raw": txt.strip()[:1500],
                })
        return jobs[:120]
    except Exception as e:
        log("hn err:", str(e)[:100])
        return []


def remotive():
    try:
        d = http_get("https://remotive.com/api/remote-jobs")
        out = []
        for j in (d.get("jobs") or []):
            hay = (j.get("title") or "") + " " + (j.get("category") or "")
            if AI_RE.search(hay):
                out.append({
                    "source": "remotive",
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location") or "Remote",
                    "url": j.get("url") or j.get("application_link") or "",
                    "body_raw": (j.get("description") or "")[:1500],
                })
        return out[:120]
    except Exception as e:
        log("remotive err:", str(e)[:100])
        return []


def wwr():
    out = []
    for q in ("ai", "llm", "automation", "property"):
        try:
            d = http_get(f"https://weworkremotely.com/remote-jobs.json?search={urllib.parse.quote(q)}")
            for j in (d.get("jobs") or []):
                out.append({
                    "source": "wwr",
                    "title": j.get("title", ""),
                    "company": j.get("company", {}).get("name", "") if isinstance(j.get("company"), dict) else "",
                    "location": j.get("region", "") or "Remote",
                    "url": j.get("url", ""),
                    "body_raw": (j.get("description", "") or "")[:1500],
                })
        except Exception as e:
            log(f"wwr {q} err:", str(e)[:80])
    return out[:120]


# ---------------- classify + match ----------------

def category_of(title, loc, body):
    if WINHALL_RE.search((title + " " + loc + " " + body)[:400]) and PM_RE.search(title):
        return "pm_winhall"
    if PM_RE.search(title) and BEACH_RE.search(loc):
        return "pm_beach"
    if AI_RE.search(title):
        return "ai_remote"
    return "other"


def strip_think(t):
    t = re.sub(r'<think>.*?</think>', '', t or '', flags=re.S)
    return t.strip()


def load_resume():
    if RESUME.exists():
        try:
            return RESUME.read_text()[:3000]
        except Exception:
            return ""
    return ""


def match_one(job, resume_txt):
    """LLM score vs the resume. Returns (score, why, category_override)."""
    cat = category_of(job.get("title", ""), job.get("location", ""), job.get("body_raw", ""))
    prompt = (
        "Job applicant resume:\n" + resume_txt + "\n\n"
        "Job posting:\nTITLE: " + job.get("title", "") +
        "\nCOMPANY: " + job.get("company", "") +
        "\nLOCATION: " + job.get("location", "") +
        "\nDESCRIPTION: " + (job.get("body_raw", "") or "")[:900] + "\n\n"
        "Judge the fit. Return ONLY JSON: {\"score\": <0-100>, \"why\": \"<one line>\", "
        "\"category\": \"ai_remote|pm_winhall|pm_beach|other\"}"
    )
    try:
        r = llm_router.call_llm(prompt, max_tokens=160, temperature=0.2,
                                json_schema={
                                    "type": "object",
                                    "properties": {
                                        "score": {"type": "number"},
                                        "why": {"type": "string"},
                                        "category": {"type": "string", "enum": ["ai_remote", "pm_winhall", "pm_beach", "other"]},
                                    },
                                    "required": ["score", "why", "category"],
                                })
        content = strip_think(r.get("content", ""))
        try:
            d = json.loads(content)
        except Exception:
            m = re.search(r'"score":\s*(\d+).*?"why":\s*"([^"]*)"', content, re.S)
            d = {"score": int(m.group(1)), "why": m.group(2), "category": cat} if m else {"score": 0, "why": "eval failed"}
        score = int(d.get("score", 0))
        why = (d.get("why") or "")[:200]
        cat = d.get("category") or cat
    except Exception as e:
        log("match err:", str(e)[:80])
        score, why = 0, "eval failed"
    return score, why, cat


# ---------------- main ----------------

def main():
    resume_txt = load_resume()
    if not resume_txt:
        log("no resume.json yet — run resume_build.py first")
        return 1
    leads = json.loads(LEADS.read_text()) if LEADS.exists() else {}
    rows = leads.get("jobs", [])
    seen = {r.get("url") for r in rows}
    cutoff = datetime.now() - timedelta(days=WINDOW_DAYS)
    rows = [r for r in rows if r.get("found_at", "") > cutoff.isoformat()[:19]] or rows[-CAP_ROWS:]

    cands = []
    for fn in (hn_whois_hiring, remotive):  # wwr 403s from the VM (datacenter IP) — PC-only source
        try:
            cands += fn()[:MAX_NEW_PER_SOURCE]
        except Exception as e:
            log(fn.__name__, "err:", str(e)[:80])

    # dedup + cap
    fresh = []
    for c in cands:
        if not c.get("url"):
            continue
        if c["url"] in seen:
            continue
        fresh.append(c)
        if len(fresh) >= MAX_NEW_PER_RUN:
            break
    log(f"candidates {len(cands)} -> new {len(fresh)}")

    added = 0
    for j in fresh:
        score, why, cat = match_one(j, resume_txt)
        row = {
            "title": (j.get("title") or "")[:150],
            "company": (j.get("company") or "")[:100],
            "location": (j.get("location") or "")[:80],
            "url": j["url"][:500],
            "body_raw": (j.get("body_raw") or "")[:1200],
            "source": j.get("source", ""),
            "category": cat,
            "score": score,
            "why": why,
            "status": "new",
            "found_at": datetime.now().isoformat(),
        }
        rows.insert(0, row)
        seen.add(j["url"])
        added += 1

    # 08-22d: score rows the ingest accepted without scoring (PC LinkedIn leg)
    scored = 0
    for r in rows:
        if r.get("why") == "pending eval" and scored < 20:
            r["body_raw"] = r.get("body_raw") or ""
            s, ww, cc = match_one(r, resume_txt)
            r["score"], r["why"], r["category"] = s, ww, cc
            scored += 1
    if scored:
        log(f"scored {scored} pending rows")

    rows = rows[:CAP_ROWS]
    leads["jobs"] = rows
    leads["updated_at"] = datetime.now().isoformat()
    LEADS.write_text(json.dumps(leads, indent=1))
    log(f"added {added}, total {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
