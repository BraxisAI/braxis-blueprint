# BRAXIS BLUEPRINT — The $0 AI Empire Playbook

**One founder. One year. Zero dollars on APIs. 140+ autonomous agents, 20+ free LLM lanes, 1,800+ songs, a living 3D city with persistent AI citizens, and a fully automated sales/content machine — built entirely on free tiers, open weights, and stubbornness.**

This repo is the honest, unpolished blueprint: the actual scripts that run the empire, the architecture that holds it together, and the failure classes that almost killed it — so you don't have to learn them the way I did.

> I'm not selling you a course. I'm handing you the scripts. Everything here ran in production today.

## The Empire in Numbers
- **140+ autonomous agents** — a CEO/chief-of-staff decision duo + a city of persistent citizens with memory, reflection, and a self-improvement loop
- **20+ free LLM lanes** — a router that falls through providers (cooldowns, dead-model tracking, self-optimizing) without spending a dollar
- **1,800+ songs, 5 video styles, daily content across 5 platforms** — one pipeline, zero budget
- **~1,000 cold emails/week** with SPF/DKIM/DMARC, bounce management, and spam-safe rate capping
- **14 live Stripe products** with automated fulfillment
- **A 3D world** (braxisai.com/world) where the mayor is an LLM agent and the citizens self-modify
- **3 verified backup copies** of everything, nightly

## Live Demos
- The world: https://braxisai.com/world/
- The talking mayor: https://braxisai.com/avatar/
- The music machine: https://braxisai.com/music/
- The job-hunt machine (built for the founder's own search): https://braxisai.com/ops/jobs.html

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
├── 20+ free LLM lanes (Groq, NVIDIA NIM, Gemini, Mistral, Zhipu, OpenRouter :free, local Ollama)
│   └── llm_router.py — chains with cooldowns/failover/optimizer (free-only, fail-closed)
├── SQLite + WAL (single-writer, flock-guarded — the lock-class fixes)
├── ~107 cron jobs, all wrapped in cronwrap.sh (flock + timeout)
├── systemd services: webhook, dashboard, nginx, the duo loops
├── nightly 3-copy backups (local + OCI bucket)
└── PC (residential IP): the sender, the browser lanes, the GPU
```

## The Hard-Won Lessons (failure classes, fixed for good)
1. **A missing import kills a lane silently** — `import shutil` in a resolve block; bare `except: pass` hid it for days. Test every gate with the REAL failure.
2. **Quality gates must check the package, not the prose** — 4 days of zero clicks because pitch emails had no links. Now: no link, no send.
3. **Auto-responses are not leads** — count only human replies. One "stop" = permanent blocklist, never contact again.
4. **The clock lies** — a sender compared local time against UTC windows and silently muted itself. UTC everywhere.
5. **Free tiers churn** — providers retire models without notice (SambaNova's "free" became a paywall overnight; Groq retired llama-70b). The optimizer suspends/demotes automatically. Verify endpoints with real probes, always.
6. **The VM IP is a ghost town** — Reddit, LinkedIn, WWR all 403 datacenter IPs. Residential-IP browser lanes are the answer for anything social.
7. **City-building is the seduction** — the mayor wanted to build districts; the founder banned city work until the first sale. Money first, world second.

## The Honest Truth
The tools are commoditizing. Everyone can now stack free APIs. What you can't copy from a tutorial is the **operational scar tissue**: a year of failure classes, fixed for good, documented here.

I built this to run a business. It hasn't made its first $19 yet — the machine works, the positioning is the problem, and that part is on me, not the stack.

## License
MIT — do whatever you want, just don't pretend you invented it.

## Contact
chris@braxisai.com · https://braxisai.com

*Built in public, in production, on free tiers, daily.*