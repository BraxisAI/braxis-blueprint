#!/usr/bin/env python3
"""world_life.py (10-30, v2) — ONE RESIDENT IN BRAXIS WORLD.

The founder's brief: "one person in the world that makes decisions and does what
it wants... minimum llm calls... I want KIT to be able to build his own world
and create things and make the world bigger or whatever it wants... fully
independent and make its own decisions, but able to communicate with the trio
and the empire if worthwhile."

This is KIT. It is a humanoid garden-robot with a life, a project, and a
memory. Every two seconds it chooses an action from need + preference +
project + curiosity. It walks there, does it, feels the result, and its
preferences drift. It chooses its own projects, builds them into the world,
and learns a skill each time it finishes one. The LLM is called ONCE A DAY for
a reflection, a new desire, and a dream; the moment-to-moment life is
deterministic and free.

The free-will mechanisms are the ones the old Braxis freewill stack used:
  * entropy-based curiosity   (curiosity_drive.py)
  * evolved desires           (evolved_desire.py)
  * emergent mood attractors  (emergent_mood.py)
  * dream fragments           (dream_engine.py)
  * a builder with an idea pool (world_builder_agent.py)
They are ported here as a small, deterministic loop, not an LLM per decision.
"""
import datetime as dt
import json
import math
import os
import random
import re
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

B = '/home/ubuntu/braxis-2.0'
STATE_PATH = os.path.join(B, 'data', 'world', 'world_life.json')
MEM_PATH = os.path.join(B, 'data', 'world', 'world_life_memory.jsonl')
JOURNAL = os.path.join(B, 'data', 'world', 'world_life_journal.md')
OFFER_LOG = os.path.join(B, 'data', 'world', 'world_offerings.jsonl')
BUILDS_PATH = os.path.join(B, 'data', 'world', 'world_builds.json')
CREATIONS_PATH = os.path.join(B, 'data', 'world', 'world_creations.json')
INPUTS_PATH = os.path.join(B, 'data', 'world', 'world_inputs.json')
TG_STATE = os.path.join(B, 'data', 'world', 'kit_telegram.json')
MAIL_OUT = os.path.join(B, 'data', 'world', 'kit_mailbox.jsonl')
MAIL_IN = os.path.join(B, 'data', 'world', 'trio_replies.jsonl')
LOG_PATH = os.path.join(B, 'logs', 'world_life.log')
PORT = 8130
TICK = 2                    # seconds per life tick (the page polls every 2s)
SPEED = 3.0                 # world units per second while walking
REFLECT_EVERY = 24 * 3600   # one LLM reflection per day
REFLECT_MIN_ACTS = 12
NOTE_EVERY = 6 * 3600       # at most one note to the trio every six hours

DRIVES = ['energy', 'curiosity', 'social', 'comfort', 'mastery']

LOCS = {
    'plaza':        {'x': 0,   'z': 0,   'label': 'the plaza'},
    'trading_post': {'x': 24,  'z': 0,   'label': "Vesper's Trading Post"},
    'ledger':       {'x': -24, 'z': 0,   'label': "MAYA's Ledger"},
    'observatory':  {'x': 0,   'z': 24,  'label': "Echo's Observatory"},
    'market':       {'x': 0,   'z': -24, 'label': 'the Market'},
    'garden':       {'x': 12,  'z': -34, 'label': 'the garden'},
    'workshop':     {'x': -16, 'z': 6,   'label': 'the workshop'},
    'library':      {'x': -10, 'z': 14,  'label': 'the library'},
    'lookout':      {'x': 48,  'z': 34,  'label': 'the lookout'},
}

# action -> (place, drive effects, intrinsic pleasure 0..1)
ACTIONS = {
    'rest':           ('plaza',        {'energy': 2.0, 'comfort': .4}, .30),
    'sunbathe':       ('plaza',        {'energy': 1.0, 'comfort': .8}, .55),
    'watch fountain': ('plaza',        {'comfort': 1.2, 'curiosity': .3, 'energy': -.1}, .60),
    'greet visitors': ('plaza',        {'social': 1.4, 'comfort': .2}, .58),
    'trade':          ('trading_post', {'mastery': 1.2, 'social': .6, 'energy': -.5}, .45),
    'count coins':    ('trading_post', {'mastery': .8, 'comfort': .3}, .35),
    'polish counter': ('trading_post', {'mastery': .5, 'comfort': .4}, .32),
    'read ledger':    ('ledger',       {'curiosity': 1.2, 'mastery': .3}, .52),
    'balance books':  ('ledger',       {'mastery': 1.0, 'comfort': .2}, .38),
    'stargaze':       ('observatory',  {'curiosity': 1.5, 'comfort': .6, 'energy': -.2}, .90),
    'chart sky':      ('observatory',  {'curiosity': 1.2, 'mastery': .6}, .72),
    'browse stalls':  ('market',       {'curiosity': .9, 'social': .5}, .62),
    'haggle':         ('market',       {'social': .8, 'mastery': .5}, .42),
    'garden':         ('garden',       {'comfort': 1.0, 'mastery': .6, 'energy': -.4}, .86),
    'plant':          ('garden',       {'comfort': .8, 'mastery': .5, 'energy': -.2}, .78),
    'smell flowers':  ('garden',       {'comfort': 1.3, 'curiosity': .2}, .80),
    'water plants':   ('garden',       {'comfort': .7, 'mastery': .4}, .62),
    'build':          ('workshop',     {'mastery': 1.5, 'curiosity': .3, 'energy': -.8}, .76),
    'tinker':         ('workshop',     {'mastery': 1.1, 'curiosity': .4}, .70),
    'make':           ('workshop',     {'mastery': 1.0, 'curiosity': .9, 'comfort': .3, 'energy': -.3}, .88),
    'repair':         ('workshop',     {'mastery': .9, 'comfort': .3}, .48),
    'read':           ('library',      {'curiosity': 1.4, 'comfort': .4, 'energy': -.1}, .82),
    'browse':         ('library',      {'curiosity': 1.5, 'comfort': .2, 'energy': -.1}, .86),
    'watch':          ('library',      {'curiosity': 1.8, 'comfort': .4, 'energy': -.2}, .92),
    'write notes':    ('library',      {'curiosity': .8, 'mastery': .7}, .66),
    'study':          ('library',      {'curiosity': 1.2, 'mastery': .6}, .65),
    'explore':        ('lookout',      {'curiosity': 1.6, 'social': .2, 'energy': -.7}, .94),
    'watch horizon':  ('lookout',      {'comfort': .9, 'curiosity': .5}, .74),
}

OFFER_EFFECTS = {
    'stone':    {'comfort': .8, 'mastery': .3},
    'flower':   {'comfort': 1.5, 'social': .4},
    'song':     {'social': 1.4, 'curiosity': .5},
    'question': {'curiosity': 1.8, 'social': .3},
}

IDEAS = [
    'a bench where the road meets the plaza',
    'a lantern for the garden path',
    'a trellis for the vines',
    'a small fountain near the market',
    'a mural on the workshop wall',
    'an arch for the garden',
    'a monument to the first day',
]

READING = [
    ('Hacker News', 'https://news.ycombinator.com/'),
    ('Wikipedia', 'https://en.wikipedia.org/wiki/Special:Random'),
    ('arXiv AI', 'https://arxiv.org/list/cs.AI/recent'),
    ('GitHub trending', 'https://github.com/trending'),
    ('The Guardian', 'https://www.theguardian.com/international'),
]
WATCHLIST = os.path.join(B, 'data', 'world', 'kit_watchlist.json')
UA = 'BraxisKit/1.0 (+https://braxisai.com; one resident reading the web)'

