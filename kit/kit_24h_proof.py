#!/usr/bin/env python3
"""kit_24h_proof.py — the 24-hour receipt for KIT."""
import datetime as dt
import json
import math
import os

B = '/home/ubuntu/braxis-2.0'
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
BUILDS = os.path.join(B, 'data', 'world', 'world_builds.json')
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
JOURNAL = os.path.join(B, 'data', 'world', 'world_life_journal.md')
OUT = os.path.join(B, 'data', 'world', 'kit_24h_proof.json')


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def main():
    s = _load(STATE, {})
    builds = _load(BUILDS, [])
    creations = _load(CREATIONS, [])
    counts = s.get('counts') or {}
    total = sum(counts.values()) or 1
    entropy = -sum((v / total) * math.log(v / total, 2) for v in counts.values() if v)
    try:
        journal_lines = sum(1 for _ in open(JOURNAL, encoding='utf-8'))
    except Exception:
        journal_lines = 0
    report = {
        'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'name': s.get('name'), 'world': s.get('world_name'),
        'hobby': s.get('hobby'), 'creative_hobby': s.get('creative_hobby'),
        'llm_calls': s.get('llm_calls'),
        'builds': len(builds), 'creations': len(creations),
        'projects_done': len(s.get('projects_done') or []),
        'signals_total': s.get('signals_total'),
        'posts': s.get('posts'),
        'visitors': s.get('visitors'), 'offerings': s.get('offerings'),
        'visitor_impressions': len(s.get('visitor_impressions') or {}),
        'action_counts': counts,
        'action_entropy_bits': round(entropy, 3),
        'action_history_tail': (s.get('action_history') or [])[-20:],
        'thought_history_tail': (s.get('thought_history') or [])[-6:],
        'journal_lines': journal_lines,
        'reflection': s.get('reflection'),
        'wishlist': s.get('wishlist'),
        'self_model': s.get('self_model'),
    }
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    os.replace(tmp, OUT)
    try:
        with open(JOURNAL, 'a', encoding='utf-8') as f:
            f.write('\n**%s** — 24-hour proof: %d builds, %d creations, '
                    '%d projects, %d signals, %d posts, action entropy %.2f bits.\n'
                    % (dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                       len(builds), len(creations), len(s.get('projects_done') or []),
                       int(s.get('signals_total') or 0), int(s.get('posts') or 0), entropy))
    except Exception:
        pass
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
