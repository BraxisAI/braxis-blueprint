"""BRAXIS V2 — LLM router. Full empire stack (13+ routes) ported from the old
gateway (looted main.py) and verified live 2026-08-02. Quality fallback chain
led by the big brains; per-task model policy with alternation between the 2
best. DeepSeek reserved for Claude CLI (not in chain). OpenRouter = final
resort tier only, capped at $0.10/day. Spend-capped $10/day total."""
import json
import threading
import time

import requests

from shared import config
from shared.db import get_dashboard_db, record_spend
from shared.logger import get_logger

logger = get_logger("llm_router")

# (name, base_url, model, key, timeout_seconds)
PROVIDERS = [
    # --- NVIDIA big brains (the empire's heavy hitters) ---
    # FIXED 2026-08-06: this route was pointed at nemotron-3-super-120b (a 120B).
    # mistral-nemotron = the real Mistral Nemotron 675B. Verified PONG.
    ("nvidia-mistral-675b", "https://integrate.api.nvidia.com/v1/chat/completions",
     "mistralai/mistral-nemotron", config.NVIDIA_API_KEY, 120),
    ("nemotron-550b", "https://integrate.api.nvidia.com/v1/chat/completions",
     "nvidia/nemotron-3-ultra-550b-a55b", config.NVIDIA_API_KEY, 120),
    ("nvidia-nim", "https://integrate.api.nvidia.com/v1/chat/completions",
     "meta/llama-3.3-70b-instruct", config.NVIDIA_API_KEY, 60),
    ("nvidia-llama-8b", "https://integrate.api.nvidia.com/v1/chat/completions",
     "meta/llama-3.1-8b-instruct", config.NVIDIA_API_KEY, 60),
    # --- Groq workhorses (FIXED 2026-08-17: llama-3.3-70b-versatile and
    # llama-3.1-8b-instant were RETIRED from this account; live models are
    # gpt-oss-120b/20b, qwen3.6-27b, allam-2-7b — verified 200 in probe) ---
    ("groq-70b", "https://api.groq.com/openai/v1/chat/completions",
     "openai/gpt-oss-120b", config.GROQ_API_KEY, 30),
    ("groq-70b-bak", "https://api.groq.com/openai/v1/chat/completions",
     "openai/gpt-oss-20b", config.GROQ_API_KEY_BACKUP, 30),
    # --- NVIDIA Build catalog (verified 08-23, free tier, no CC): lightning
    # fast 0.3s, muse multimodal (vision), deepseek-v4 1M ctx (slow + halluc
    # reports — TAIL ONLY). glm-5.2 already deprecated (absent from catalog). ---
    ("nvidia-lightning", "https://integrate.api.nvidia.com/v1/chat/completions",
     "nvidia/nemotron-3.5-lightning-30b-a3b", config.NVIDIA_API_KEY, 60),
    ("nvidia-muse", "https://integrate.api.nvidia.com/v1/chat/completions",
     "meta/muse-glimmer-30b", config.NVIDIA_API_KEY, 60),
    ("nvidia-deepseek-v4", "https://integrate.api.nvidia.com/v1/chat/completions",
     "deepseek-ai/deepseek-v4-flash-0731", config.NVIDIA_API_KEY, 120),
    # --- Cloudflare Workers AI (free tier, wired 2026-08-12) ---
    ("cloudflare-70b", "https://api.cloudflare.com/client/v4/accounts/e424d4788f03c2c8d17c39dd809f5a19/ai/v1/chat/completions",
     "@cf/meta/llama-3.3-70b-instruct-fp8-fast", config.CLOUDFLARE_API_TOKEN, 60),
    ("cloudflare-8b", "https://api.cloudflare.com/client/v4/accounts/e424d4788f03c2c8d17c39dd809f5a19/ai/v1/chat/completions",
     "@cf/meta/llama-3.1-8b-instruct", config.CLOUDFLARE_API_TOKEN, 60),
    # --- Zhipu GLM-4-Flash (free API, wired 2026-08-12) ---
    ("zhipu-glm-flash", "https://open.bigmodel.cn/api/paas/v4/chat/completions",
     "glm-4-flash", config.ZHIPU_API_KEY, 60),
    # OpenRouter (paid lanes only — FIXED 2026-08-17: the :free models
    # (llama-3.3-70b, qwen3-235b) were retired from the free list, 404).
    # Paid lanes capped by OPENROUTER_DAILY_CAP to stretch the ~$9 credit.
    ("openrouter-r1", "https://openrouter.ai/api/v1/chat/completions",
     "deepseek/deepseek-reasoner", config.OPENROUTER_API_KEY, 120),
    ("openrouter-qwen235", "https://openrouter.ai/api/v1/chat/completions",
     "qwen/qwen3-235b-a22b", config.OPENROUTER_API_KEY, 120),
    # OpenRouter :free lanes — RE-ADDED 2026-08-18 (names end "-free" so the
    # paid-cap logic skips them; all three probed HTTP 200 live)
    ("openrouter-550b-free", "https://openrouter.ai/api/v1/chat/completions",
     "nvidia/nemotron-3-ultra-550b-a55b:free", config.OPENROUTER_API_KEY, 60),
    ("openrouter-oss20b-free", "https://openrouter.ai/api/v1/chat/completions",
     "openai/gpt-oss-20b:free", config.OPENROUTER_API_KEY, 60),
    ("openrouter-120b-free", "https://openrouter.ai/api/v1/chat/completions",
     "nvidia/nemotron-3-super-120b-a12b:free", config.OPENROUTER_API_KEY, 60),
    # --- Ollama local (qwen2.5:7b, installed 08-12 — the offline/quota-free lane) ---
    ("ollama-qwen", "http://localhost:11434/v1/chat/completions",
     "qwen2.5:7b", "ollama", 120),
    # --- Mistral La Plateforme (Experiment tier ~1B tokens/month, 2026-08-12) ---
    ("mistral-large", "https://api.mistral.ai/v1/chat/completions",
     "mistral-large-latest", config.MISTRAL_API_KEY, 60),  # user-verified: large IS free-tier accessible
    ("mistral-medium", "https://api.mistral.ai/v1/chat/completions",
     "mistral-medium-2508", config.MISTRAL_API_KEY, 60),
    ("groq-qwen-32b", "https://api.groq.com/openai/v1/chat/completions",
     "qwen/qwen3.6-27b", config.GROQ_API_KEY, 30),
    ("groq-8b", "https://api.groq.com/openai/v1/chat/completions",
     "allam-2-7b", config.GROQ_API_KEY, 30),
    # --- SambaNova (DeepSeek variants intentionally excluded: reserved for Claude CLI) ---
    ("sambanova-70b", "https://api.sambanova.ai/v1/chat/completions",
     "Meta-Llama-3.3-70B-Instruct", config.SAMBANOVA_API_KEY, 60),
    ("sambanova-gemma", "https://api.sambanova.ai/v1/chat/completions",
     "gemma-4-31B-it", config.SAMBANOVA_API_KEY, 60),
    ("sambanova-gpt-oss", "https://api.sambanova.ai/v1/chat/completions",
     "gpt-oss-120b", config.SAMBANOVA_API_KEY, 60),
    # --- Cerebras ---
    # 08-21: cerebras = PayGo now (migrated from free tier, $5 trial credit needs card — PAID, skipped per free-only rule). Entries kept dormant.
    ("cerebras-oss-120b", "https://api.cerebras.ai/v1/chat/completions",
     "gpt-oss-120b", config.CEREBRAS_API_KEY, 30),
    ("cerebras-gemma", "https://api.cerebras.ai/v1/chat/completions",
     "gemma-4-31b", config.CEREBRAS_API_KEY, 30),
]  # cerebras-glm removed 2026-08-17 (zai-glm-4.7 archived, 404)