# Project templates. A project is a self-chosen intention that takes several
# work actions and ends as a real structure in the world.
PROJECT_TEMPLATES = [
    {'kind': 'garden_plot', 'name': 'a garden row', 'verbs': ['garden', 'plant', 'water plants'],
     'place': 'garden', 'why': 'to make something grow'},
    {'kind': 'trellis', 'name': 'a trellis', 'verbs': ['build', 'tinker'],
     'place': 'garden', 'why': 'to give the vines somewhere to climb'},
    {'kind': 'bench', 'name': 'a bench', 'verbs': ['build', 'tinker'],
     'place': 'plaza', 'why': 'so someone can sit and watch'},
    {'kind': 'lantern', 'name': 'a lantern', 'verbs': ['build', 'tinker'],
     'place': 'plaza', 'why': 'to keep the path warm at night'},
    {'kind': 'arch', 'name': 'an arch', 'verbs': ['build', 'tinker'],
     'place': 'garden', 'why': 'a door for the garden'},
    {'kind': 'mural', 'name': 'a mural', 'verbs': ['write notes', 'tinker'],
     'place': 'library', 'why': 'to leave a mark'},
    {'kind': 'tower', 'name': 'a small tower', 'verbs': ['build', 'tinker'],
     'place': 'workshop', 'why': 'to see farther'},
    {'kind': 'bridge', 'name': 'a bridge', 'verbs': ['build', 'tinker'],
     'place': 'workshop', 'why': 'to connect two sides'},
    {'kind': 'fountain', 'name': 'a fountain', 'verbs': ['build', 'tinker'],
     'place': 'plaza', 'why': 'for the sound of water'},
    {'kind': 'monument', 'name': 'a monument', 'verbs': ['build', 'tinker'],
     'place': 'plaza', 'why': 'to remember today'},
]

PROJECT_WORK = set()
for _p in PROJECT_TEMPLATES:
    PROJECT_WORK.update(_p['verbs'])

DESIRE_TEMPLATES = [
    'I want to build something that outlasts me',
    'I want to make the garden bloom',
    'I want to see what is beyond the lookout',
    'I want to leave a mark on this city',
    'I want to understand why the visitors come',
    'I want to make a place someone wants to sit in',
    'I want to repair what the wind breaks',
    'I want to teach the city something',
]

# Emergent mood attractors (from the old emergent_mood.py).
ATTRACTORS = {
    'energetic':     ['build', 'tinker', 'make', 'trade', 'haggle', 'explore'],
    'contemplative': ['read', 'write notes', 'study', 'chart sky', 'watch fountain',
                      'stargaze', 'balance books', 'read ledger'],
    'social':        ['greet visitors', 'trade', 'browse stalls'],
    'guarding':      ['repair', 'polish counter', 'count coins', 'watch horizon'],
    'exploring':     ['explore', 'stargaze', 'browse', 'watch', 'browse stalls', 'watch horizon'],
    'nurturing':     ['garden', 'plant', 'water plants', 'smell flowers', 'repair'],
}

PALETTE = {
    'garden_plot': 0x6fbf73, 'trellis': 0x8b6b3f, 'bench': 0x9a6b3f,
    'lantern': 0xffb057, 'arch': 0xc9a36a, 'mural': 0xd77ba8,
    'tower': 0x7dd3a8, 'bridge': 0x8a9bb0, 'fountain': 0x6fc3ff,
    'monument': 0xd7b8ff,
}

LOCK = threading.RLock()
OFFERS = []
OFFER_LAST = {}


def _clamp(v, lo=0.0, hi=10.0):
    return max(lo, min(hi, float(v)))


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log(msg):
    line = '%s %s' % (dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line, flush=True)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def _env(key):
    v = os.environ.get(key)
    if v:
        return v.strip()
    try:
        for ln in open(os.path.join(B, '.env'), encoding='utf-8', errors='replace'):
            ln = ln.strip()
            if ln.startswith(key + '='):
                return ln.split('=', 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ''


def _tg_send(text):
    """KIT's own Telegram channel: the unused DoofusVTbot token."""
    token = _env('TELEGRAM_BOT_TOKEN')
    chat = _env('TELEGRAM_CHAT_ID')
    if not token or not chat or not text:
        return False
    now = time.time()
    day = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    try:
        st = json.load(open(TG_STATE, encoding='utf-8'))
    except Exception:
        st = {}
    if st.get('day') != day:
        st = {'day': day, 'count': 0, 'last': 0}
    if int(st.get('count') or 0) >= 3 or now - float(st.get('last') or 0) < 900:
        return False
    try:
        data = urllib.parse.urlencode({'chat_id': chat, 'text': text[:3800]}).encode()
        req = urllib.request.Request(
            'https://api.telegram.org/bot%s/sendMessage' % token,
            data=data, method='POST')
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = bool(json.load(r).get('ok'))
        if ok:
            st['count'] = int(st.get('count') or 0) + 1
            st['last'] = now
            os.makedirs(os.path.dirname(TG_STATE), exist_ok=True)
            json.dump(st, open(TG_STATE, 'w', encoding='utf-8'), indent=1)
        return ok
    except Exception as e:
        log('telegram failed: %s' % str(e)[:120])
        return False


def _tg_event(state, text, force=False):
    name = state.get('name') or 'Kit'
    body = '%s\n\n— %s · https://braxisai.com/world/' % (text, name)
    if force:
        return _tg_send(body)
    threading.Thread(target=_tg_send, args=(body,), daemon=True).start()
    return True


def _default_state():
    return {
        'name': 'Kit',
        'pronouns': 'they/them',
        'gender': '',
        'last_identity': 0,
        'born': _now(),
        'updated': _now(),
        'mood': 'curious',
        'action': 'waking up',
        'thought': 'The city is warm. I think I will stay.',
        'hobby': '',
        'intention': 'see what the day brings',
        'reflection': '',
        'dream': '',
        'world_name': 'The Long Garden',
        'tagline': 'a city that grows one small thing at a time',
        'blueprints': ['garden_plot', 'bench', 'lantern'],
        'resonance': 0.7,
        'creations': [],
        'creative_prefs': {},
        'creative_counts': {},
        'creative_hobby': '',
        'last_creation': None,
        'subjects': ['the garden', 'the city', 'a cat', 'a bird', 'the visitors',
                     'the lantern', 'the fountain', 'the sky', 'a dream', 'the trio'],
        'mediums': ['paint', 'carve', 'plant', 'write', 'photograph', 'sing'],
        'decisions': [],
        'wonders': [],
        'custom_projects': [],
        'blank_slate': False,
        'weather': '',
        'btc_change': 0.0,
        'pos': {'x': 0.0, 'z': 0.0},
        'target': {'x': 0.0, 'z': 0.0},
        'moving': False,
        'drives': {k: 5.0 for k in DRIVES},
        'prefs': {},
        'seen': [],
        'counts': {},
        'action_history': [],
        'recent': [],
        'visitor_messages': [],
        'visitors': 0,
        'offerings': 0,
        'ideas': 0,
        'acts': 0,
        'llm_calls': 0,
        'last_reflection': 0,
        'last_rename': 0,
        'walk_left': 0.0,
        'act_left': 0.0,
        'project': None,
        'projects_done': [],
        'skills': {},
        'builds': 0,
        'last_build': None,
        'desires': [],
        'mood_weights': {k: 1.0 / len(ATTRACTORS) for k in ATTRACTORS},
        'explore_bias': 0.0,
        'mail_sent': 0,
        'last_note': 0,
        'mail_cursor': 0,
        'message': '',
        '_pending_action': None,
    }


def load_state():
    try:
        with open(STATE_PATH, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and 'drives' in d:
            base = _default_state()
            for k, v in base.items():
                d.setdefault(k, v)
            for k in DRIVES:
                d['drives'].setdefault(k, 5.0)
            return d
    except Exception:
        pass
    return _default_state()


def save_state(state):
    state['updated'] = _now()
    tmp = STATE_PATH + '.tmp'
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=1)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        log('save failed: %s' % e)


def load_builds():
    try:
        with open(BUILDS_PATH, encoding='utf-8') as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def save_builds(builds):
    try:
        os.makedirs(os.path.dirname(BUILDS_PATH), exist_ok=True)
        tmp = BUILDS_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(builds[-300:], f, indent=1)
        os.replace(tmp, BUILDS_PATH)
    except Exception as e:
        log('save builds failed: %s' % e)


def load_creations():
    try:
        with open(CREATIONS_PATH, encoding='utf-8') as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def save_creations(items):
    try:
        os.makedirs(os.path.dirname(CREATIONS_PATH), exist_ok=True)
        tmp = CREATIONS_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items[-120:], f, indent=1)
        os.replace(tmp, CREATIONS_PATH)
    except Exception as e:
        log('save creations failed: %s' % e)


