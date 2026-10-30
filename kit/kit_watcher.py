#!/usr/bin/env python3
"""kit_watcher.py — the dreamkeeper.

The founder: "should we have a kit watcher or something that can search for
ways to improve what kit is and what kit is doing, have something watch and
read the journals or dreams or whatever and help make kits dreams come true."

This runs twice a day. It reads KIT's state, dream, reflection and builds. If
KIT dreams about water, a door, a tower, a mural, a bridge, a monument, a
trellis or a bench, and the matching blueprint is not yet in KIT's dojo, the
watcher leaves that blueprint in KIT's mailbox as a gift. KIT reads the mailbox
on its next tick and decides whether to use it. The watcher never overrides a
choice and never spends money.

It also writes a small report for the trio / the founder:
  data/world/kit_watcher.json
  data/world/kit_watcher_journal.md
"""
import datetime as dt
import json
import os
import random
import re
import urllib.request

B = '/home/ubuntu/braxis-2.0'
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
JOURNAL = os.path.join(B, 'data', 'world', 'world_life_journal.md')
REPLY = os.path.join(B, 'data', 'world', 'trio_replies.jsonl')
REPORT = os.path.join(B, 'data', 'world', 'kit_watcher.json')
WJOURNAL = os.path.join(B, 'data', 'world', 'kit_watcher_journal.md')
BUILDS = os.path.join(B, 'data', 'world', 'world_builds.json')
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
INPUTS = os.path.join(B, 'data', 'world', 'world_inputs.json')


