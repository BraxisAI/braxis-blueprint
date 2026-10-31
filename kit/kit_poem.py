#!/usr/bin/env python3
"""kit_poem.py — replace a template poem with a real one, in KIT's voice.

The tick cannot wait on an LLM, so `_compose_poem()` leaves a short deterministic
placeholder. This worker upgrades one or more of those placeholders through the
free writing chain and records `text_engine='llm'`.

Run: venv/bin/python weapons/world/kit_poem.py [--creation ID] [--limit 4] [--dry]
"""
import argparse
import datetime as dt
import json
import os
import re

B = '/home/ubuntu/braxis-2.0'
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
LOG = os.path.join(B, 'logs', 'kit_poem.log')


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _clean(text):
    text = str(text or '').strip()
    text = re.sub(r'^```.*?```$', '', text, flags=re.S).strip()
    text = re.sub(r'\*\*|__|`', '', text)
    text = re.sub(r'^(poem|title)\s*:\s*', '', text, flags=re.I)
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return '\n'.join(lines)[:900]


def _generate(creation, state):
    subject = creation.get('subject') or 'the garden'
    world = state.get('world_name') or 'Glowveil Hollow'
    thought = state.get('thought') or ''
    desire = ''
    if state.get('desires'):
        desire = max(state['desires'], key=lambda d: float(d.get('score', 0))).get('text', '')
    prompt = (
        'Write a short poem of 6 to 8 lines, in the first person, as KIT, a small '
        'garden-robot who lives in a 3D world called %s. Subject: %s. '
        'Recently KIT thought: %s. KIT wants: %s. '
        'Use concrete images from a garden, a workshop, weather, tools, stones, '
        'lamps, or the town. Avoid abstract words like soul, journey, whisper, '
        'tapestry, and avoid rhyming couplets. Do not name real people, companies, '
        'products, websites, laptops, or video titles; keep the poem inside KIT\'s '
        'physical world. Do not add a title, a greeting, quotation marks, markdown, '
        'or an explanation. Return only the poem, one line per line.'
        % (world, subject, thought[:180], desire[:160]))
    try:
        from shared.llm_router import call_llm
        r = call_llm(prompt, system_prompt=(
            'You are the poet inside KIT. You write spare, concrete, slightly '
            'strange poems. Never explain the poem. Return only the poem.'),
            temperature=0.95, max_tokens=300, task='writing')
        text = r.get('content') or r.get('text') if isinstance(r, dict) else str(r)
        return _clean(text)
    except Exception as e:
        try:
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write('%s FAIL %s\n' % (dt.datetime.now(dt.timezone.utc).isoformat(), str(e)[:200]))
        except Exception:
            pass
        return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--creation', default='')
    ap.add_argument('--limit', type=int, default=4)
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    items = _load(CREATIONS, [])
    state = _load(STATE, {})
    if a.creation:
        targets = [x for x in items if x.get('id') == a.creation]
    else:
        targets = [x for x in items
                   if x.get('medium') == 'write' and x.get('text')
                   and (a.force or x.get('text_engine') != 'llm')][-max(1, a.limit):]
    if not targets:
        print('no poem needs an upgrade')
        return 0
    changed = 0
    for c in targets:
        print('poem', c.get('id'), c.get('title'))
        if a.dry:
            continue
        text = _generate(c, state)
        if not text or len(text.splitlines()) < 3:
            print('  no usable poem; keeping placeholder')
            continue
        c['text'] = text
        c['text_engine'] = 'llm'
        c['poem_at'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        changed += 1
        print(text[:400].replace('\n', ' / '))
    if changed:
        _save(CREATIONS, items)
        print('upgraded', changed)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