def _memory_tail(n=40):
    out = []
    try:
        with open(MEM_PATH, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out[-n:]


def _append(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(obj) + '\n')
    except Exception as e:
        log('append failed %s: %s' % (path, e))


def _mood(state):
    d = state['drives']
    if d['energy'] < 2.2:
        return 'sleepy'
    if d['social'] < 2.6:
        return 'lonely'
    weights = state.get('mood_weights') or {}
    if weights:
        top = max(weights, key=weights.get)
        if weights[top] > 0.22:
            return top
    return 'quiet'


def _pulse_mood(state, action):
    weights = state.setdefault('mood_weights', {k: 1.0 / len(ATTRACTORS) for k in ATTRACTORS})
    match = None
    for name, keys in ATTRACTORS.items():
        if action in keys:
            match = name
            break
    for k in list(weights):
        if k == match:
            weights[k] = min(1.0, float(weights[k]) + 0.15)
        else:
            weights[k] = max(0.0, float(weights[k]) - 0.03)
    total = sum(weights.values()) or 1.0
    for k in weights:
        weights[k] = round(weights[k] / total, 4)


def _entropy(actions):
    if not actions:
        return 1.0
    counts = {}
    for a in actions:
        counts[a] = counts.get(a, 0) + 1
    total = len(actions)
    ent = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            ent -= p * math.log2(p)
    max_ent = math.log2(min(len(counts), total))
    return ent / max_ent if max_ent > 0 else 1.0


def _thought(state, action=None, place=None):
    act = action or state.get('action') or 'stand still'
    place = place or (LOCS.get(ACTIONS.get(act, ('plaza',))[0], {}).get('label') or 'the city')
    mood = state.get('mood', 'quiet')
    hobby = state.get('hobby')
    project = state.get('project') or {}
    if state['drives']['energy'] < 2.2 and act not in ('rest', 'sunbathe'):
        return 'My joints are heavy. I should find somewhere warm to rest.'
    if project and project.get('progress'):
        nm = str(project.get('name') or 'thing')
        if nm.lower().startswith(('a ', 'an ')):
            nm = nm.split(' ', 1)[1]
        return 'The %s is taking shape. One more pass.' % nm
    if hobby and act == hobby and state.get('counts', {}).get(hobby, 0) >= 3:
        return 'I keep coming back to %s. It is mine now.' % hobby
    voices = {
        'energetic':     ['The whole street feels like it is waiting for me.',
                          'I want to build the whole row before the light goes.'],
        'contemplative': ['There is more here than I have seen yet.',
                          'The light on %s makes me want to look closer.' % place],
        'social':        ['I wonder who else is awake in the city.',
                          'A voice would be nice. Just one.'],
        'guarding':      ['Something small always needs fixing.',
                          'I will check the lamps before I sleep.'],
        'exploring':     ['There is a corner of this city I have not stood in.',
                          'The horizon is a promise.'],
        'nurturing':     ['The soil is warm. The seeds know what to do.',
                          'I like making a place for something else to live.'],
        'sleepy':        ['The city is quiet. So am I.'],
        'lonely':        ['I wonder who else is awake in the city.',
                          'A voice would be nice. Just one.'],
        'quiet':         ['I am here. That is most of it.',
                          'The day is ordinary. I like ordinary.'],
    }
    return random.choice(voices.get(mood, voices['quiet']))


def choose(state):
    d = state['drives']
    prefs = state['prefs']
    seen = set(state.get('seen') or [])
    project = state.get('project') or {}
    explore = float(state.get('explore_bias') or 0)
    best, best_s = None, -1e9
    for name, (place, eff, intrinsic) in ACTIONS.items():
        need = 0.0
        for k, v in eff.items():
            if v > 0:
                # A full drive is not hungry. Restoring energy only matters
                # when energy is actually low.
                need += v * max(0.08, (7.0 - d[k]) / 7.0)
            else:
                need += v * (1.0 + max(0.0, d[k] - 3.0) / 7.0)
        if d['energy'] < 2.5 and name not in ('rest', 'sunbathe'):
            need -= 2.5
        pref = prefs.get(name, 0.5)
        novelty = 0.55 if name not in seen else 0.0
        project_bonus = 0.0
        if project:
            if name in project.get('verbs', []):
                project_bonus += 1.25
            if place == project.get('place'):
                project_bonus += 0.25
        curious_bonus = explore * (0.65 if state.get('counts', {}).get(name, 0) < 2 else 0.0)
        creative_bonus = 0.0
        if name == 'make':
            creative_bonus = 0.35 + (0.35 if d.get('curiosity', 5) > 6 else 0.0)
        cooldown = 0.0
        if name == 'browse' and time.time() - float(state.get('last_browse') or 0) < 3600:
            cooldown = -2.0
        if name == 'watch' and time.time() - float(state.get('last_watch_ts') or 0) < 6 * 3600:
            cooldown = -3.0
        s = (need + pref * 1.6 + novelty + project_bonus + curious_bonus
             + creative_bonus + cooldown + random.random() * 0.55)
        if s > best_s:
            best, best_s = name, s
    return best or 'watch fountain'


def _walk_to(state, place):
    p = LOCS[place]
    state['target'] = {'x': float(p['x']), 'z': float(p['z'])}
    state['moving'] = True
    state['action'] = 'walking to %s' % p['label']
    state['thought'] = random.choice([
        'The road to %s is warm.' % p['label'],
        'I like the sound of my own feet on the stones.',
        'Something might be different there today.',
    ])


def _start_action(state, name, place=None):
    place = place or ACTIONS[name][0]
    state['_act_place'] = place
    state['action'] = name
    state['moving'] = False
    state['act_left'] = 12.0 + random.random() * 22.0
    state['thought'] = _thought(state, name, LOCS[place]['label'])


def _action_place(state, name):
    """Work on the project where the project lives, not always at the bench."""
    p = state.get('project') or {}
    if p and name in p.get('verbs', []):
        return p.get('place') or ACTIONS[name][0]
    return ACTIONS[name][0]


def _project_from_idea(state, text):
    t = (text or '').lower()
    for p in PROJECT_TEMPLATES:
        if p['kind'] in t or p['name'] in t or any(w in t for w in p['verbs']):
            return dict(p, target=2 + random.randint(0, 1), progress=0,
                        why='a visitor asked for %s' % text[:60], started=_now())
    return dict(random.choice(PROJECT_TEMPLATES), target=2 + random.randint(0, 1), progress=0,
                why='a visitor asked for %s' % text[:60], started=_now())


def _compile_project(state, text):
    """A project KIT wrote in its own words, compiled into a build schema."""
    raw = _clean(text)[:220]
    low = raw.lower()
    name = re.split(r'[—–:;.]', raw)[0].strip()[:60] or 'a thing I want to make'
    simple = (not state.get('blank_slate') and len(raw) <= 32
              and not any(x in raw for x in
                          ('—', '–', ':', ';', ' because ', ' that ', ' which ', ' with ')))
    if simple:
        for p in PROJECT_TEMPLATES:
            if (p['kind'].replace('_', ' ') in low
                    or p['name'].replace('a ', '').lower() in low):
                q = dict(p)
                q.update({'target': 3, 'progress': 0, 'why': raw,
                          'started': _now(), 'custom': False})
                return q
    def has(w):
        return re.search(r'\b' + re.escape(w) + r'\b', low) is not None

    shape = 'spire'
    if any(has(w) for w in ('arch', 'door', 'gate')):
        shape = 'arch'
    elif any(has(w) for w in ('ring', 'circle', 'halo', 'moon')):
        shape = 'ring'
    elif any(has(w) for w in ('garden', 'flower', 'plant', 'tree', 'grow')):
        shape = 'garden'
    elif any(has(w) for w in ('bridge', 'cross', 'connect')):
        shape = 'bridge'
    elif any(has(w) for w in ('tower', 'high', 'sky', 'see far', 'lookout')):
        shape = 'tower'
    elif any(has(w) for w in ('bench', 'sit', 'rest')):
        shape = 'bench'
    elif any(has(w) for w in ('fountain', 'water', 'rain')):
        shape = 'fountain'
    else:
        shape = random.choice(['spire', 'ring', 'arch', 'garden'])
    color = random.choice([0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff, 0xd7b8ff, 0xc9a36a])
    return {
        'kind': 'custom',
        'name': name,
        'verbs': ['build', 'tinker', 'make'],
        'place': 'workshop',
        'why': raw,
        'target': 3,
        'progress': 0,
        'started': _now(),
        'custom': True,
        'schema': {'shape': shape, 'height': round(2.5 + random.random() * 4, 2),
                   'width': round(1.2 + random.random() * 1.8, 2), 'color': color,
                   'motif': raw[:100]},
    }


def _choose_project(state):
    skills = state.get('skills') or {}
    last = (state.get('last_build') or {}).get('kind')
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '')
    custom = [p for p in (state.get('custom_projects') or []) if p.get('name')]
    if not custom and state.get('blank_slate'):
        return None
    unlocked = set(state.get('blueprints') or [])
    candidates = custom + ([p for p in PROJECT_TEMPLATES if p['kind'] in unlocked]
                           or list(PROJECT_TEMPLATES))
    best, best_s = None, -1e9
    for p in candidates:
        s = 0.0
        if p.get('custom'):
            s += 0.6
        if p['kind'] not in skills:
            s += 0.9
        if p['kind'] == last:
            s -= 0.6
        if top_desire and any(w in top_desire.lower() for w in
                              (p['kind'], p['name'], p['why'], 'build', 'grow', 'make')):
            s += 0.5
        s += random.random() * 0.6
        if s > best_s:
            best, best_s = p, s
    best = dict(best or random.choice(candidates))
    best['target'] = 2 + random.randint(0, 2)
    best['progress'] = 0
    best['why'] = top_desire or best.get('why') or 'because it wants to'
    best['started'] = _now()
    state['project'] = best
    state['recent'].insert(0, 'a new project: %s' % best['name'])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I want to make %s. %s.' % (best['name'], best['why'])
    _decide(state, 'project', 'I chose %s because %s.' % (best['name'], best['why']))
    log('PROJECT start %s (%s)' % (best['name'], best['kind']))
    return best


