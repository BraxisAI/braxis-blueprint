# The Job-Hunt Machine — how to run it

The job watcher scans free job boards hourly, LLM-scores every posting against
your resume (0-100 + a plain-English reason), and builds a desk you can open
in a browser. All free-tier, no paid APIs.

## 1. Fork + clone

```bash
git clone https://github.com/YOUR-USER/braxis-blueprint.git
cd braxis-blueprint
```

## 2. Drop in your resume

The watcher reads `data/job/resume.json`. There's a template:

```bash
cp data/job/resume.json.example data/job/resume.json
# then edit it — name, summary, skills, experience, preferences
```

The scoring categories live at the top of `scripts/job_watcher.py`
(`AI_RE`, `PM_RE`, `WINHALL_RE`, `BEACH_RE`, `REMOTE_RE`) — edit the
regexes to match what you're hunting.

## 3. Install + run

```bash
pip install -r requirements.txt   # if one exists; otherwise: pip install openai
python scripts/job_watcher.py
```

It scans HN "Who is hiring" (via Algolia), Remotive, and We Work Remotely,
scores each lead, and writes `data/job_leads.json`.

## 4. The desk

Serve the desk however you like:

```bash
python -m http.server 8090 --directory data
# open http://localhost:8090/jobs.html
```

(If `jobs.html` isn't in your fork, the `data/job_leads.json` file is the
data — the desk page is just a render of it.)

## 5. Hourly automation (optional)

```bash
crontab -e
# add:
# 45 * * * * cd /path/to/braxis-blueprint && python scripts/job_watcher.py
```

## What it does NOT do

- No auto-applying (you review the desk, you click apply — accounts stay safe)
- LinkedIn/Indeed need a logged-in browser session (the VM code covers the
  API-accessible boards only)
- It scores against YOUR resume — the better the resume, the better the scores

## Failure classes it was built around

- Duplicate-process cascades → run under `cronwrap.sh` (flock + timeout) if
  you automate it
- Dead/free-lane LLM endpoints → `llm_router.py` falls through providers with
  cooldowns; if every lane is down it raises instead of inventing scores
