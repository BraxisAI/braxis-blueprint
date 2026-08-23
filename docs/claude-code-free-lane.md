# Run Claude Code for Free — Without Accidentally Billing Yourself

*The recipe, the pitfall, and the fix — from the night I drained my paid DeepSeek balance learning it.*

Claude Code is a paid tool. But there's an open-source path to run it on **free model lanes** — and most guides leave out the part that costs you money. This is the complete recipe: how to set it up, the three ways it silently bills you anyway, and how to know it's actually free.

---

## The stack (and what's whose)

| Piece | What | Whose |
|---|---|---|
| **free-claude-code** (Alishahryar1) | A local proxy that translates Claude Code's API calls to OpenAI-compatible providers | MIT, ~38.5k stars — **theirs**, credit it |
| **NVIDIA NIM** | Free tier hosting `deepseek-v4-flash-0731` (1M ctx, 40 req/min) | NVIDIA's free developer program |
| **Groq** | Free tier, fast lanes (`gpt-oss-120b`, `qwen3.6-27b`) | Groq's free tier |
| **The integration + the pitfalls below** | The bat, the two-door config, the drain fixes | **yours — this write-up** |

---

## The recipe

1. `git clone https://github.com/Alishahryar1/free-claude-code.git`
2. `uv run fcc-server` (needs **uv >= 0.11.16** — `uv self update` if the project refuses to build)
3. The `.env` — the two-door config that never bills you:

```env
NVIDIA_NIM_API_KEY=nvapi-YOUR-KEY
GROQ_API_KEY=gsk_YOUR-KEY
MODEL=nvidia_nim/deepseek-ai/deepseek-v4-flash-0731     # primary: NIM free
MODEL_SONNET=groq/openai/gpt-oss-120b                    # fallback door: Groq
MODEL_HAIKU=groq/qwen/qwen3.6-27b                        # fast small lane
ANTHROPIC_AUTH_TOKEN=freecc
```

4. Launch Claude Code pointed at the proxy:

```bat
set ANTHROPIC_BASE_URL=http://127.0.0.1:8082
set ANTHROPIC_AUTH_TOKEN=freecc
set ANTHROPIC_API_KEY=
claude --settings %USERPROFILE%\.claude\free-settings.json
```

5. **The verify rule (non-negotiable):** if the CLI header shows the model *with* an "API Usage Billing" badge — **you are on the paid lane.** The proxy must answer `http://127.0.0.1:8082/v1/models` before the CLI opens.

---

## The three ways it bills you anyway (the part nobody wrote down)

### 1. The proxy never actually starts
The bat says "starting the proxy" and launches Claude Code regardless. The proxy's down → Claude Code falls back to its configured default → the paid API. **Fix:** probe the proxy port before launching; fail hard with the log on screen.

### 2. Your environment is poisoned with the paid config
You set `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` globally (user-level `setx`) for the paid lane. Every session — including "free" — inherits them. The proxy never gets touched; every "free" call bills DeepSeek. **Fix:** remove the user-level vars (the paid lane lives in a settings file instead) + have the bat clear `ANTHROPIC_API_KEY` in-session.

### 3. Your settings.json fights the free lane
Claude Code reads `~/.claude/settings.json` env — if it carries the paid base URL + key, it overrides the shell. **Fix:** a separate `free-settings.json` (proxy URL, no paid key anywhere) + `claude --settings` on the free launch.

---

## The honest reality of "free"

- **Speed:** the NIM free tier is 40 req/min with queues — expect 20-60s answers. It feels half-speed. That's the price of $0.
- **Depth:** the free build (`-0731`) is newer and less battle-tested than the production API — keep the complicated multi-step builds on the paid lane, give the mechanical grind to the free one.
- **The effort dial:** `CLAUDE_CODE_EFFORT_LEVEL=high` in the free settings gets most of the reasoning depth at a sane speed. `max` on a throttled free lane = slow + drift.

**The split that works:** free lane = file ops, cron wiring, verification, the grind. Paid lane = the architecture, the builds, the reasoning. Same model family, different door, different budget.

---

*Written 2026-08-23 by the founder of the [BRAXIS $0 AI empire](https://braxisai.com) — the full playbook is in this repo. The proxy is [free-claude-code](https://github.com/Alishahryar1/free-claude-code) (MIT, theirs — go star it). The drain lessons are mine — I paid for them so you don't have to.*