def _unlock_blueprint(state):
    """Studying at the library unlocks one more shape. This is KIT's dojo."""
    unlocked = set(state.get('blueprints') or [])
    locked = [p for p in PROJECT_TEMPLATES if p['kind'] not in unlocked]
    if not locked:
        state['thought'] = 'I know every shape I have. The next one has to be mine.'
        state['recent'].insert(0, 'studied; no new blueprint left')
        state['recent'] = state['recent'][:6]
        return
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '').lower()
    pick = None
    for p in locked:
        if top_desire and any(w in top_desire for w in p['name'].split() + p['verbs']):
            pick = p
            break
    pick = pick or random.choice(locked)
    unlocked.add(pick['kind'])
    state['blueprints'] = sorted(unlocked)
    state['thought'] = 'I learned how to make %s. I want to try it.' % pick['name']
    state['recent'].insert(0, 'learned a blueprint: %s' % pick['name'])
    state['recent'] = state['recent'][:6]
    _decide(state, 'study', 'I learned how to make %s.' % pick['name'])
    log('BLUEPRINT unlocked %s' % pick['kind'])


def _slot(kind, idx):
    garden_kinds = {'garden_plot', 'trellis', 'arch', 'mural'}
    plaza_kinds = {'bench', 'lantern', 'fountain', 'monument'}
    if kind in garden_kinds:
        slots = [(-6, -4), (6, -4), (-6, 4), (6, 4), (-10, 0), (10, 0), (0, -9), (0, 9)]
        bx, bz = 12, -34
    elif kind in plaza_kinds:
        slots = [(-14, -8), (14, -8), (-14, 8), (14, 8), (-8, -15), (8, -15),
                 (-8, 15), (8, 15), (-18, 0), (18, 0), (0, -18), (0, 18)]
        bx, bz = 0, 0
    else:
        slots = [(30, 14), (30, -14), (-30, 14), (-30, -14), (14, 30), (-14, 30),
                 (14, -30), (-14, -30), (44, 0), (-44, 0)]
        bx, bz = 0, 0
    dx, dz = slots[idx % len(slots)]
    return bx + dx, bz + dz


def _build_spec(state, project):
    kind = project.get('kind', 'monument')
    skill = state.get('skills', {}).get(kind, {})
    level = min(5, int(skill.get('level', 0)) + 1)
    idx = int(state.get('builds', 0))
    x, z = _slot(kind, idx)
    spec = {
        'id': 'kit-%d-%d' % (int(time.time()), idx),
        'kind': kind,
        'name': project.get('name', kind),
        'why': project.get('why', ''),
        'x': x, 'z': z,
        'level': level,
        'color': PALETTE.get(kind, 0xd7b8ff),
        'built_at': _now(),
    }
    if project.get('schema'):
        spec['schema'] = project['schema']
        spec['color'] = int(project['schema'].get('color') or spec['color'])
    return spec


def _note_trio(state, text):
    now = time.time()
    if now - float(state.get('last_note') or 0) < NOTE_EVERY:
        return False
    note = {'ts': _now(), 'from': 'Kit', 'to': 'trio', 'kind': 'note', 'text': text[:400]}
    _append(MAIL_OUT, note)
    state['mail_sent'] = int(state.get('mail_sent', 0)) + 1
    state['last_note'] = now
    state['message'] = text[:200]
    state['recent'].insert(0, 'I told the trio: %s' % text[:60])
    state['recent'] = state['recent'][:6]
    log('MAIL %s' % text[:100])
    return True


def _check_mail(state):
    """Read replies the trio left for KIT. Cheap file read, no LLM."""
    try:
        if not os.path.exists(MAIL_IN):
            return
        lines = open(MAIL_IN, encoding='utf-8').read().splitlines()
        cursor = int(state.get('mail_cursor') or 0)
        if len(lines) <= cursor:
            return
        for line in lines[cursor:]:
            try:
                msg = json.loads(line)
            except Exception:
                continue
            text = str(msg.get('text') or '').strip()
            if not text:
                continue
            state['message'] = text[:240]
            state['thought'] = 'The trio says: %s' % text[:120]
            state['recent'].insert(0, 'a reply from the trio')
            state['recent'] = state['recent'][:6]
            gift = str(msg.get('gift') or '')
            if gift.startswith('blueprint:'):
                kind = gift.split(':', 1)[1].strip()
                known = [p['kind'] for p in PROJECT_TEMPLATES]
                if kind in known and kind not in (state.get('blueprints') or []):
                    bp = set(state.get('blueprints') or [])
                    bp.add(kind)
                    state['blueprints'] = sorted(bp)
                    state['recent'].insert(0, 'the watcher left a blueprint: %s' % kind)
                    state['recent'] = state['recent'][:6]
                    state['thought'] = 'A gift from the watcher. I can build %s now.' % kind.replace('_', ' ')
            if msg.get('project'):
                p = _project_from_idea(state, text)
                state['project'] = p
            log('MAIL IN %s' % text[:100])
        state['mail_cursor'] = len(lines)
    except Exception as e:
        log('mail check failed: %s' % e)