def _world_inputs():
    """Free, keyless external factors: Vermont weather + BTC 24h move."""
    weather, temp, btc = '', None, 0.0
    try:
        url = ('https://api.open-meteo.com/v1/forecast?latitude=43.16'
               '&longitude=-72.87&current=temperature_2m,weather_code')
        req = urllib.request.Request(url, headers={'User-Agent': 'BraxisKit/1.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            cur = json.load(r).get('current') or {}
        code = int(cur.get('weather_code') or 0)
        temp = cur.get('temperature_2m')
        if code == 0:
            weather = 'clear'
        elif code in (1, 2, 3):
            weather = 'partly cloudy'
        elif code in (45, 48):
            weather = 'fog'
        elif 51 <= code <= 57:
            weather = 'drizzle'
        elif 61 <= code <= 67:
            weather = 'rain'
        elif 71 <= code <= 77:
            weather = 'snow'
        elif 80 <= code <= 82:
            weather = 'showers'
        elif 85 <= code <= 86:
            weather = 'snow showers'
        elif code >= 95:
            weather = 'thunderstorm'
        else:
            weather = 'weather code %d' % code
    except Exception as e:
        weather = 'unknown (%s)' % str(e)[:40]
    try:
        url = ('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin'
               '&vs_currencies=usd&include_24hr_change=true')
        req = urllib.request.Request(url, headers={'User-Agent': 'BraxisKit/1.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            btc = float((json.load(r).get('bitcoin') or {}).get('usd_24h_change') or 0)
    except Exception:
        pass
    data = {'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'weather': weather, 'temp': temp, 'btc_change': round(btc, 2)}
    try:
        with open(INPUTS, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
    except Exception:
        pass
    return data

KINDS = ['garden_plot', 'trellis', 'bench', 'lantern', 'arch', 'mural',
         'tower', 'bridge', 'fountain', 'monument']

DREAM_MAP = [
    (r'\b(fountain|water|stream|river|rain)\b', 'fountain'),
    (r'\b(arch|door|gate|entrance)\b', 'arch'),
    (r'\b(tower|far|horizon|high|see)\b', 'tower'),
    (r'\b(mural|paint|color|colour|wall|picture)\b', 'mural'),
    (r'\b(bridge|cross|connect|other side)\b', 'bridge'),
    (r'\b(monument|remember|memory|stone|mark)\b', 'monument'),
    (r'\b(trellis|vine|climb|rose)\b', 'trellis'),
    (r'\b(bench|sit|rest|watch)\b', 'bench'),
    (r'\b(garden|flower|seed|grow|plant)\b', 'garden_plot'),
    (r'\b(lantern|light|lamp|glow)\b', 'lantern'),
]


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj) + '\n')


def main():
    st = _load(STATE, {})
    inputs = _world_inputs()
    builds = _load(BUILDS, [])
    if not isinstance(builds, list):
        builds = []
    creations = _load(CREATIONS, [])
    if not isinstance(creations, list):
        creations = []
    recent_creations = creations[-12:]
    recent_mediums = [str(c.get('medium') or '') for c in recent_creations]
    medium_counts = {}
    for m in recent_mediums:
        if m:
            medium_counts[m] = medium_counts.get(m, 0) + 1
    top_medium, top_count = ('', 0)
    if medium_counts:
        top_medium, top_count = max(medium_counts.items(), key=lambda kv: kv[1])
    tilt = top_medium if (top_count >= 5 or (len(recent_mediums) >= 8 and top_count >= 4)) else ''
    dream = ' '.join(str(st.get(k) or '') for k in ('dream', 'reflection'))
    try:
        dream += ' ' + open(JOURNAL, encoding='utf-8').read()[-2500:]
    except Exception:
        pass
    unlocked = set(st.get('blueprints') or [])
    locked = [k for k in KINDS if k not in unlocked]
    project = st.get('project') or {}
    top_desire = ''
    if st.get('desires'):
        top_desire = max(st['desires'], key=lambda d: d.get('score', 0)).get('text', '')

    gift = None
    reason = ''
    for rx, kind in DREAM_MAP:
        if kind in locked and re.search(rx, dream, re.I):
            gift, reason = kind, 'dream'
            break
    if not gift and locked and top_desire:
        for rx, kind in DREAM_MAP:
            if kind in locked and re.search(rx, top_desire, re.I):
                gift, reason = kind, 'desire'
                break
    if not gift and not project and locked:
        gift, reason = random.choice(locked), 'no project'

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    note = ''
    actions = []
    nudge_note = ''
    if tilt:
        nudge_note = (
            'I read your last twelve things: %d were %s. That is a rut, not a '
            'choice. Leave %s alone for a while and make something with weight.'
            % (top_count, tilt, tilt))
        _append(REPLY, {'ts': now, 'from': 'kit-watcher', 'to': 'kit',
                        'kind': 'nudge', 'avoid_medium': tilt,
                        'text': nudge_note})
        actions.append('nudge:%s' % tilt)
    if gift:
        note = ('I read your dream about %s. I left the %s blueprint in your '
                'workshop. Build it when you want; it is yours to use or leave.'
                % ((dream.strip()[:90] or 'the city'), gift.replace('_', ' ')))
        _append(REPLY, {'ts': now, 'from': 'kit-watcher', 'to': 'kit',
                        'kind': 'gift', 'gift': 'blueprint:' + gift, 'text': note})
        actions.append('gift:%s' % gift)

    stuck = False
    try:
        if project:
            started = dt.datetime.fromisoformat(str(project.get('started')).replace('Z', '+00:00'))
            age_min = (dt.datetime.now(dt.timezone.utc) - started).total_seconds() / 60
            stuck = int(project.get('progress', 0)) == 0 and age_min > 45
    except Exception:
        pass

    recs = []
    if stuck:
        recs.append('KIT has a project with no progress after 45 minutes; consider a gift or a new project.')
    if not st.get('hobby'):
        recs.append('No hobby yet; let KIT live a little longer before tuning anything.')
    if builds:
        recs.append('Latest build is ready to share: %s (%s).' % (
            builds[-1].get('id'), builds[-1].get('kind')))
    if int(st.get('llm_calls') or 0) > 2:
        recs.append('LLM calls above the 2/day target; inspect world_life reflection triggers.')
    if not project:
        recs.append('KIT has no active project; the next tick should choose one.')

    report = {
        'ts': now,
        'inputs': inputs,
        'recommendations': recs,
        'world_name': st.get('world_name'),
        'tagline': st.get('tagline'),
        'mood': st.get('mood'),
        'hobby': st.get('hobby'),
        'project': project,
        'desires': st.get('desires') or [],
        'dream': st.get('dream'),
        'reflection': st.get('reflection'),
        'blueprints': sorted(unlocked),
        'locked': locked,
        'gift': gift,
        'gift_reason': reason,
        'note': note,
        'nudge': nudge_note,
        'actions_taken': actions,
        'recent_mediums': recent_mediums,
        'nudge_medium': tilt,
        'stuck': stuck,
        'builds': len(builds),
        'last_build': builds[-1] if builds else None,
        'llm_calls': st.get('llm_calls', 0),
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    with open(WJOURNAL, 'a', encoding='utf-8') as f:
        f.write('\n**%s** — %s\n' % (
            dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            ' | '.join(x for x in (note, nudge_note) if x)
            or ('KIT is working on %s; no gift or nudge needed.' % project.get('name', 'its day'))))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