# Gemini routes — verified live 2026-08-02 (AI-Studio key, GEMINI_API_KEY in .env)
PROVIDERS += [
    ("gemini-flash", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-2.5-flash", config.GEMINI_API_KEY, 30),
    ("gemini-pro", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-2.5-pro", config.GEMINI_API_KEY, 30),
]

# Second Gemini account (GEMINI_API_KEY2 in .env) = independent free quota.
# Key minted 2026-08-06 (braxisai2@gmail.com). NOTE: the new account CANNOT
# use gemini-2.5-* ('no longer available to new users') — verified working:
# gemini-flash-latest (200), gemini-pro-latest (429, not in free tier).
PROVIDERS += [
    ("gemini-flash-2", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-flash-latest", config.GEMINI_API_KEY2, 30),
    ("gemini-pro-2", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-pro-latest", config.GEMINI_API_KEY2, 30),
]

# Pollinations — keyless, free, unlimited (verified 2026-08-10). True last
# resort only: small open model, good for never-silent fallback.
PROVIDERS += [
    ("pollinations", "https://text.pollinations.ai/openai",
     "openai", "", 30),
]

# Third Gemini key (GEMINI_API_KEY3) - same account family as key2 (AQ.Ab8RN6
# prefix). Redundancy, not a new quota pool. Verified 2026-08-10.
PROVIDERS += [
    ("gemini-flash-3", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-flash-latest", config.GEMINI_API_KEY3, 30),
]

# Third Gemini key (GEMINI_API_KEY4) - same account family as key2 (AQ.Ab8RN6
# prefix). Redundancy, not a new quota pool. Verified 2026-08-10.
PROVIDERS += [
    ("gemini-flash-4", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-flash-latest", config.GEMINI_API_KEY4, 30),
    ("gemini-flash-6", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "gemini-flash-latest", config.GEMINI_API_KEY6, 30),
]

# Quality fallback chain — old gateway order, extended with verified models.
QUALITY_FALLBACK = [
    "nvidia-mistral-675b", "nemotron-550b", "groq-70b", "groq-70b-bak",
    "groq-qwen-32b", "gemini-flash", "gemini-flash-2",
    "gemini-flash-4", "gemini-flash-6", "gemini-flash-3",
    "nvidia-nim", "cloudflare-70b", "zhipu-glm-flash",
    # 08-22: sambanova (402 paywall) + cerebras (PayGo) removed from chains; defs dormant
    "mistral-medium", "openrouter-550b-free", "openrouter-120b-free",
    "openrouter-oss20b-free", "pollinations",
]  # 2026-08-18: openrouter :free lanes re-added (probed live) (ollama not installed, openrouter :free
# retired 404, cerebras-glm archived); cloudflare stays at tail (daily quota)

# Per-task model policies. First two entries alternate round-robin; the rest
# of the quality chain backs them up.
# 2026-08-06: smartest model per job, not biggest. No DeepSeek (CLI-only).
TASKS = {
    # prose/outreach — benchmarked 2026-08-06 (realistic prompt, 2 rounds):
    #   550B:   2-7s, good copy     <- leads: reliable big brain
    #   groq-70b: 0.3-0.4s, good    <- fast workhorse
    #   675B:   >25s timeouts tonight (flaky free endpoint) -> quality
    #           backup, cooldown keeps it from stalling the chain
    #   gemini: 429 quota, -2 = 2nd account when key added
    "writing": ["nemotron-550b", "groq-70b", "nvidia-mistral-675b", "nvidia-nim",
                "groq-70b-bak", "mistral-large", "mistral-medium", "zhipu-glm-flash",
                "cloudflare-70b", "gemini-flash", "gemini-flash-2", "gemini-flash-3",
                "nvidia-deepseek-v4", "pollinations"],  # 08-23: deepseek-v4 tail (slow, halluc reports)
    # groq-qwen-32b removed 2026-08-07: leaks <think> traces into content
    # (thinking model, no disable flag on Groq) - would pollute keyword output.
    "keywords": ["groq-70b", "groq-qwen-32b", "groq-8b", "nvidia-llama-8b", "zhipu-glm-flash", "cloudflare-8b", "ollama-qwen"],  # fast structured extraction (qwen3.6-27b = 123ms)
    # companion chat (2026-08-17): groq gpt-oss-120b leads — warm + 0.2s.
    "chat": ["groq-70b", "groq-qwen-32b", "groq-70b-bak", "mistral-medium",
             "zhipu-glm-flash", "gemini-flash", "gemini-flash-2", "gemini-flash-3",
             "gemini-flash-4", "gemini-flash-6", "cloudflare-8b", "pollinations"],
    "design": ["nemotron-550b", "groq-70b", "nvidia-mistral-675b", "nvidia-nim",
               "groq-70b-bak", "mistral-large", "mistral-medium", "zhipu-glm-flash",
               "cloudflare-70b", "gemini-flash", "gemini-flash-2", "gemini-flash-3",
               "openrouter-qwen235"],  # qwen235 = paid cap
    # 550B-led analysis; the old '675B echoed prompts' finding was the
    # misrouted 120B, not the real 675B
    "analysis": ["nemotron-550b", "nvidia-mistral-675b", "groq-70b", "nvidia-nim", "nvidia-lightning", "openrouter-r1", "ollama-qwen"],
}

_ALT = {}

# FIXED 2026-08-06: cooldown routing. A provider that fails with an HTTP
# error (429 quota / 5xx) gets skipped for a window instead of being re-tried
# on every call — each wasted attempt cost 1-4s of latency and hammered the
# dead quota. Hard (quota/rate-limit) failures cool for 12h (daily quotas
# don't reset mid-day); soft 5xx cool for 30 min. Transient timeouts and
# empty-content responses do NOT trigger cooldown (they're not the provider's
# fault).
_COOLDOWN = {}  # provider name -> (until_ts, reason)
# FIXED 2026-08-08: min seconds between calls per provider - spread the burst
# so per-minute limits are never hit in the first place (was: free endpoints
# 429'd on bursts, then 12h-cooldowned the whole chain).
_LAST_CALL = {}
# FIXED 2026-08-12: wall-clock caps. The flaky big brains trickle-stream and
# never trip the socket timeout (550B took 121s while 'OK') — a slow-but-alive
# endpoint monopolized every writing call. Cap = fail fast to groq (0.3s).
_WALL_CAP = {'nemotron-550b': 25, 'nvidia-mistral-675b': 25}


def _call_with_watchdog(p, body, timeout, cap):
    """Call a provider but give up after `cap` wall-clock seconds (daemon thread)."""
    result = {}

    def _run():
        try:
            result["r"] = _call(p, body, timeout)
        except Exception as e:
            result["e"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=cap)
    if t.is_alive():
        raise TimeoutError(f"{p[0]} exceeded {cap}s wall-clock cap")
    if "e" in result:
        raise result["e"]
    return result["r"]


_MIN_INTERVAL = {
    'nemotron-550b': 3.0, 'nvidia-mistral-675b': 4.0, 'groq-70b': 1.0,
    'groq-70b-bak': 1.0, 'cloudflare-70b': 2.0, 'cloudflare-8b': 1.0, 'zhipu-glm-flash': 1.5, 'ollama-qwen': 0.5, 'mistral-large': 2.0, 'mistral-medium': 1.5,
    'nvidia-nim': 1.5, 'nvidia-llama-8b': 1.0,
    'groq-8b': 0.5, 'gemini-flash': 3.0, 'gemini-flash-2': 3.0, 'gemini-flash-4': 3.0, 'gemini-flash-6': 3.0, 'gemini-flash-3': 3.0,
    'gemini-pro': 4.0, 'gemini-pro-2': 4.0,
}


def _mark_fail(name: str, msg: str):
    m = (msg or '').lower()
    # FIXED 2026-08-08: every 429 was treated as daily-quota exhaustion -> 12h
    # cooldown. A burst of calls trips PER-MINUTE limits (gemini ~15 RPM, groq
    # ~30, NVIDIA stricter) which recover in minutes - 12h on those killed the
    # whole chain for the night. Only explicit daily-quota language gets 12h.
    rate = any(k in m for k in ('rate limit', 'rate_limit', 'too many requests',
                                'rpm', 'resource has been exhausted',
                                'requests per', 'per minute', 'per day'))
    quota = any(k in m for k in ('quota', 'daily', 'current quota', 'day limit',
                                 'per-day', 'exceeded your current'))
    # 08-18: 12h ONLY for explicit daily language (gemini's per-minute
    # 'current quota' message was locking lanes for 10h and cascading).
    if '429' in m and quota and not rate and any(
            k in m for k in ('daily', 'per day', 'day limit', 'per-day', 'daily quota')):
        cool = 12 * 3600
    elif '429' in m or rate:
        cool = 15 * 60            # per-minute limit - recovers fast
    else:
        cool = 30 * 60            # 5xx
    _COOLDOWN[name] = (time.time() + cool, msg[:80])


def _mark_ok(name: str):
    _COOLDOWN.pop(name, None)


DEAD_FILE = config.BASE_DIR / 'data' / 'dead_models.json'


def _dead() -> set:
    """Models flagged by the canary (data/dead_models.json) - skip at call time."""
    try:
        return set(json.loads(DEAD_FILE.read_text()))
    except Exception:
        return set()


def _log_call(name: str, ms: float, ok: bool, err: str = ''):
    """Per-call stats for the reliability picture (logs/llm_calls.jsonl)."""
    try:
        line = json.dumps({'t': time.strftime('%Y-%m-%d %H:%M:%S'), 'provider': name,
                           'ok': ok, 'ms': int(ms), 'err': str(err)[:60]})
        with open(config.BASE_DIR / 'logs' / 'llm_calls.jsonl', 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def _daily_spend() -> float:
    # 08-18: db contention must NEVER block the chain — spend is bookkeeping
    try:
        with get_dashboard_db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost),0) FROM api_spend WHERE created_at > datetime('now','-1 day')"
            ).fetchone()
            return float(row[0])
    except Exception:
        return 0.0


def _by_name(name: str):
    return next((p for p in PROVIDERS if p[0] == name), None)


def _call(p, body: dict, timeout: int) -> dict:
    b = dict(body)
    b["model"] = p[2]
    # FIXED 2026-08-06: gemini-2.5 and gpt-oss are thinking models — they burn
    # max_tokens on reasoning and return empty/truncated copy on small budgets.
    if p[0].startswith("gemini") or "gpt-oss" in p[2]:
        b["max_tokens"] = max(1024, b.get("max_tokens", 2000) * 4)
    # FIXED 2026-08-06: nemotron-3-ultra leaks chain-of-thought into content on
    # tight token budgets (hosted endpoint merges the thinking trace). Turning
    # thinking OFF kills the leak — verified live on the 550B. The reasoning
    # budget then goes to the actual answer instead of a truncated thought.
    if "nemotron-3-ultra" in p[2]:
        b["chat_template_kwargs"] = {"enable_thinking": False}
    r = requests.post(p[1], headers={"Authorization": "Bearer " + p[3]}, json=b, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(p[0] + " HTTP " + str(r.status_code) + ": " + r.text[:120])
    data = r.json()
    # some providers (Gemini OpenAI-compat, Cerebras) return content as a
    # list of parts instead of a plain string — normalize both shapes
    _msg = data["choices"][0]["message"]
    content = _msg.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    usage = data.get("usage", {})
    cost = usage.get("prompt_tokens", 0) * 0.5 / 1_000_000
    try:
        record_spend(p[0], p[2], cost)
    except Exception:
        pass
    logger.info("LLM ok: %s/%s (%.4f$)", p[0], p[2], cost)
    return {"content": content, "provider": p[0], "model": p[2]}


_TUNING_CACHE = {'data': None, 'mt': 0}

def _tuning():
    """08-21 MODEL OPTIMIZER hook: read data/model_tuning.json (written by
    the daily optimizer) with mtime-cache so long-running processes see
    changes without restart. Returns (suspend_set, demote_set)."""
    try:
        p = config.BASE_DIR / 'data' / 'model_tuning.json'
        mt = p.stat().st_mtime
        if _TUNING_CACHE['data'] is None or mt != _TUNING_CACHE['mt']:
            _TUNING_CACHE['data'] = json.loads(p.read_text())
            _TUNING_CACHE['mt'] = mt
        d = _TUNING_CACHE['data']
        return set(d.get('suspend', {})), set(d.get('demote', {}))
    except Exception:
        return set(), set()


def _try(names, body):
    last = None
    _sus, _dem = _tuning()
    # suspended -> never attempted (dead-weight skip); demoted -> moved to
    # the tail so healthy lanes serve first
    if _sus or _dem:
        names = [n for n in names if n not in _sus]
        if _dem:
            names = [n for n in names if n not in _dem] +                     [n for n in names if n in _dem]
    for name in names:
        p = _by_name(name)
        if not p or not p[3]:
            continue
        # paid openrouter lanes: hard daily cap (the ~$9 credit must stretch)
        if name.startswith("openrouter-") and not name.endswith("-free") \
                and _daily_spend() >= config.OPENROUTER_DAILY_CAP:
            logger.warning("openrouter paid lanes capped at $%.2f/day",
                           config.OPENROUTER_DAILY_CAP)
            continue
        cd = _COOLDOWN.get(name)
        if cd and cd[0] > time.time():
            last = RuntimeError("%s on cooldown: %s" % (name, cd[1]))
            continue
        if name in _dead():
            last = RuntimeError("%s flagged dead by canary" % name)
            continue
        _t0 = time.time()
        if name in _dead():
            last = RuntimeError("%s flagged dead by canary" % name)
            continue
        # burst throttle: WAIT out the interval instead of skipping - a skip
        # with every provider throttled = fake 'all providers failed'
        _wait = _MIN_INTERVAL.get(name, 1.5) - (time.time() - _LAST_CALL.get(name, 0))
        if _wait > 0:
            time.sleep(_wait)
        _t0 = time.time()
        try:
            _LAST_CALL[name] = time.time()
            res = _call_with_watchdog(p, body, p[4], _WALL_CAP.get(name, 60))
            # FIXED 2026-08-06: a 200 with empty content is a FAILURE — it
            # produced the blank/identical gap-pitch emails (gemini thinking
            # models burn max_tokens on reasoning). Keep walking the chain.
            if not (res.get("content") or "").strip():
                raise RuntimeError(p[0] + " returned empty content")
            from shared.loop_shield import detect_loop
            if detect_loop(res.get("content")):
                raise RuntimeError(p[0] + " DOOM LOOP detected (repetitive output)")
            _mark_ok(name)
            _log_call(name, (time.time() - _t0) * 1000, True)
            return res, None
        except Exception as e:
            last = e
            msg = str(e)
            _log_call(name, (time.time() - _t0) * 1000, False, msg)
            if 'HTTP' in msg:  # provider error (quota/5xx) → cooldown
                _mark_fail(name, msg)
            elif 'timed out' in msg.lower() or 'Timeout' in type(e).__name__:
                # FIXED 2026-08-06: a slow/frozen endpoint (the 675B was
                # queueing >25s) must not burn its 120s timeout on every call.
                _COOLDOWN[name] = (time.time() + 20 * 60, 'timeout')
            logger.warning("LLM %s failed: %s", name, msg)
            time.sleep(1)
    if last is not None:
        _cd = {k: ("%ds left" % int(v[0] - time.time())) for k, v in _COOLDOWN.items() if v[0] > time.time()}
        if _cd:
            logger.warning('chain exhausted - cooldowns: %s', _cd)
    return None, last


def call_llm(prompt: str, system_prompt: str = "", model: str = None,
             max_tokens: int = 2000, temperature: float = 0.7,
             provider: str = None, task: str = None,
             json_schema: dict = None) -> dict:
    """Route to the best model. Order: explicit model/provider -> task policy
    (alternating) -> quality fallback chain. Returns {'content','provider','model'}.
    08-21: json_schema= forces structured output (Groq OpenAI-compat
    response_format=json_schema) — verdicts parse at ~100% instead of the
    regex-parse 15-30% failure class."""
    if _daily_spend() >= config.MAX_DAILY_API_SPEND:
        raise RuntimeError("Daily API spend cap reached ($" + str(config.MAX_DAILY_API_SPEND) + ")")
    body = {
        "messages": [{"role": "system", "content": system_prompt or "You are a helpful assistant."},
                     {"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": temperature,
    }
    if json_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "structured_output", "schema": json_schema,
                            "strict": True},
        }
    if model or provider:
        names = [p[0] for p in PROVIDERS
                 if (not provider or p[0].startswith(provider) or p[0] == provider)
                 and (not model or p[2] == model or p[0] == model)]
        res, _ = _try(names, body)
        if res:
            return res
        res, last = _try(QUALITY_FALLBACK, body)
        if res:
            return res
        raise RuntimeError("All LLM providers failed. Last: " + str(last))

    names = QUALITY_FALLBACK
    if task and task in TASKS and TASKS[task]:
        t = TASKS[task]
        if len(t) >= 2:
            i = _ALT.get(task, 0)
            _ALT[task] = 1 - i
            names = [t[i]] + [t[1 - i]] + [n for n in QUALITY_FALLBACK if n not in t[:2]]
        else:
            names = t + [n for n in QUALITY_FALLBACK if n not in t]
        # FIXED 2026-08-06: quality floor — customer-facing creative tasks
        # (writing/design) NEVER fall through to the weak-model tail of the
        # chain. If every brain in the task list is dead, call_llm raises and
        # the caller holds the work for a later run instead of shipping
        # generic copy from an 8B. Other tasks may use the full chain.
        if task in ('writing', 'design'):
            names = t
    res, last = _try(names, body)
    if res:
        # FIXED 2026-08-06: LOUD signal when the intended top pick didn't
        # serve — this is how 'silent generification' starts. Watch for
        # 'CHAIN DEGRADED' in logs.
        if res["provider"] != names[0]:
            logger.warning("CHAIN DEGRADED: %s served task=%s (wanted %s) — quality may be lower",
                           res["provider"], task, names[0])
        return res
    raise RuntimeError("All LLM providers failed. Last: " + str(last))