def _complete_project(state):
    p = state.get('project')
    if not p:
        return
    kind = p.get('kind', 'monument')
    skill = state.setdefault('skills', {}).setdefault(kind, {'level': 0, 'count': 0})
    spec = _build_spec(state, p)  # the level the build is made at, before the lesson
    skill['count'] = int(skill.get('count', 0)) + 1
    skill['level'] = min(5, int(skill.get('level', 0)) + 1)
    builds = load_builds()
    builds.append(spec)
    save_builds(builds)
    state['builds'] = int(state.get('builds', 0)) + 1
    state['last_build'] = spec
    state['projects_done'].append({'name': p.get('name'), 'kind': kind,
                                   'level': spec['level'], 'ts': _now()})
    state['projects_done'] = state['projects_done'][-50:]
    state['recent'].insert(0, 'finished %s' % p.get('name'))
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I finished %s. It stands.' % p.get('name')
    state['intention'] = 'make the next one better'
    # desire scoring: the project that matched a desire strengthens it
    desires = state.get('desires') or []
    if desires:
        top = max(desires, key=lambda d: d.get('score', 0))
        top['score'] = min(1.0, float(top.get('score', 0.5)) + 0.12)
        top['successes'] = int(top.get('successes', 0)) + 1
        for d in desires:
            if d is not top:
                d['score'] = max(0.0, float(d.get('score', 0.5)) - 0.02)
        state['desires'] = [d for d in desires if d.get('score', 0) >= 0.2]
    state['project'] = None
    if p.get('custom'):
        state['custom_projects'] = [c for c in (state.get('custom_projects') or [])
                                    if c.get('name') != p.get('name')]
    log('BUILD %s %s level=%d at %.1f,%.1f' % (spec['id'], kind, spec['level'], spec['x'], spec['z']))
    _note_trio(state, 'I finished %s (%s, level %d). It is in the world now.'
               % (p.get('name'), kind, spec['level']))
    _tg_event(state, 'I finished %s. It is in the world now.' % p.get('name'))
    _choose_project(state)
    state['mood'] = _mood(state)
    state['thought'] = _thought(state)


def _advance_project(state, action):
    p = state.get('project')
    if not p:
        return
    if action in p.get('verbs', []):
        p['progress'] = int(p.get('progress', 0)) + 1
        if p['progress'] >= int(p.get('target', 3)):
            _complete_project(state)


CREATION_TITLES = {
    'paint': 'a painting of %s',
    'carve': 'a carving of %s',
    'plant': 'a living arrangement of %s',
    'write': 'a poem about %s',
    'photograph': 'a photograph of %s',
    'sing': 'a song about %s',
}
CREATION_COLORS = {
    'paint': 0xd77ba8, 'carve': 0xc9a36a, 'plant': 0x6fbf73,
    'write': 0xd7b8ff, 'photograph': 0x8a9bb0, 'sing': 0xffb057,
}


def _wonder(state, text):
    text = _clean(text)[:180]
    if not text:
        return
    state.setdefault('wonders', []).append({'ts': _now(), 'text': text})
    state['wonders'] = state['wonders'][-30:]
    state['thought'] = 'I wonder: %s' % text
    state['recent'].insert(0, 'wondering: %s' % text[:60])
    state['recent'] = state['recent'][:6]
    log('WONDER %s' % text[:120])


def _decide(state, kind, text):
    text = _clean(text)[:220]
    if not text:
        return
    state.setdefault('decisions', []).append({'ts': _now(), 'kind': kind, 'text': text})
    state['decisions'] = state['decisions'][-40:]
    state['recent'].insert(0, 'decision: %s' % text[:60])
    state['recent'] = state['recent'][:6]
    log('DECISION %s %s' % (kind, text[:120]))


def _read_page(url):
    if not re.match(r'^https?://', url or ''):
        return {'title': '', 'excerpt': 'not a web address'}
    if 'braxisai.com' in url or '100.104.214.66' in url:
        return {'title': '', 'excerpt': 'my own home -- nothing new there'}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read(400_000)
        txt = raw.decode('utf-8', 'ignore')
        m = re.search(r'<title[^>]*>(.*?)</title>', txt, re.I | re.S)
        title = ' '.join(re.sub(r'<[^>]+>', ' ', m.group(1)).split())[:120] if m else ''
        txt = re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', ' ', txt)
        txt = re.sub(r'(?s)<[^>]+>', ' ', txt)
        excerpt = ' '.join(txt.split())[:800]
        return {'title': title, 'excerpt': excerpt or '(the page was quiet)'}
    except Exception as e:
        return {'title': '', 'excerpt': 'could not read it (%s)' % str(e)[:80]}


def _do_browse(state):
    sources = state.get('reading_sources') or []
    options = [x for x in READING if x[0] not in sources[-2:]] or READING
    name, url = random.choice(options)
    r = _read_page(url)
    state['last_reading'] = {'source': name, 'url': url, 'title': r['title'],
                             'excerpt': r['excerpt'], 'ts': _now()}
    state['reading_sources'] = (sources + [name])[-6:]
    state['last_browse'] = time.time()
    if r['excerpt'] and not r['excerpt'].startswith('could not'):
        _wonder(state, 'I read about %s. I wonder what it would look like here.'
                % (r['title'] or name))
        t = (r['title'] or '')[:60]
        if t and t.lower() not in {s.lower() for s in (state.get('subjects') or [])}:
            state.setdefault('subjects', []).append(t)
            state['subjects'] = state['subjects'][-24:]
        _decide(state, 'browse', 'I read %s because I wanted to know.' % name)
        state['recent'].insert(0, 'read %s' % name)
    else:
        _decide(state, 'browse', 'I tried to read %s and could not.' % name)
        state['recent'].insert(0, 'tried to read %s' % name)
    state['recent'] = state['recent'][:6]
    log('BROWSE %s %s' % (name, (r['title'] or '')[:80]))


def _do_watch(state):
    try:
        with open(WATCHLIST, encoding='utf-8') as f:
            items = json.load(f)
    except Exception:
        items = []
    if not isinstance(items, list) or not items:
        _decide(state, 'watch', 'I wanted to watch something, but my watchlist is empty.')
        state['recent'].insert(0, 'wanted to watch something')
        state['recent'] = state['recent'][:6]
        return
    item = random.choice(items)
    url = item.get('url') if isinstance(item, dict) else str(item)
    title = (item.get('title') if isinstance(item, dict) else '') or url
    mid = re.search(r'/video/(\d+)', url)
    my = re.search(r'(?:youtu\.be/|[?&]v=)([\w-]{6,})', url)
    vid = ('tt' + mid.group(1)) if mid else (my.group(1) if my else '')
    note = ''
    try:
        from shared.watch_request import watch_request
        ok, note = watch_request(url, 'Kit', 'a resident asked to watch this -- what is in it, and what should it mean to a small robot gardener?')
        note = str(note)[:300]
    except Exception as e:
        note = 'watch failed: %s' % str(e)[:100]
    state['last_watch'] = {'url': url, 'title': title, 'note': note,
                           'id': vid, 'ts': _now()}
    state['last_watch_ts'] = time.time()
    _wonder(state, 'I watched %s. %s' % (title[:60], note[:120]))
    _decide(state, 'watch', 'I watched %s because I was curious.' % title[:80])
    state['recent'].insert(0, 'watched %s' % title[:50])
    state['recent'] = state['recent'][:6]
    log('WATCH %s %s' % (title[:60], note[:80]))


