#!/usr/bin/env python3
"""KIT's free LLM budget and quality lane.

One daily budget shared by the reflection and the event summarizer. The lead
model is the free 550B Nemotron Ultra on OpenRouter; the fallback is the free
measured background chain. No paid OpenRouter lane can enter this code.
"""
import datetime as dt
import fcntl
import json
import os
import time

B = '/home/ubuntu/braxis-2.0'
BUDGET_PATH = os.path.join(B, 'data', 'world', 'kit_llm_budget.json')
LEDGER = os.path.join(B, 'data', 'world', 'kit_llm_ledger.jsonl')
LOCK = os.path.join(B, 'data', 'world', 'kit_llm_budget.lock')
CAP = 16
LEAD = 'openrouter-nemotron-ultra-free'


def _today():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')


def _load():
    try:
        with open(BUDGET_PATH, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    if d.get('day') != _today():
        d = {'day': _today(), 'count': 0}
    return d


def remaining():
    d = _load()
    return max(0, CAP - int(d.get('count') or 0))


def take():
    """Atomically reserve one call from today's budget."""
    os.makedirs(os.path.dirname(BUDGET_PATH), exist_ok=True)
    with open(LOCK, 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        d = _load()
        if int(d.get('count') or 0) >= CAP:
            return False
        d['count'] = int(d.get('count') or 0) + 1
        tmp = BUDGET_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=1)
        os.replace(tmp, BUDGET_PATH)
        fcntl.flock(lock, fcntl.LOCK_UN)
        return True


def call(prompt, max_tokens=220, temperature=0.85):
    """Free call: 550B Nemotron Ultra first, free background chain second."""
    if not take():
        return {'content': '', 'model': '', 'ok': False,
                'error': 'daily budget exhausted', 'remaining': 0}
    from shared.llm_router import call_llm
    text, model = '', ''
    try:
        r = call_llm(prompt=prompt, task='kit_reflection', model=LEAD,
                     max_tokens=max_tokens, temperature=temperature,
                     fallback=False)
        text = (r or {}).get('content') or ''
        if text.strip():
            model = (r or {}).get('model') or LEAD
    except Exception:
        text = ''
    if not text.strip():
        try:
            r = call_llm(prompt=prompt, task='background',
                         max_tokens=max_tokens, temperature=temperature)
            text = (r or {}).get('content') or ''
            model = (r or {}).get('model') or 'background'
        except Exception:
            text = ''
    ok = bool(text.strip())
    try:
        with open(LEDGER, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': dt.datetime.now(dt.timezone.utc).isoformat(
                timespec='seconds'), 'model': model, 'ok': ok,
                'chars': len(text), 'remaining': remaining()}) + '\n')
    except Exception:
        pass
    return {'content': text, 'model': model, 'ok': ok, 'error': '',
            'remaining': remaining()}
