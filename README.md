# BRAXIS BLUEPRINT — The $0 AI Empire Playbook

**One founder. One year. Zero dollars on APIs. 180 scheduled jobs across 7 services, 43 free LLM lanes, 2,100+ songs, a living 3D city with persistent AI citizens, and a content machine that runs itself — built entirely on free tiers, open weights, and stubbornness.**

This repo is the honest, unpolished blueprint: the actual scripts that run the empire, the architecture that holds it together, and the failure classes that almost killed it — so you don't have to learn them the way I did.

> I'm not selling you a course. I'm handing you the scripts.

> **Want this run for your business instead of built by you?** A $25 same-day *opportunity brief*: three overlooked revenue openings for your shop, ranked by effort vs payoff, with a 7-day plan. **[Get yours →](https://buy.stripe.com/aFafZhgVaeSqa0G34F7ES1V)**

## The Empire in Numbers

These are counted, not estimated. Where a number went backwards, it says so.

- **180 scheduled jobs across 7 services** — a CEO/chief-of-staff decision duo, plus a city of persistent citizens with memory, reflection, and a self-improvement loop
- **43 free LLM lanes** — a router that falls through providers (cooldowns, dead-model tracking, a self-optimizing tuner) without spending a dollar on APIs
- **2,100+ songs, 5 video styles, daily content across 8 platforms** — one pipeline, zero budget
- **Cold email: 45/day at its peak, then it fell to 1/day and I stopped the lane.** The mechanism is still in here and still documented; the volume is not what it was. I would rather show you the curve than a number I can no longer back up
- **11 live Stripe products** with automated fulfillment
- **A 3D world** (braxisai.com/world) where the mayor is an LLM agent and the citizens self-modify
- **3 verified backup copies** of everything, nightly

## Live Demos
- The living system map: https://braxisai.com/map — the whole estate, live
- The world: https://braxisai.com/world/
- The talking mayor: https://braxisai.com/avatar/
- The music machine: https://braxisai.com/music/
- The resume the machine built for its founder: https://braxisai.com/resume/

## What's In Here
| File | What it teaches |
|---|---|
| `llm_router.py` | The dispatcher: task-chained fallbacks, cooldowns, dead-model tracking, a self-optimizing model tuner, free-only enforcement |
| `cronwrap.sh` | The automation discipline: flock-based single-instance guards + timeout kill — the fix for the duplicate-process cascade class |
| `backup.sh` + `backup_upload.py` | The 3-copy safety net: local rotation + object-storage offsite + verified restores |
| `om_daily.py` | The daily content machine (renders, queues, publishes) |
| `tiktok_autoposter.py` | The cookie-session social lane pattern — and a lesson: `import shutil` matters (a missing import silently killed a lane for days) |
| `job_watcher.py` | The job-hunt machine: scan free boards → LLM-score each posting against a resume → desk. **Run it:** [docs/job-hunt-machine.md](docs/job-hunt-machine.md) — fork, drop your resume into `data/job/resume.json` (template included), run it |
| `vesper_avatar_say.py` | A talking 3D avatar with word-timed lip-sync, zero API keys (edge-tts `boundary="WordBoundary"` gotcha included) |
| `resume_build.py` | The living-map-as-resume pattern: the empire's own state becomes a job application |

## Architecture (the 30-second version)
```
VM (Oracle ARM free tier, 24GB)
├── 43 free LLM lanes (Groq, NVIDIA NIM, Gemini, Mistral, Zhipu, OpenRouter :free, local Ollama)
│   └── llm_router.py — chains with cooldowns/failover/optimizer (free-only, fail-closed)
├── SQLite + WAL (single-writer, flock-guarded — the lock-class fixes)
├── ~180 cron jobs, all wrapped in cronwrap.sh (flock + timeout)
├── systemd services: webhook, dashboard, nginx, the duo loops
├── nightly 3-copy backups (local + OCI bucket)
└── PC (residential IP): the sender, the browser lanes, the GPU
```

The stack is watched, not assumed: a probe runs every 30 minutes and records what
actually served. Over the last 24h that was 4,016 calls, a 30.7% attempt-failure
rate and a 1.6% request-failure rate — most failures are absorbed by the fallback
chain rather than surfacing to the caller. Measure your own stack; the number is
usually worse than you think and better than it looks.

## The Hard-Won Lessons (failure classes, fixed for good)
1. **A missing import kills a lane silently** — `import shutil` in a resolve block; bare `except: pass` hid it for days. Test every gate with the REAL failure.
2. **Quality gates must check the package, not the prose** — 4 days of zero clicks because pitch emails had no links. Now: no link, no send.
3. **Auto-responses are not leads** — count only human replies. One "stop" = permanent blocklist, never contact again.
4. **The clock lies** — a sender compared local time against UTC windows and silently muted itself. UTC everywhere.
5. **Free tiers churn** — providers retire models without notice (SambaNova's "free" became a paywall overnight; Groq retired llama-70b). The optimizer suspends/demotes automatically. Verify endpoints with real probes, always.
6. **The VM IP is a ghost town** — Reddit, LinkedIn, WWR all 403 datacenter IPs. Residential-IP browser lanes are the answer for anything social.
7. **City-building is the seduction** — the mayor wanted to build districts; the founder banned city work until the first sale. Money first, world second.
8. **A lane that fails 100% of the time has an unencoded platform rule, not a bug.** A whole posting lane died for days because nothing checked Bluesky's 300-character limit — the gate checked caps, dedup and spacing, and never length. Correlation was total: 51 of 51 failures were over the limit, 0 of 5 successes were.
9. **A file change is not a deployment.** Fixes sat inert for hours because nobody restarted the process that ran the old code. Twice in one week.

## The Honest Truth
The tools are commoditizing. Everyone can now stack free APIs. What you can't copy from a tutorial is the **operational scar tissue**: a year of failure classes, fixed for good, documented here.

I built this to run a business. It hasn't made its first sale yet — the machine works, the positioning is the problem, and that part is on me, not the stack.

## License
MIT — do whatever you want, just don't pretend you invented it.

## Contact
chris@braxisai.com · https://braxisai.com

*Built in public, in production, on free tiers, daily.*