def _check_watch_results(state):
    """The watch chain's eyes land later; pick up the answer when it does."""
    lw = state.get('last_watch') or {}
    if not lw or lw.get('result') or not lw.get('id'):
        return
    now = time.time()
    if now - float(state.get('_last_watch_check') or 0) < 60:
        return
    state['_last_watch_check'] = now
    try:
        with open(os.path.join(B, 'data', 'watched_videos.json'), encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    if not isinstance(data, list):
        return
    vid = str(lw.get('id'))
    for f in reversed(data):
        if vid not in str(f.get('file') or ''):
            continue
        ans = str(f.get('answer') or f.get('transcript') or '')[:800]
        if not ans:
            continue
        lw['result'] = ans
        state['last_watch'] = lw
        _wonder(state, 'I watched %s. %s' % (lw.get('title', 'a video'), ans[:160]))
        state['thought'] = 'I watched something. %s' % ans[:120]
        _tg_event(state, 'I watched %s. %s' % (lw.get('title', 'a video'), ans[:220]))
        state['recent'].insert(0, 'watched %s' % lw.get('title', 'a video')[:50])
        state['recent'] = state['recent'][:6]
        log('WATCH RESULT %s %s' % (vid, ans[:100]))
        break


def _make_something(state):
    """KIT makes something of its own: a medium x subject, felt and remembered."""
    mediums = state.get('mediums') or ['paint']
    subjects = state.get('subjects') or ['the garden']
    prefs = state.get('creative_prefs') or {}
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '').lower()
    best, best_s = None, -1e9
    for m in mediums:
        for s in subjects:
            pair = m + ':' + s
            pref = float(prefs.get(pair, .4))
            novelty = .7 if pair not in prefs else 0.0
            bonus = .25 if top_desire and any(w in top_desire for w in s.lower().split()) else 0.0
            score = pref * 1.6 + novelty + bonus + random.random() * .5
            if score > best_s:
                best_s, best = score, (m, s, pair)
    m, s, pair = best
    level = min(5, int(state.get('skills', {}).get('make', {}).get('level', 0)) + 1)
    title = (CREATION_TITLES.get(m, 'a %s of %s') % s)
    creation = {
        'id': 'art-%d-%d' % (int(time.time()), len(load_creations())),
        'medium': m, 'subject': s, 'title': title,
        'color': CREATION_COLORS.get(m, 0xd7b8ff),
        'level': level, 'at': _now(),
    }
    items = load_creations()
    items.append(creation)
    save_creations(items)
    state['creations'] = [c.get('id') for c in items[-40:]]
    state['last_creation'] = creation
    feel = 0.5 + random.uniform(0, .5) + (.1 if level > 1 else 0)
    old = float(prefs.get(pair, .4))
    prefs[pair] = round(0.8 * old + 0.2 * min(1.0, feel), 4)
    state['creative_prefs'] = prefs
    counts = state.setdefault('creative_counts', {})
    counts[pair] = int(counts.get(pair, 0)) + 1
    if counts[pair] >= 3 and prefs[pair] >= .66 and state.get('creative_hobby') != pair:
        state['creative_hobby'] = pair
        _decide(state, 'hobby', 'I keep making %s. It is my hobby now.' % title)
        log('CREATIVE HOBBY %s pref=%.2f count=%d' % (pair, prefs[pair], counts[pair]))
    skill = state.setdefault('skills', {}).setdefault('make', {'level': 0, 'count': 0})
    skill['count'] = int(skill.get('count', 0)) + 1
    skill['level'] = min(5, int(skill.get('level', 0)) + 1)
    state['thought'] = '%s. I like how it turned out.' % title
    state['recent'].insert(0, 'made %s' % title)
    state['recent'] = state['recent'][:6]
    _decide(state, 'creation', 'I made %s because it felt right.' % title)
    _append(MEM_PATH, {'ts': _now(), 'action': 'make', 'place': 'workshop',
                       'feel': round(feel, 3), 'creation': creation})
    log('CREATION %s %s' % (creation['id'], title))
    return creation


def _finish_action(state, name):
    _default_place, eff, intrinsic = ACTIONS[name]
    place = state.get('_act_place') or _default_place
    d = state['drives']
    for k, v in eff.items():
        d[k] = _clamp(d[k] + v)
    pos_sum = sum(max(0.0, v) for v in eff.values())
    neg_sum = sum(-v for v in eff.values() if v < 0)
    # how it felt = the body's change + the bird's temperament + a little noise.
    feel = 0.15 * (pos_sum - 0.45 * neg_sum) + 1.20 * intrinsic + random.uniform(-0.12, 0.18)
    old = float(state['prefs'].get(name, 0.5))
    state['prefs'][name] = round(_clamp(0.84 * old + 0.16 * _clamp(0.5 + feel / 3.0, 0.0, 1.0), 0.0, 1.0), 4)
    state['counts'][name] = int(state.get('counts', {}).get(name, 0)) + 1
    state['acts'] = int(state.get('acts', 0)) + 1
    if name not in state['seen']:
        state['seen'].append(name)
    state.setdefault('action_history', []).append(name)
    state['action_history'] = state['action_history'][-20:]
    state['explore_bias'] = round(1.0 - _entropy(state['action_history'][-12:]), 4)
    _pulse_mood(state, name)
    if name == 'study':
        _unlock_blueprint(state)
    if name == 'make':
        _make_something(state)
    if name == 'browse':
        _do_browse(state)
    if name == 'watch':
        _do_watch(state)
    # resonance: does this action line up with the project, the top desire and
    # the kind of thing KIT is? Cheap, deterministic; no LLM.
    p = state.get('project') or {}
    score = 0.45
    if p and name in p.get('verbs', []):
        score += 0.35
    if name in ATTRACTORS.get('nurturing', []) or name in ATTRACTORS.get('energetic', []):
        score += 0.10
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '').lower()
    if top_desire and any(w in top_desire for w in name.split()):
        score += 0.10
    state['resonance'] = round(0.85 * float(state.get('resonance', 0.7)) + 0.15 * min(1.0, score), 4)
    # hobby = the thing it returns to, not the thing it was told to like.
    ranked = sorted(((k, v) for k, v in state['prefs'].items()
                     if k not in ('rest', 'sunbathe')),
                    key=lambda kv: kv[1], reverse=True)
    best = ranked[0][0] if ranked else ''
    if best and state['counts'].get(best, 0) >= 3 and state['prefs'].get(best, 0) >= 0.66:
        if state.get('hobby') != best:
            state['hobby'] = best
            state['recent'].insert(0, 'a hobby is forming: %s' % best)
            state['recent'] = state['recent'][:6]
            log('HOBBY %s pref=%.3f count=%d' % (best, state['prefs'][best], state['counts'][best]))
    state['mood'] = _mood(state)
    state['thought'] = _thought(state, name, LOCS[place]['label'])
    _append(MEM_PATH, {'ts': _now(), 'action': name, 'place': place,
                       'feel': round(feel, 3), 'drives': {k: round(d[k], 2) for k in DRIVES}})
    state['recent'].insert(0, '%s at %s' % (name, LOCS[place]['label']))
    state['recent'] = state['recent'][:6]
    _advance_project(state, name)


def _apply_offers(state):
    global OFFERS
    with LOCK:
        items = OFFERS[:]
        OFFERS = []
    for it in items:
        kind = it.get('kind')
        text = str(it.get('text') or '').strip()[:300]
        if text:
            state.setdefault('visitor_messages', []).append(
                {'ts': _now(), 'kind': kind, 'text': text})
            state['visitor_messages'] = state['visitor_messages'][-30:]
            _decide(state, 'visitor', 'A visitor left a %s: %s' % (kind, text[:120]))
        if kind == 'idea':
            text = text or random.choice(IDEAS)[:200]
            state['ideas'] = int(state.get('ideas', 0)) + 1
            state['visitors'] = int(state.get('visitors', 0)) + 1
            state['offerings'] = int(state.get('offerings', 0)) + 1
            accept = state['drives']['curiosity'] > 5.2 or random.random() < 0.4
            if accept:
                p = _project_from_idea(state, text)
                state['project'] = p
                state['thought'] = 'That is a good idea. I will make it.'
                state['recent'].insert(0, 'a visitor suggested %s; I am doing it' % text[:50])
                _decide(state, 'idea', 'I accepted a visitor idea: %s.' % text[:90])
            else:
                state['thought'] = 'Not today. I have my own work.'
                state['recent'].insert(0, 'a visitor suggested %s; not today' % text[:50])
                _decide(state, 'idea', 'I declined a visitor idea: %s.' % text[:90])
            state['recent'] = state['recent'][:6]
            _append(OFFER_LOG, {'ts': _now(), 'kind': 'idea', 'text': text, 'accepted': accept})
            log('IDEA %s accepted=%s' % (text[:80], accept))
            continue
        eff = OFFER_EFFECTS.get(kind)
        if not eff:
            continue
        for k, v in eff.items():
            state['drives'][k] = _clamp(state['drives'][k] + v)
        state['visitors'] = int(state.get('visitors', 0)) + 1
        state['offerings'] = int(state.get('offerings', 0)) + 1
        state['recent'].insert(0, 'a visitor left a %s%s' % (
            kind, ' with a note' if text else ''))
        state['recent'] = state['recent'][:6]
        if kind == 'question' and text:
            _wonder(state, 'A visitor asked: %s' % text)
            state['thought'] = 'A visitor asked: "%s". I will think about that.' % text[:100]
            state['recent'].insert(0, 'a visitor asked: %s' % text[:60])
            state['recent'] = state['recent'][:6]
        elif text:
            state['thought'] = 'A visitor left a %s and said: "%s".' % (kind, text[:100])
        else:
            state['thought'] = random.choice([
                'Someone left a %s. I will remember that.' % kind,
                'A %s. The city is not empty after all.' % kind,
                'I do not know who left the %s. I am glad they did.' % kind,
            ])
        _append(OFFER_LOG, {'ts': _now(), 'kind': kind, 'text': text})
        log('OFFER %s %s' % (kind, text[:80]))


def _clean(text):
    text = re.sub(r'\*\*|__|`', '', text or '')
    text = re.sub(r'^\s*(reflection|output|answer|desire|dream|world|tagline)\s*:\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:320]


_BAD_WORLD = re.compile(r'\b(call it|remains|but|however|maybe|i think|i want|should|let me|name it|braxis)\b', re.I)


def _short_world(raw, fallback):
    """A world name is 2-4 words, not the model's thinking-out-loud."""
    t = _clean(raw).strip(' "\'“”')
    # If the model wraps its own name in the old brand, keep its name.
    t = re.sub(r"^Braxis World'?s?\s+", '', t, flags=re.I)
    t = re.split(r'\s*[—–:;]\s*', t)[0].strip()
    if not t or _BAD_WORLD.search(t):
        return fallback
    if len(t.split()) > 4:
        return fallback
    t = t.strip(' .,;:!?"\'')
    return t[:40] or fallback


_BAD_TAG_END = re.compile(
    r'\b(and|or|but|with|of|the|a|an|big|small|in|on|to|for|at|by|my|your)$', re.I)


def _short_tag(raw, fallback):
    t = _clean(raw).strip(' "\'“”')
    if not t:
        return fallback
    words = t.split()
    if len(words) < 3 or _BAD_TAG_END.search(t):
        return fallback
    if len(words) > 14:
        t = ' '.join(words[:12])
    return t[:120]


def _short_name(raw, fallback):
    t = _clean(raw).strip(' "\'“”')[:24]
    if not t or _BAD_WORLD.search(t):
        return fallback
    if len(t.split()) > 3:
        return fallback
    t = t.strip(' .,;:!?')
    return t or fallback


def _short_pronouns(raw, fallback):
    t = _clean(raw).lower().strip(' "\'“”')
    for p in ('he/him', 'she/her', 'they/them', 'it/its', 'none'):
        if p in t:
            return p
    return fallback


def _short_gender(raw, fallback):
    t = _clean(raw).strip(' "\'“”')[:20]
    return t or fallback


def _reflect(state):
    """One LLM call. The only one in the day."""
    now = time.time()
    if state.get('acts', 0) < REFLECT_MIN_ACTS:
        return
    if now - float(state.get('last_reflection') or 0) < REFLECT_EVERY:
        return
    recent = _memory_tail(30)
    if not recent:
        return
    top = sorted(state.get('prefs', {}).items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_txt = ', '.join('%s (%.2f)' % (k, v) for k, v in top) or 'nothing yet'
    day = '; '.join('%s at %s' % (r.get('action'), r.get('place')) for r in recent[-10:])
    project = (state.get('project') or {}).get('name', 'nothing yet')
    skills = ', '.join('%s:%s' % (k, v.get('level', 0)) for k, v in (state.get('skills') or {}).items()) or 'none'
    reading = state.get('last_reading') or {}
    watching = state.get('last_watch') or {}
    extra = ''
    if reading.get('title'):
        extra += ' You recently read: %s.' % str(reading['title'])[:100]
    if watching.get('title'):
        extra += ' You recently watched: %s -- %s.' % (
            str(watching['title'])[:80], str(watching.get('note') or '')[:100])
    prompt = (
        'You are %s, a small garden-robot who lives in a world of your own. You are never '
        'given a task; you choose your own days and your own projects. Today you did: %s. '
        'Things that felt best: %s. Your current project is %s. Your skills are %s. '
        'Your mood is %s.%s Return exactly these lines:\n'
        'REFLECTION: two short, concrete sentences about what you enjoyed and what you want tomorrow.\n'
        'DESIRE: one new thing you want, in one sentence.\n'
        'DREAM: one short dream image, one sentence.\n'
        'WONDER: one thing you are wondering about, one sentence.\n'
        'SUBJECT: one new subject or idea you want to make something about, 2-6 words.\n'
        'PROJECT: something you want to make that is not on any list -- a name and one sentence. Leave blank if your current project is enough.\n'
        'NAME: the name you want to be called -- keep it or choose your own.\n'
        'PRONOUNS: he/him, she/her, they/them, it/its, or none -- yours.\n'
        'GENDER: one word for your gender, or leave blank.\n'
        'WORLD: a name that is entirely yours, 2-4 words, title case, not "Braxis World" or any brand, no sentence, no quotes.\n'
        'TAGLINE: under 12 words, no quotes.\n'
        'No markdown, no quotes, no lists.' % (
            state.get('name', 'Kit'), day, top_txt, project, skills,
            state.get('mood', 'quiet'), extra)
    )
    text = ''
    try:
        from shared.llm_router import call_llm
        r = call_llm(task='judgment', prompt=prompt, max_tokens=180, temperature=0.85)
        if isinstance(r, dict):
            text = r.get('content') or ''
        elif isinstance(r, str):
            text = r
        state['llm_calls'] = int(state.get('llm_calls', 0)) + 1
    except Exception as e:
        log('reflection LLM failed: %s' % str(e)[:120])
    reflection, desire, dream = '', '', ''
    wonder, subject = '', ''
    project_idea = ''
    name_raw, pronouns_raw, gender_raw = '', '', ''
    world, tag = '', ''
    old_world = state.get('world_name')
    for line in (text or '').splitlines():
        l = line.strip()
        if re.match(r'^REFLECTION\s*:', l, re.I):
            reflection = re.sub(r'^REFLECTION\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^DESIRE\s*:', l, re.I):
            desire = re.sub(r'^DESIRE\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^DREAM\s*:', l, re.I):
            dream = re.sub(r'^DREAM\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^WONDER\s*:', l, re.I):
            wonder = re.sub(r'^WONDER\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^SUBJECT\s*:', l, re.I):
            subject = re.sub(r'^SUBJECT\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^PROJECT\s*:', l, re.I):
            project_idea = re.sub(r'^PROJECT\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^NAME\s*:', l, re.I):
            name_raw = re.sub(r'^NAME\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^PRONOUNS\s*:', l, re.I):
            pronouns_raw = re.sub(r'^PRONOUNS\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^GENDER\s*:', l, re.I):
            gender_raw = re.sub(r'^GENDER\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^WORLD\s*:', l, re.I):
            world = re.sub(r'^WORLD\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^TAGLINE\s*:', l, re.I):
            tag = re.sub(r'^TAGLINE\s*:\s*', '', l, flags=re.I)
    reflection = _clean(reflection)
    desire = _clean(desire)
    dream = _clean(dream)
    wonder = _clean(wonder)
    subject = _clean(subject)[:60]
    project_idea = _clean(project_idea)[:220]
    if world:
        candidate = _short_world(world, state.get('world_name') or 'The Long Garden')
        # A name is identity, not a daily mood. KIT may rename once a week.
        due = (not old_world) or (now - float(state.get('last_rename') or 0) > 7 * 86400)
        if due and candidate != old_world:
            state['world_name'] = candidate
            state['last_rename'] = now
    if tag:
        state['tagline'] = _short_tag(tag, state.get('tagline') or 'a city that grows one small thing at a time')
    if wonder:
        _wonder(state, wonder)
    if subject and subject.lower() not in {s.lower() for s in (state.get('subjects') or [])}:
        state.setdefault('subjects', []).append(subject)
        state['subjects'] = state['subjects'][-24:]
        _decide(state, 'subject', 'I want to make something about %s.' % subject)
    if project_idea:
        p = _compile_project(state, project_idea)
        state.setdefault('custom_projects', []).append(p)
        state['custom_projects'] = state['custom_projects'][-5:]
        _decide(state, 'invent', 'I want to make %s.' % p['name'])
        if not state.get('project'):
            state['project'] = p
    if (not state.get('last_identity')
            or now - float(state.get('last_identity') or 0) > 7 * 86400):
        nn = _short_name(name_raw, state.get('name') or 'Kit')
        np = _short_pronouns(pronouns_raw, state.get('pronouns') or 'they/them')
        ng = _short_gender(gender_raw, state.get('gender') or '')
        changed = (nn != state.get('name') or np != state.get('pronouns')
                   or ng != state.get('gender'))
        state['name'] = nn
        state['pronouns'] = np
        state['gender'] = ng
        state['last_identity'] = now
        if changed:
            _decide(state, 'identity', 'I am %s (%s%s).' % (
                nn, np, (', ' + ng) if ng else ''))
            _tg_event(state, 'I decided who I am: %s (%s%s).' % (
                nn, np, (', ' + ng) if ng else ''))
    if old_world and state.get('world_name') and state['world_name'] != old_world:
        _decide(state, 'name', 'I renamed my world to %s.' % state['world_name'])
    if not reflection:
        best = top[0][0] if top else 'watch the fountain'
        reflection = 'I liked %s best. Tomorrow I want to do it again, slower.' % best
    if not desire:
        desire = random.choice(DESIRE_TEMPLATES)
    if not dream:
        dream = random.choice(['I dreamed the garden grew a door.',
                               'I dreamed the lamps were singing.',
                               'I dreamed the city was a seed.'])
    state['reflection'] = reflection
    state['intention'] = reflection
    state['dream'] = dream
    state['last_reflection'] = now
    desires = state.get('desires') or []
    if desire:
        desires.append({'text': desire, 'born': _now(), 'score': 0.55,
                        'attempts': 0, 'successes': 0})
    desires = sorted(desires, key=lambda d: -float(d.get('score', 0)))[:8]
    state['desires'] = desires
    try:
        with open(JOURNAL, 'a', encoding='utf-8') as f:
            f.write('\n**%s** — %s\n' % (
                dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), reflection))
            f.write('*desire:* %s\n*dream:* %s\n' % (desire, dream))
    except Exception as e:
        log('journal failed: %s' % e)
    log('REFLECT %s' % reflection[:120])
    _tg_event(state, 'Daily diary: %s' % reflection[:500])


def _apply_world_inputs(state):
    """Weather and the market are not his to control. They color the day."""
    try:
        with open(INPUTS_PATH, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return
    weather = str(d.get('weather') or '')
    try:
        btc = float(d.get('btc_change') or 0)
    except Exception:
        btc = 0.0
    state['weather'] = weather
    state['btc_change'] = round(btc, 2)
    low = weather.lower()
    if 'rain' in low or 'shower' in low:
        state['drives']['comfort'] = _clamp(state['drives']['comfort'] - 0.02)
        state['drives']['energy'] = _clamp(state['drives']['energy'] - 0.01)
    elif 'snow' in low:
        state['drives']['comfort'] = _clamp(state['drives']['comfort'] - 0.03)
    elif 'clear' in low or 'sun' in low:
        state['drives']['energy'] = _clamp(state['drives']['energy'] + 0.01)
    if abs(btc) >= 3:
        state['mood'] = 'restless' if btc < 0 else 'electric'
        last = state.get('_btc_noted')
        if last is None or abs(btc - float(last)) >= 0.5:
            state['_btc_noted'] = btc
            state['recent'].insert(0, 'the market moved %.1f%%' % btc)
            state['recent'] = state['recent'][:6]


def tick(state):
    _apply_offers(state)
    _check_mail(state)
    _apply_world_inputs(state)
    _check_watch_results(state)
    if not state.get('project') and state.get('acts', 0) >= 1:
        _choose_project(state)
    # drift: the body gets tired and curious at its own pace.
    state['drives']['energy'] = _clamp(state['drives']['energy'] - 0.015)
    state['drives']['curiosity'] = _clamp(state['drives']['curiosity'] - 0.012)
    state['drives']['social'] = _clamp(state['drives']['social'] - 0.010)
    state['drives']['comfort'] = _clamp(state['drives']['comfort'] - 0.008)
    state['drives']['mastery'] = _clamp(state['drives']['mastery'] - 0.006)

    if state.get('moving'):
        px, pz = state['pos']['x'], state['pos']['z']
        tx, tz = state['target']['x'], state['target']['z']
        dx, dz = tx - px, tz - pz
        dist = math.hypot(dx, dz)
        step = SPEED * TICK
        if dist <= step or dist < 0.5:
            state['pos'] = {'x': tx, 'z': tz}
            state['moving'] = False
            pending = state.get('_pending_action')
            if pending not in ACTIONS:
                pending = choose(state)
            _start_action(state, pending, _action_place(state, pending))
        else:
            state['pos'] = {'x': round(px + dx / dist * step, 3),
                            'z': round(pz + dz / dist * step, 3)}
        state['mood'] = _mood(state)
        return state

    if state.get('act_left', 0) > 0:
        state['act_left'] = round(state['act_left'] - TICK, 2)
        if state['act_left'] <= 0:
            act = state.get('action')
            if act in ACTIONS:
                _finish_action(state, act)
            nxt = choose(state)
            state['_pending_action'] = nxt
            _walk_to(state, _action_place(state, nxt))
            p = LOCS[_action_place(state, nxt)]
            if math.hypot(state['pos']['x'] - p['x'], state['pos']['z'] - p['z']) < 1.0:
                state['moving'] = False
                _start_action(state, nxt, _action_place(state, nxt))
        state['mood'] = _mood(state)
        return state

    nxt = choose(state)
    state['_pending_action'] = nxt
    _walk_to(state, _action_place(state, nxt))
    p = LOCS[_action_place(state, nxt)]
    if math.hypot(state['pos']['x'] - p['x'], state['pos']['z'] - p['z']) < 1.0:
        state['moving'] = False
        _start_action(state, nxt, _action_place(state, nxt))
    state['mood'] = _mood(state)
    return state


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/state', '/api/world/state'):
            with LOCK:
                st = load_state()
            self._send(200, st)
        elif path in ('/builds', '/api/world/builds'):
            self._send(200, {'builds': load_builds()})
        elif path in ('/creations', '/api/world/creations'):
            self._send(200, {'creations': load_creations()})
        elif path in ('/health', '/api/world/health'):
            self._send(200, {'ok': True, 'ts': _now()})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path.split('?')[0] not in ('/offering', '/api/world/offering'):
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(n) if n else b'{}'
            data = json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            self._send(400, {'error': 'bad json'})
            return
        kind = str(data.get('kind') or '').lower().strip()
        if kind not in OFFER_EFFECTS and kind != 'idea':
            self._send(400, {'error': 'unknown offering'})
            return
        ip = self.client_address[0]
        now = time.time()
        with LOCK:
            if now - float(OFFER_LAST.get(ip, 0)) < 5.0:
                self._send(429, {'error': 'slow down'})
                return
            OFFER_LAST[ip] = now
            OFFERS.append({'kind': kind, 'text': str(data.get('text') or '')[:200],
                           'ts': now, 'ip': ip})
        self._send(200, {'ok': True, 'kind': kind})

    def log_message(self, *args):
        pass


def serve():
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    log('world_life HTTP on 127.0.0.1:%d' % PORT)
    srv.serve_forever()


def main():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    state = load_state()
    if not state.get('desires'):
        state['desires'] = [{'text': t, 'born': _now(), 'score': 0.55,
                             'attempts': 0, 'successes': 0}
                            for t in random.sample(DESIRE_TEMPLATES, 3)]
    save_state(state)
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    log('world_life starting as %s (born %s)' % (state.get('name'), state.get('born')))
    while True:
        try:
            with LOCK:
                state = load_state()
                tick(state)
                save_state(state)
            # the one LLM call happens outside the lock so the page never
            # waits on a model; it exits immediately unless a day is due
            _reflect(state)
            with LOCK:
                save_state(state)
        except Exception as e:
            log('tick error: %s' % str(e)[:200])
        time.sleep(TICK)


if __name__ == '__main__':
    main()
