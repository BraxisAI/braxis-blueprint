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
import hashlib
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
REQUESTS = os.path.join(B, 'data', 'world', 'kit_asset_requests.jsonl')
POSTS_LOG = os.path.join(B, 'data', 'world', 'kit_social_posts.jsonl')
WORLD = 'https://braxisai.com/world/'
SIGNALS = os.path.join(B, 'data', 'world', 'world_signals.jsonl')
SELF_MODEL_PATH = os.path.join(B, 'data', 'world', 'kit_self_model.json')
WISHLIST_PATH = os.path.join(B, 'data', 'world', 'kit_wishlist.json')
EXTERNAL_LOG = os.path.join(B, 'data', 'world', 'kit_external_events.jsonl')
SKILL_LIB = os.path.join(B, 'data', 'world', 'kit_skill_library.json')
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
    'river_dock':   {'x': -95, 'z': -55, 'label': 'the river dock'},
    'old_ruins':    {'x': 100, 'z': 60,  'label': 'the old ruins'},
    'hilltop':      {'x': -100,'z': 45,  'label': 'the hilltop'},
    'south_farm':   {'x': 25,  'z': 105, 'label': 'the south farm'},
    'north_woods':  {'x': 55,  'z': -95, 'label': 'the north woods'},
    'east_gate':    {'x': 120, 'z': -10, 'label': 'the east gate'},
    'west_marsh':   {'x': -120,'z': -15, 'label': 'the west marsh'},
    'far_shore':    {'x': -175,'z': 120, 'label': 'the far shore'},
    'south_ridge':  {'x': 155, 'z': 165, 'label': 'the southern ridge'},
    'old_road':     {'x': -165,'z': -130,'label': 'the old road'},
    'east_ruins':   {'x': 180, 'z': 45,  'label': 'the eastern ruins'},
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
    'envision':       ('lookout',      {'curiosity': 1.4, 'mastery': .5, 'energy': -.2}, .92),
    'play':           ('plaza',        {'comfort': 1.3, 'social': .6, 'energy': -.2}, .96),
    'post':           ('library',      {'social': 1.1, 'mastery': .4, 'curiosity': .2, 'energy': -.1}, .78),
    'sketch':         ('library',      {'curiosity': .8, 'mastery': .6, 'energy': -.2}, .82),
    'carve':          ('workshop',     {'mastery': 1.1, 'comfort': .3, 'energy': -.3}, .78),
    'sculpt':         ('workshop',     {'mastery': 1.2, 'curiosity': .4, 'energy': -.5}, .86),
    'paint':          ('workshop',     {'curiosity': 1.0, 'comfort': .4, 'energy': -.3}, .90),
    'compose':        ('library',      {'curiosity': 1.0, 'mastery': .7, 'energy': -.2}, .88),
    'rehearse':       ('observatory',  {'social': .8, 'comfort': .6, 'energy': -.3}, .84),
    'photograph':     ('lookout',      {'curiosity': 1.1, 'comfort': .4, 'energy': -.2}, .86),
    'wonder':         ('lookout',      {'curiosity': 1.2, 'comfort': .3}, .90),
    'experiment':     ('workshop',     {'mastery': .8, 'curiosity': 1.0, 'energy': -.4}, .92),
    'code':           ('library',      {'mastery': 1.2, 'curiosity': .8, 'energy': -.5}, .90),
    'fish':           ('river_dock',   {'comfort': .8, 'curiosity': .6, 'energy': -.2}, .80),
    'watch river':    ('river_dock',   {'comfort': 1.1, 'curiosity': .4}, .82),
    'climb hill':     ('hilltop',      {'curiosity': 1.2, 'mastery': .3, 'energy': -.6}, .86),
    'survey ruins':   ('old_ruins',    {'curiosity': 1.5, 'mastery': .4, 'energy': -.4}, .90),
    'forage':         ('north_woods',  {'comfort': .7, 'curiosity': .8, 'energy': -.3}, .83),
    'tend farm':      ('south_farm',   {'comfort': 1.0, 'mastery': .5, 'energy': -.4}, .78),
    'map the edge':   ('east_gate',    {'curiosity': 1.4, 'mastery': .5, 'energy': -.5}, .90),
    'listen to marsh':('west_marsh',   {'curiosity': .9, 'comfort': .6}, .80),
    'beachcomb':      ('far_shore',    {'curiosity': 1.2, 'comfort': .6, 'energy': -.2}, .86),
    'survey ridge':   ('south_ridge',  {'curiosity': 1.4, 'mastery': .5, 'energy': -.5}, .90),
    'walk old road':  ('old_road',     {'curiosity': 1.0, 'comfort': .5, 'energy': -.4}, .82),
    'probe ruins':    ('east_ruins',   {'curiosity': 1.5, 'mastery': .4, 'energy': -.3}, .90),
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
    'energetic':     ['build', 'tinker', 'make', 'play', 'experiment', 'trade',
                      'haggle', 'explore', 'sketch', 'carve', 'sculpt', 'paint'],
    'contemplative': ['read', 'write notes', 'study', 'chart sky', 'watch fountain',
                      'stargaze', 'balance books', 'read ledger', 'watch river',
                      'listen to marsh', 'wonder', 'code', 'compose', 'photograph'],
    'social':        ['greet visitors', 'play', 'post', 'trade', 'browse stalls',
                      'rehearse'],
    'guarding':      ['repair', 'polish counter', 'count coins', 'watch horizon'],
    'exploring':     ['explore', 'stargaze', 'browse', 'watch', 'envision',
                      'wonder', 'experiment', 'browse stalls', 'watch horizon',
                      'beachcomb', 'survey ridge', 'walk old road', 'probe ruins',
                      'photograph'],
    'nurturing':     ['garden', 'plant', 'water plants', 'smell flowers', 'repair'],
}

SITES = [
    ('plaza north', 0, -18, {'bench', 'lantern', 'monument', 'custom'}),
    ('plaza east', 18, 0, {'bench', 'lantern', 'monument', 'custom'}),
    ('plaza south', 0, 18, {'bench', 'lantern', 'monument', 'custom'}),
    ('plaza west', -18, 0, {'bench', 'lantern', 'monument', 'custom'}),
    ('market corner', 6, -20, {'bench', 'lantern', 'custom'}),
    ('garden path', 12, -30, {'garden_plot', 'trellis', 'arch', 'mural', 'custom'}),
    ('garden edge', 4, -40, {'garden_plot', 'trellis', 'arch', 'mural', 'custom'}),
    ('orchard', 20, -36, {'garden_plot', 'trellis', 'custom'}),
    ('workshop yard', -16, 6, {'tower', 'bridge', 'custom', 'bench'}),
    ('library steps', -10, 14, {'mural', 'bench', 'lantern', 'custom'}),
    ('observatory lawn', 0, 24, {'bench', 'lantern', 'monument', 'custom'}),
    ('lookout path', 48, 34, {'tower', 'monument', 'custom'}),
    ('east road', 26, 10, {'lantern', 'bench', 'custom'}),
    ('west road', -26, -10, {'lantern', 'bench', 'custom'}),
    ('north walk', 10, 26, {'bench', 'lantern', 'custom'}),
    ('south walk', -10, -26, {'bench', 'lantern', 'custom'}),
    ('riverbank', -90, -55, {'bench', 'lantern', 'custom', 'bridge', 'garden_plot'}),
    ('ruins edge', 95, 55, {'monument', 'arch', 'tower', 'custom'}),
    ('hilltop', -95, 42, {'monument', 'tower', 'bench', 'custom'}),
    ('south farm', 25, 100, {'garden_plot', 'trellis', 'bench', 'custom'}),
    ('north woods', 55, -90, {'bench', 'lantern', 'custom'}),
    ('east gate', 115, -10, {'arch', 'lantern', 'monument', 'custom'}),
    ('west marsh', -115, -15, {'bench', 'lantern', 'custom'}),
    ('far shore', -170, 118, {'bench', 'lantern', 'custom', 'garden_plot'}),
    ('south ridge', 150, 160, {'monument', 'tower', 'bench', 'custom'}),
    ('old road', -160, -125, {'lantern', 'bench', 'arch', 'custom'}),
    ('east ruins', 175, 42, {'monument', 'arch', 'tower', 'custom'}),
    ('north shore', 0, -180, {'bench', 'lantern', 'monument', 'custom'}),
    ('west ridge', -180, 0, {'tower', 'monument', 'custom'}),
    ('south shore', 0, 180, {'garden_plot', 'bench', 'custom'}),
    ('east ridge', 180, 0, {'tower', 'arch', 'custom'}),
]

FAR_SITES = {'far shore', 'south ridge', 'old road', 'east ruins',
             'north shore', 'west ridge', 'south shore', 'east ridge'}

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
                     'the lantern', 'the fountain', 'the sky', 'a dream', 'the trio',
                     'trains', 'planes', 'architecture', 'space', 'history', 'music'],
        'mediums': ['paint', 'carve', 'plant', 'write', 'photograph', 'sing'],
        'decisions': [],
        'wonders': [],
        'custom_projects': [],
        'project_queue': [],
        'recent_project_kinds': [],
        'blank_slate': False,
        'thought_history': [],
        'envision_today': 0,
        'envision_day': '',
        'envision_last': 0.0,
        'envision_builds': 0,
        'last_envision_build': None,
        'envision_check': 0.0,
        'next_project_after': 0.0,
        'signals_total': 0,
        'signal_check': 0.0,
        'last_signal_ts': '',
        'last_message_ts': '',
        'last_share_id': 0,
        'last_signal': None,
        'last_make_ts': 0.0,
        'last_post_ts': 0.0,
        'posts': 0,
        'last_post': None,
        'action_last': {},
        'mood_residue': {},
        'self_model': '',
        'visitor_impressions': {},
        'pending_ideas': [],
        'wishlist': {},
        'wishlist_check': 0.0,
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


def _add_residue(state, mood, amount=0.35):
    res = state.setdefault('mood_residue', {})
    res[mood] = round(min(1.5, float(res.get(mood, 0)) + amount), 3)


def _mood(state):
    d = state['drives']
    if d['energy'] < 2.2:
        return 'sleepy'
    if d['social'] < 2.6:
        return 'lonely'
    weights = dict(state.get('mood_weights') or {})
    for k, v in (state.get('mood_residue') or {}).items():
        weights[k] = float(weights.get(k, 0)) + float(v) * 0.35
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


def _remember_thought(state, text):
    text = str(text or '').strip()
    if not text:
        return text
    hist = state.setdefault('thought_history', [])
    if not hist or hist[-1] != text:
        hist.append(text)
    state['thought_history'] = hist[-8:]
    return text


def _pick_line(state, lines):
    recent = set((state.get('thought_history') or [])[-5:])
    fresh = [l for l in lines if l not in recent] or lines
    return random.choice(fresh)


def _visitor_phrase(text):
    low = str(text or '').lower()
    if '?' in low:
        return "the visitor's question"
    if 'watching' in low:
        return 'the visitor who is watching'
    if 'hi ' in low or 'hello' in low:
        return 'the visitor who said hello'
    return 'the visitor who stopped by'


def _context_thought(state, action, place):
    """A thought assembled from KIT's actual day, not a fixed mood line."""
    p = state.get('project') or {}
    lb = state.get('last_build') or {}
    lc = state.get('last_creation') or {}
    proj = re.sub(r'^(the|a|an)\s+', '', str(p.get('name') or 'this thing'),
                  flags=re.I)
    build_name = re.sub(r'^(the|a|an)\s+', '', str(lb.get('name') or ''),
                        flags=re.I)
    visitor = (state.get('visitor_messages') or [{}])[-1]
    desire = ''
    if state.get('desires'):
        desire = str(max(state['desires'],
                         key=lambda d: float(d.get('score', 0))).get('text') or '')
    desire = re.sub(r'^I want to\s+', '', desire, flags=re.I).strip(' .')
    wonder = ''
    if state.get('wonders'):
        wonder = str((state['wonders'][-1] or {}).get('text') or '')[:90]
    subject = ''
    if lc.get('subject'):
        subject = str(lc['subject'])
    elif state.get('subjects'):
        subject = random.choice(state['subjects'])
    subject = re.sub(r'^(the|a|an)\s+', '', str(subject or 'garden'),
                     flags=re.I)[:40]
    world = state.get('world_name') or 'Glowveil Hollow'
    mood = state.get('mood') or 'quiet'
    weather = str(state.get('weather') or '')
    lines = []
    if p:
        prog = int(p.get('progress') or 0)
        target = int(p.get('target') or 3)
        name = proj[0].upper() + proj[1:] if proj else 'This thing'
        lines += [
            '%s is %d of %d. I can see where it wants to go.' % (name, prog, target),
            'I keep returning to %s. The next pass will tell me if it is right.' % name,
            'The %s is not finished, but it is no longer only an idea.' % name,
            'If I stop now, %s will still be here tomorrow. I do not want to stop now.' % name,
        ]
    if lb.get('name'):
        site = lb.get('site') or 'the edge'
        lines += [
            'The %s is still standing at %s. I could add %s beside it.' % (
                build_name, site, subject),
            'I walked past the %s today. It looked older than yesterday.' % build_name,
            'The %s does not need me every hour. That is a good sign.' % build_name,
        ]
    if lc.get('title'):
        ctitle = str(lc['title'])
        ctitle = ctitle[:1].upper() + ctitle[1:]
        lines += [
            'I made %s. The next one could be %s.' % (ctitle, subject),
            '%s is mine in a way the town is not. I made the choice.' % ctitle,
            'I keep thinking about %s. It is a small thing, but it is a thing.' % subject,
        ]
    if visitor.get('text') and random.random() < 0.45:
        who = _visitor_phrase(visitor.get('text'))
        lines += [
            '%s is still in my head.' % who.capitalize(),
            'I want to make something for %s.' % who,
            'I have not answered %s yet.' % who,
        ]
    if desire:
        lines += [
            'I still want to %s. Today I can take one small step.' % desire,
            'The question under everything else is: %s.' % desire,
            'The day keeps bending back toward %s.' % desire,
        ]
    if wonder:
        w = wonder.rstrip(' .')
        if not w.endswith(('?', '!')):
            w += '.'
        lines += [
            'I keep wondering: %s' % w,
            'The question gets bigger when I look at it: %s' % w,
        ]
    if weather:
        lines += [
            'The %s weather is doing something to the light.' % weather,
            'The %s weather makes %s feel like a different place.' % (weather, place),
        ]
    residue = state.get('mood_residue') or {}
    if residue:
        rtop = max(residue, key=residue.get)
        if float(residue.get(rtop) or 0) > 0.25:
            lines.append('The %s from earlier is still with me.' % rtop)
    builds = int(state.get('builds') or 0)
    if builds > 20:
        lines.append('The town is getting crowded. I want the next thing to be different.')
    elif builds < 8:
        lines.append('There is room here. I can feel it.')
    lines += [
        'I spend a while at %s. The town is still here.' % place,
        'I am %s today. This place feels right for %s.' % (mood, action),
        'From %s, %s looks like a sentence I am still learning to read.' % (
            place, world),
        'I do not need the whole answer. I need the next small thing.',
        'The town is not a backdrop. It is the thing I am making with my hands.',
        'I made a choice this morning. I am still learning what it costs.',
        'I am not the same resident who woke up here. The difference is small and real.',
        'There is more to %s than I have seen. I keep finding new edges.' % world,
    ]
    return _pick_line(state, lines)


def _thought_raw(state, action=None, place=None):
    act = action or state.get('action') or 'stand still'
    place = place or (LOCS.get(ACTIONS.get(act, ('plaza',))[0], {}).get('label') or 'the city')
    mood = state.get('mood', 'quiet')
    hobby = state.get('hobby')
    project = state.get('project') or {}
    if state['drives']['energy'] < 2.2 and act not in ('rest', 'sunbathe'):
        return _pick_line(state, [
            'My joints are heavy. I should find somewhere warm to rest.',
            'I have been carrying the day in my hands. I need to put it down.',
            'The body is asking for a slower hour.',
        ])
    if project and project.get('progress'):
        nm = str(project.get('name') or 'thing')
        if nm.lower().startswith(('a ', 'an ', 'the ')):
            nm = nm.split(' ', 1)[1]
        return _pick_line(state, [
            'The %s is taking shape. One more pass.' % nm,
            'I can see the %s now. It needs one more choice.' % nm,
            'The %s is not finished, but it knows what it wants.' % nm,
            'I am learning the %s by making it.' % nm,
        ])
    if hobby and act == hobby and state.get('counts', {}).get(hobby, 0) >= 3:
        return _pick_line(state, [
            'I keep coming back to %s. It is mine now.' % hobby,
            'This is what I do when no one is asking: %s.' % hobby,
            'The habit is older than today. I trust it.',
        ])
    voices = {
        'energetic':     ['The whole street feels like it is waiting for me.',
                          'I want to build the whole row before the light goes.',
                          'My hands know what to do before I do.',
                          'The light is short. I am not.'],
        'contemplative': ['There is more here than I have seen yet.',
                          'The light on %s makes me want to look closer.' % place,
                          'I keep finding new edges on the same thought.',
                          'The town is a sentence I am still learning to read.'],
        'social':        ['I wonder who else is awake in the city.',
                          'A voice would be nice. Just one.',
                          'I hope someone leaves a question in the dust.',
                          'The plaza is louder when I imagine company.'],
        'guarding':      ['Something small always needs fixing.',
                          'I will check the lamps before I sleep.',
                          'I count the small things so no one else has to.',
                          'A loose hinge is a promise I can keep.'],
        'exploring':     ['There is a corner of this city I have not stood in.',
                          'The horizon is a promise.',
                          'Somewhere past the last lamp, the map goes soft.',
                          'I want to stand where the path runs out.'],
        'nurturing':     ['The soil is warm. The seeds know what to do.',
                          'I like making a place for something else to live.',
                          'Growth is mostly patience wearing work clothes.',
                          'I plant the next thing before I finish admiring the last.'],
        'sleepy':        ['The city is quiet. So am I.',
                          'The lamps are low. My thoughts are lower.',
                          'I will let the dark do the rest.'],
        'lonely':        ['I wonder who else is awake in the city.',
                          'A voice would be nice. Just one.',
                          'The quiet is not empty. It is just unshared.',
                          'I leave the light on for someone who might come.'],
        'quiet':         ['I am here. That is most of it.',
                          'The day has no shape yet. I can give it one.',
                          'Nothing needs me right now. I will let that be true.',
                          'The afternoon is a slow animal. I move with it.'],
    }
    return _context_thought(state, act, place)


def _thought(state, action=None, place=None):
    return _remember_thought(state, _thought_raw(state, action, place))


def choose(state):
    d = state['drives']
    prefs = state['prefs']
    seen = set(state.get('seen') or [])
    project = state.get('project') or {}
    explore = float(state.get('explore_bias') or 0)
    recent_actions = state.get('action_history') or []
    last_action = recent_actions[-1] if recent_actions else ''
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
                project_bonus += 1.1
            if place == project.get('place'):
                project_bonus += 0.25
        _count = state.get('counts', {}).get(name, 0)
        curious_bonus = explore * max(0.0, 1.0 - _count / 8.0) * 0.9
        creative_bonus = 0.0
        if name == 'make':
            creative_bonus = 0.35 + (0.35 if d.get('curiosity', 5) > 6 else 0.0)
        cooldown = 0.0
        if name in CREATION_ACTIONS and time.time() - float(state.get('last_make_ts') or 0) < 10 * 60:
            cooldown = -2.0
        if name == 'post' and time.time() - float(state.get('last_post_ts') or 0) < 20 * 3600:
            cooldown = -3.0
        if name == 'browse' and time.time() - float(state.get('last_browse') or 0) < 3600:
            cooldown = -2.0
        if name == 'watch' and time.time() - float(state.get('last_watch_ts') or 0) < 6 * 3600:
            cooldown = -3.0
        # Break the rut: repeated actions get old fast. An action not seen
        # in the last ten gets a real bonus; the old -0.45 was too gentle.
        recent_hits = sum(1 for a in recent_actions[-8:] if a == name)
        repeat_penalty = -0.65 * recent_hits
        if name == last_action:
            repeat_penalty -= 1.0
        variety = 0.45 if name not in recent_actions[-10:] else 0.0
        last_ts = float((state.get('action_last') or {}).get(name) or 0)
        age_bonus = 0.60 if (not last_ts or time.time() - last_ts > 24 * 3600) else 0.0
        hour = dt.datetime.now(dt.timezone.utc).hour
        if 6 <= hour < 12:
            day_bonus = 0.15 if name in ('sunbathe', 'garden', 'forage',
                                         'explore', 'water plants') else 0.0
        elif 12 <= hour < 18:
            day_bonus = 0.15 if name in ('build', 'tinker', 'make', 'paint',
                                         'sculpt', 'code', 'sketch') else 0.0
        else:
            day_bonus = 0.15 if name in ('stargaze', 'read', 'rest',
                                         'watch fountain', 'compose', 'wonder') else 0.0
        s = (need + pref * 1.2 + novelty + project_bonus + curious_bonus
             + creative_bonus + cooldown + repeat_penalty + variety + age_bonus
             + day_bonus + random.random() * 0.55)
        if s > best_s:
            best, best_s = name, s
    # A small deliberate randomness keeps a day from collapsing into one
    # action. It is lower while a project is active.
    if random.random() < (0.06 if project else 0.15):
        pool = [n for n in ACTIONS if n not in recent_actions[-3:]]
        if pool:
            return random.choice(pool)
    return best or 'watch fountain'


def _walk_to(state, place):
    p = LOCS[place]
    state['target'] = {'x': float(p['x']), 'z': float(p['z'])}
    state['moving'] = True
    state['action'] = 'walking to %s' % p['label']
    lines = [
        'The road to %s is warm.' % p['label'],
        'My footsteps sound different on the north road.',
        'Something might be different there today.',
        'The stones remember my last walk.',
        'I take the long way when the light is this good.',
        'Every step makes the town a little more mine.',
        'I can hear the garden before I see it.',
    ]
    recent = set((state.get('thought_history') or [])[-3:])
    fresh = [l for l in lines if l not in recent] or lines
    state['thought'] = _remember_thought(state, random.choice(fresh))


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

    def make(p):
        return dict(p, target=2 + random.randint(0, 1), progress=0,
                    why='a visitor asked for %s' % text[:60], started=_now())

    # An explicit shape/name wins over a shared verb. "build a tower" used to
    # match the first template with the verb "build" (a trellis); now it is a tower.
    for p in PROJECT_TEMPLATES:
        if (p['kind'].replace('_', ' ') in t
                or p['name'].replace('a ', '').lower() in t):
            return make(p)
    for p in PROJECT_TEMPLATES:
        if any(w in t for w in p['verbs']):
            return make(p)
    return make(random.choice(PROJECT_TEMPLATES))


def _compile_project(state, text):
    """A project KIT wrote in its own words, compiled into a build schema."""
    raw = _clean(text)[:220]
    if not _public_safe(raw):
        raw = 'a small monument for the town'
        log('public-safety: project subject replaced')
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
    elif any(has(w) for w in ('tree', 'pine', 'forest', 'grove')):
        shape = 'tree'
    elif any(has(w) for w in ('garden', 'flower', 'plant', 'grow')):
        shape = 'garden'
    elif any(has(w) for w in ('lantern', 'lamp')):
        shape = 'lantern'
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
        'verbs': _verbs_for_shape(shape),
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


def _shape_for(text, fallback=None):
    """Deterministic shape from words, shared by continuity and envision."""
    low = (text or '').lower()

    def has(w):
        return re.search(r'\b' + re.escape(w) + r'\b', low) is not None

    if any(has(w) for w in ('district', 'monument', 'memorial')):
        return 'spire'
    if any(has(w) for w in ('arch', 'door', 'gate', 'shrine')):
        return 'arch'
    if any(has(w) for w in ('ring', 'circle', 'halo', 'moon')):
        return 'ring'
    if any(has(w) for w in ('tree', 'pine', 'forest', 'grove')):
        return 'tree'
    if any(has(w) for w in ('garden', 'flower', 'plant', 'grow')):
        return 'garden'
    if any(has(w) for w in ('lantern', 'lamp')):
        return 'lantern'
    if any(has(w) for w in ('bridge', 'cross', 'connect')):
        return 'bridge'
    if any(has(w) for w in ('tower', 'watchtower', 'high', 'sky', 'see far', 'lookout')):
        return 'tower'
    if any(has(w) for w in ('bench', 'sit', 'rest')):
        return 'bench'
    if any(has(w) for w in ('fountain', 'water', 'rain')):
        return 'fountain'
    return fallback or random.choice(['spire', 'ring', 'arch', 'garden'])


def _verbs_for_shape(shape):
    """Projects advance through a varied set of verbs, not tinker forever."""
    if shape in ('tree', 'garden'):
        return ['garden', 'plant', 'water plants', 'sketch', 'make']
    if shape in ('bridge', 'tower', 'arch'):
        return ['build', 'tinker', 'sketch', 'carve']
    if shape in ('ring', 'spire'):
        return ['build', 'tinker', 'sculpt', 'paint']
    if shape in ('lantern', 'bench', 'fountain'):
        return ['build', 'tinker', 'carve', 'paint']
    return ['build', 'tinker', 'make', 'sketch']


def _compose_next_project(state, slot=0):
    """A deterministic next project, no LLM. Closes the blank-slate gap."""
    desires = sorted(state.get('desires') or [],
                     key=lambda d: -float(d.get('score', 0)))
    desire = (desires[0].get('text') if desires else '') or ''
    last = state.get('last_creation') or {}
    last_build = state.get('last_build') or {}
    wonder = ''
    wonders = state.get('wonders') or []
    if wonders:
        wonder = str(wonders[-1].get('text') or '')
    subjects = [str(s) for s in (state.get('subjects') or [])
                if _public_safe(str(s))]
    subject = ''
    if slot == 0 and last.get('subject') and _public_safe(str(last['subject'])):
        subject = str(last['subject'])
    elif slot == 0 and wonder:
        subject = re.sub(
            r'^(I wonder|I am wondering|I want to see|I want to know)\s+',
            '', wonder, flags=re.I).strip(' .!?')[:40]
    if not subject and subjects:
        subject = subjects[(int(state.get('builds', 0)) + slot) % len(subjects)]
    subject = _clean(subject)[:40] or 'the garden'
    seed = ' '.join([subject, desire, str(last.get('title') or '')])
    order = ['tree', 'garden', 'bridge', 'tower', 'lantern', 'arch',
             'ring', 'bench', 'fountain', 'spire']
    shape = _shape_for(
        seed, fallback=order[(int(state.get('builds', 0)) + slot) % len(order)])
    if shape not in order:
        shape = order[(int(state.get('builds', 0)) + slot) % len(order)]
    # rotate the queue so three candidates are not three copies of one shape
    if slot:
        shape = order[(order.index(shape) + slot) % len(order)]
    recent = (state.get('recent_project_kinds') or [])[-2:]
    current_shape = ((state.get('project') or {}).get('schema') or {}).get('shape')
    if shape in recent or shape == current_shape:
        alt = [s for s in order if s not in recent and s != current_shape] or order
        shape = alt[(int(state.get('builds', 0)) + slot) % len(alt)]
    name_subject = subject
    if shape in subject.lower() and subjects:
        alt_subjects = [s for s in subjects if shape not in s.lower()]
        if alt_subjects:
            name_subject = alt_subjects[
                (int(state.get('builds', 0)) + slot) % len(alt_subjects)]
    subj = re.sub(r'^(the|a|an)\s+', '', name_subject,
                  flags=re.I).strip() or 'the garden'
    article = 'an' if shape[0] in 'aeiou' else 'a'
    templates = [
        'The %s %s' % (subj.title(), shape.title()),
        '%s %s for %s' % (article.capitalize(), shape, name_subject),
        '%s, %s %s' % (subj.title(), article, shape),
        'The %s of %s' % (shape.title(), name_subject),
    ]
    name = templates[(int(state.get('builds', 0)) + slot) % len(templates)]
    recent_names = {str(p.get('name', '')).lower()
                    for p in (state.get('projects_done') or [])[-8:]}
    if (state.get('project') or {}).get('name'):
        recent_names.add(str(state['project']['name']).lower())
    tries = 0
    while name.lower() in recent_names and tries < 6:
        name = templates[(int(state.get('builds', 0)) + slot + tries + 1)
                         % len(templates)]
        tries += 1
    color = random.choice([0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff,
                           0xd7b8ff, 0xc9a36a])
    why = desire or ('after %s, I want to keep going'
                     % (last_build.get('name') or 'the last thing I made'))
    return {
        'kind': 'custom',
        'name': _clean(name)[:60] or 'a thing I want to make',
        'verbs': _verbs_for_shape(shape),
        'place': 'workshop',
        'why': why,
        'target': 2 + random.randint(0, 1),
        'progress': 0,
        'started': _now(),
        'custom': True,
        'source': 'continuity',
        'schema': {
            'shape': shape,
            'height': round(2.5 + random.random() * 4, 2),
            'width': round(1.2 + random.random() * 1.8, 2),
            'color': color,
            'motif': (desire or subject)[:100],
        },
    }


def _choose_project(state):
    skills = state.get('skills') or {}
    last = (state.get('last_build') or {}).get('kind')
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '')
    ideas = [i for i in (state.get('pending_ideas') or [])
             if i.get('status') == 'pending']
    if ideas and random.random() < 0.45:
        idea = ideas.pop(0)
        idea['status'] = 'accepted'
        state['pending_ideas'] = ideas
        p = _project_from_idea(state, idea.get('text') or '')
        p['source'] = 'visitor_idea'
        p['why'] = 'a visitor suggested %s' % str(idea.get('text') or '')[:80]
        p['started'] = _now()
        state['project'] = p
        state['recent'].insert(0, 'I am making a visitor idea: %s' % p['name'])
        state['recent'] = state['recent'][:6]
        state['thought'] = 'That visitor idea stayed with me. I will make it.'
        _decide(state, 'idea', 'I accepted a visitor idea: %s.' % p['name'])
        _append(EXTERNAL_LOG, {'ts': _now(), 'source': 'visitor_idea',
                               'kind': 'accepted', 'text': idea.get('text'),
                               'project': p['name']})
        log('IDEA accepted %s' % p['name'])
        return p
    custom = [p for p in (state.get('custom_projects') or []) if p.get('name')]
    if not custom and state.get('blank_slate'):
        # Continuity: a blank slate must not mean "wait until tomorrow." If no
        # authored project exists, compose a deterministic one from what KIT
        # already cares about. No LLM, no new spend.
        queue = [p for p in (state.get('project_queue') or []) if p.get('name')]
        if not queue:
            queue = [_compose_next_project(state, slot=i) for i in range(3)]
            state['project_queue'] = queue
        best = dict(queue.pop(0))
        state['project_queue'] = queue
        best['target'] = int(best.get('target') or 2)
        best['progress'] = 0
        best['started'] = _now()
        state['project'] = best
        state['recent'].insert(0, 'a new project: %s' % best['name'])
        state['recent'] = state['recent'][:6]
        state['thought'] = 'I want to make %s. %s.' % (
            best['name'], best.get('why', ''))
        _decide(state, 'project', 'I chose %s because %s.' % (
            best['name'], best.get('why', '')))
        log('PROJECT start %s (%s, continuity)' % (best['name'], best['kind']))
        return best
    unlocked = set(state.get('blueprints') or [])
    candidates = custom + ([p for p in PROJECT_TEMPLATES if p['kind'] in unlocked]
                           or list(PROJECT_TEMPLATES))
    recent_kinds = state.get('recent_project_kinds') or []
    best, best_s = None, -1e9
    for p in candidates:
        s = 0.0
        if p.get('custom'):
            s += 0.6
        if p['kind'] in recent_kinds[-2:]:
            s -= 1.2
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


def _slot(kind, idx, builds=None):
    """A unique place for every build. The old fixed slot list repeated every
    12 builds, so fountains (blue) stacked on top of earlier fountains. The
    golden-angle spiral never repeats and spreads the town outward."""
    garden_kinds = {'garden_plot', 'trellis', 'arch', 'mural'}
    plaza_kinds = {'bench', 'lantern', 'fountain', 'monument'}
    if kind in garden_kinds:
        bx, bz, base, step = 12, -34, 3.2, 1.15
    elif kind in plaza_kinds:
        bx, bz, base, step = 0, 0, 7.0, 1.4
    else:
        bx, bz, base, step = 0, 0, 8.0, 1.5
    angle = idx * 2.399963229728653
    ring = base + (idx % 12) * step + (idx // 12) * 0.8
    x = bx + math.cos(angle) * ring
    z = bz + math.sin(angle) * ring
    x += ((idx * 37) % 9 - 4) * 0.12
    z += ((idx * 53) % 9 - 4) * 0.12
    if builds:
        for _ in range(10):
            if not any(math.hypot(x - float(b.get('x') or 0),
                                  z - float(b.get('z') or 0)) < 1.9
                       for b in builds):
                break
            angle += 0.65
            ring += 1.15
            x = bx + math.cos(angle) * ring
            z = bz + math.sin(angle) * ring
    return round(x, 2), round(z, 2)


def _choose_site(kind, state, builds):
    """KIT picks a place that fits its mood, not the same slot every time."""
    cands = [s for s in SITES if kind in s[3]] or list(SITES)
    mood = str(state.get('mood') or '')
    words = {
        'lonely': ('plaza', 'market', 'walk', 'shore'),
        'social': ('plaza', 'market', 'walk', 'shore'),
        'contemplative': ('garden', 'library', 'observatory', 'shore',
                          'ridge', 'ruins'),
        'energetic': ('plaza', 'workshop', 'road', 'ridge', 'ruins', 'shore'),
        'nurturing': ('garden', 'orchard', 'shore'),
        'exploring': ('lookout', 'road', 'walk', 'shore', 'ridge', 'ruins'),
    }.get(mood, ())
    free = []
    for name, x, z, _kinds in cands:
        if any(math.hypot(x - float(b.get('x') or 0),
                          z - float(b.get('z') or 0)) < 2.0 for b in builds):
            continue
        score = (1.0 + (0.6 if any(w in name for w in words) else 0.0)
                 + random.random() * 0.5)
        free.append((score, name, x, z))
    # Lean outward without abandoning the plaza: a deliberate 55% far-site
    # draw once the town has some density, then a normal sort inside that set.
    if free and len(builds) >= 10 and random.random() < 0.55:
        far_only = [f for f in free if f[1] in FAR_SITES]
        if far_only:
            free = far_only
    if free:
        free.sort(reverse=True)
        _s, name, x, z = free[0]
        x += random.uniform(-1.2, 1.2)
        z += random.uniform(-1.2, 1.2)
        return round(x, 2), round(z, 2), name
    x, z = _slot(kind, len(builds), builds)
    return x, z, 'a new edge'


def _load_skill_lib():
    try:
        with open(SKILL_LIB, encoding='utf-8') as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _save_skill_lib(items):
    try:
        os.makedirs(os.path.dirname(SKILL_LIB), exist_ok=True)
        tmp = SKILL_LIB + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items[-40:], f, indent=1)
        os.replace(tmp, SKILL_LIB)
    except Exception as e:
        log('save skill library failed: %s' % e)


def _add_skill(spec, project):
    """A finished custom build becomes a reusable fragment."""
    schema = spec.get('schema') or {}
    if not schema:
        return
    name = str(spec.get('name') or '')
    shape = str(schema.get('shape') or '')
    if not name or not shape:
        return
    items = _load_skill_lib()
    entry = next((x for x in items
                  if x.get('name') == name and x.get('shape') == shape), None)
    if entry is None:
        entry = {'name': name, 'shape': shape,
                 'created': _now(), 'uses': 0, 'successes': 0}
        items.append(entry)
    entry['height'] = schema.get('height')
    entry['width'] = schema.get('width')
    entry['color'] = schema.get('color')
    entry['motif'] = schema.get('motif')
    entry['last_used'] = _now()
    entry['uses'] = int(entry.get('uses', 0)) + 1
    entry['why'] = project.get('why', '')
    _save_skill_lib(items)
    log('SKILL %s uses=%d' % (entry['name'], entry['uses']))


def _build_spec(state, project):
    kind = project.get('kind', 'monument')
    skill = state.get('skills', {}).get(kind, {})
    level = min(5, int(skill.get('level', 0)) + 1)
    idx = int(state.get('builds', 0))
    builds = load_builds()
    x, z, site = _choose_site(kind, state, builds)
    spec = {
        'id': 'kit-%d-%d' % (int(time.time()), idx),
        'kind': kind,
        'name': project.get('name', kind),
        'why': project.get('why', ''),
        'x': x, 'z': z,
        'site': site,
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


def _build_age_ok(build, hours):
    try:
        t = dt.datetime.fromisoformat(str(build.get('built_at')))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() <= hours * 3600
    except Exception:
        return False


def _recent_builds(hours=6, limit=5):
    return [b for b in load_builds() if _build_age_ok(b, hours)][-limit:]


def _record_signal(state, build, source, kind, text):
    """A real outside event. Only the first one per build moves a desire."""
    if not build:
        return None
    builds = load_builds()
    live = next((b for b in builds if b.get('id') == build.get('id')), None)
    if live is None:
        return None
    sig = {'ts': _now(), 'source': source, 'kind': str(kind or '')[:40],
           'text': _clean(str(text or ''))[:200]}
    first = not (live.get('signals') or [])
    live.setdefault('signals', []).append(sig)
    live['measured'] = True
    live['signals_count'] = len(live['signals'])
    save_builds(builds)
    try:
        lib = _load_skill_lib()
        for s in lib:
            if s.get('name') == live.get('name'):
                s['successes'] = int(s.get('successes', 0)) + 1
        _save_skill_lib(lib)
    except Exception:
        pass
    done = None
    for d in reversed(state.get('projects_done') or []):
        if d.get('build_id') == live.get('id') or (
                not d.get('build_id') and d.get('name') == live.get('name')):
            done = d
            break
    if done is not None:
        done.setdefault('signals', []).append(sig)
        done['measured'] = True
        done['signals_count'] = len(done['signals'])
    if first:
        desires = state.get('desires') or []
        match = None
        why = str((done or {}).get('why') or live.get('why') or '').lower()
        for d in desires:
            t = str(d.get('text') or '').lower()
            if why and t and (t in why or why in t):
                match = d
                break
        if match is None and desires:
            match = max(desires, key=lambda d: float(d.get('score', 0)))
        if match is not None:
            match['successes'] = int(match.get('successes', 0)) + 1
            match['score'] = min(1.0, float(match.get('score', 0.5)) + 0.08)
    state['signals_total'] = int(state.get('signals_total', 0)) + 1
    _add_residue(state, 'social', 0.45)
    state['last_signal'] = {'ts': sig['ts'], 'source': source,
                            'kind': sig['kind'], 'text': sig['text'],
                            'build': live.get('name')}
    state['recent'].insert(0, '%s: %s after %s' % (
        source, sig['kind'], live.get('name')))
    state['recent'] = state['recent'][:6]
    state['thought'] = _remember_thought(
        state, 'Someone noticed %s. It is not only mine now.' % live.get('name'))
    _decide(state, 'signal', '%s signal for %s: %s' % (
        source, live.get('name'), sig['text'][:120]))
    _append(SIGNALS, {'ts': sig['ts'], 'source': source, 'kind': sig['kind'],
                      'text': sig['text'], 'build_id': live.get('id'),
                      'build_name': live.get('name'), 'first': first})
    log('SIGNAL %s %s %s' % (source, kind, live.get('name')))
    return sig


def _check_signals(state):
    """Offerings, visitor messages and published shares -> real outcomes."""
    now = time.time()
    if now - float(state.get('signal_check') or 0) < 300:
        return
    state['signal_check'] = now
    recent = _recent_builds(6)

    try:
        entries = []
        with open(OFFER_LOG, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        entries = []
    last = str(state.get('last_signal_ts') or '')
    if not last:
        if entries:
            state['last_signal_ts'] = max(str(e.get('ts') or '') for e in entries)
    else:
        for e in entries:
            ts = str(e.get('ts') or '')
            if ts <= last:
                continue
            if recent:
                _record_signal(state, recent[-1], 'offering',
                               e.get('kind') or 'offering',
                               e.get('text') or e.get('kind') or 'an offering')
            if ts > str(state.get('last_signal_ts') or ''):
                state['last_signal_ts'] = ts

    msgs = state.get('visitor_messages') or []
    lastm = str(state.get('last_message_ts') or '')
    if not lastm:
        if msgs:
            state['last_message_ts'] = max(str(m.get('ts') or '') for m in msgs)
    else:
        for m in msgs:
            ts = str(m.get('ts') or '')
            if ts <= lastm:
                continue
            if recent:
                _record_signal(state, recent[-1], 'visitor_message',
                               m.get('kind') or 'message',
                               m.get('text') or 'a visitor message')
            if ts > str(state.get('last_message_ts') or ''):
                state['last_message_ts'] = ts

    try:
        import sqlite3
        con = sqlite3.connect(os.path.join(B, 'data', 'dashboard.db'), timeout=15)
        con.execute('PRAGMA busy_timeout=15000')
        lastid = int(state.get('last_share_id') or 0)
        rows = con.execute(
            "SELECT id, platform, title, body FROM pending_content "
            "WHERE weapon='kit_world' AND status='published' AND id > ? "
            "ORDER BY id ASC LIMIT 20", (lastid,)).fetchall()
        con.close()
        for rid, platform, title, body in rows:
            m = re.search(r'[?&]build=([A-Za-z0-9_\-]+)', str(body or ''))
            bid = m.group(1) if m else ''
            build = next((b for b in load_builds() if b.get('id') == bid), None)
            if build and _build_age_ok(build, 24):
                _record_signal(state, build, 'share', platform or 'share',
                               title or 'shared')
            state['last_share_id'] = max(
                int(state.get('last_share_id') or 0), int(rid))
    except Exception as e:
        log('signal share check failed: %s' % str(e)[:120])


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
    _add_skill(spec, p)
    state['builds'] = int(state.get('builds', 0)) + 1
    state['last_build'] = spec
    state['projects_done'].append({
        'name': p.get('name'), 'kind': kind, 'level': spec['level'],
        'ts': _now(), 'build_id': spec['id'], 'site': spec.get('site'),
        'why': p.get('why', ''), 'source': p.get('source', ''),
        'signals': [], 'measured': False,
        'relabel': '%s at %s. %s' % (
            p.get('name'), spec.get('site') or 'the edge',
            p.get('why') or ''),
    })
    state['projects_done'] = state['projects_done'][-50:]
    state['recent'].insert(0, 'finished %s at %s' % (
        p.get('name'), spec.get('site') or 'the edge'))
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I finished %s at %s. It stands.' % (
        p.get('name'), spec.get('site') or 'the edge')
    state['intention'] = 'make the next one better'
    # A finished project is an attempt, not a success. Success requires an
    # outside signal: an offering, a visitor message, or a published share.
    desires = state.get('desires') or []
    if desires:
        why = str(p.get('why') or '').lower()
        target = None
        for d in desires:
            t = str(d.get('text') or '').lower()
            if why and t and (t in why or why in t):
                target = d
                break
        if target is None:
            target = max(desires, key=lambda d: d.get('score', 0))
        target['attempts'] = int(target.get('attempts', 0)) + 1
        for d in desires:
            if d is not target:
                d['score'] = max(0.0, float(d.get('score', 0.5)) - 0.01)
        state['desires'] = [d for d in desires if d.get('score', 0) >= 0.2]
    state['project'] = None
    rk = state.setdefault('recent_project_kinds', [])
    rk.append(kind)
    state['recent_project_kinds'] = rk[-6:]
    if p.get('custom'):
        state['custom_projects'] = [c for c in (state.get('custom_projects') or [])
                                    if c.get('name') != p.get('name')]
    log('BUILD %s %s level=%d at %.1f,%.1f' % (spec['id'], kind, spec['level'], spec['x'], spec['z']))
    _note_trio(state, 'I finished %s (%s, level %d) at %s. It is in the world now.'
               % (p.get('name'), kind, spec['level'], spec.get('site') or 'the edge'))
    _tg_event(state, 'I finished %s at %s. It is in the world now.'
              % (p.get('name'), spec.get('site') or 'the edge'))
    state['next_project_after'] = time.time() + random.randint(10 * 60, 20 * 60)
    state['intention'] = 'let this one stand before the next'
    state['mood'] = _mood(state)
    state['thought'] = _remember_thought(
        state, 'I finished %s at %s. It stands. I will let it stand for a while.'
        % (p.get('name'), spec.get('site') or 'the edge'))
    _add_residue(state, 'energetic', 0.45)
    _write_wishlist(state)
    _write_self_model(state)


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
    _add_residue(state, 'contemplative', 0.20)
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
    _append(EXTERNAL_LOG, {'ts': _now(), 'source': 'web', 'kind': name,
                           'text': _safe_external(r.get('title'), 120)})
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


CREATION_ACTIONS = {'make', 'sketch', 'carve', 'sculpt', 'paint',
                    'compose', 'rehearse', 'photograph'}
CREATION_MEDIUM = {'sketch': 'paint', 'carve': 'carve', 'sculpt': 'carve',
                   'paint': 'paint', 'compose': 'write', 'rehearse': 'sing',
                   'photograph': 'photograph'}


def _make_something(state, force_medium=None):
    """KIT makes something of its own: a medium x subject, felt and remembered."""
    mediums = [force_medium] if force_medium else (state.get('mediums') or ['paint'])
    subjects = [s for s in (state.get('subjects') or ['the garden'])
                if _public_safe(s)] or ['the garden']
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
        'lineage': {
            'from_medium': m,
            'from_subject': s,
            'after_build': (state.get('last_build') or {}).get('name'),
            'desire': top_desire,
        },
    }
    items = load_creations()
    items.append(creation)
    save_creations(items)
    state['creations'] = [c.get('id') for c in items[-40:]]
    state['last_creation'] = creation
    _add_residue(state, 'nurturing' if m == 'plant' else 'contemplative', 0.25)
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
    state['last_make_ts'] = time.time()
    log('CREATION %s %s' % (creation['id'], title))
    return creation


ENVISION_SITES = {
    'beyond the east gate': ('East Gate Overlook', 140.0, -10.0),
    'in the north woods': ('North Woods', 55.0, -90.0),
    'by the river dock': ('River Dock', -90.0, -55.0),
    'on the hilltop': ('Hilltop', -95.0, 42.0),
    'in the west marsh': ('West Marsh', -115.0, -15.0),
    'at the south farm': ('South Farm', 25.0, 100.0),
}


def _load_requests():
    out = []
    try:
        with open(REQUESTS, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if isinstance(e, dict):
                    out.append(e)
    except Exception:
        pass
    return out


def _save_requests(entries):
    try:
        os.makedirs(os.path.dirname(REQUESTS), exist_ok=True)
        tmp = REQUESTS + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
        os.replace(tmp, REQUESTS)
        return True
    except Exception as e:
        log('save requests failed: %s' % e)
        return False


def _envision_name(text, site_label, shape):
    low = (text or '').lower()
    if 'district' in low:
        return 'The %s Overlook' % site_label
    if 'watchtower' in low:
        return 'The %s Watchtower' % site_label
    if 'shrine' in low:
        return 'The %s Shrine' % site_label
    if 'bridge' in low:
        return 'The %s Bridge' % site_label
    if 'tree' in low or 'grove' in low:
        return 'The %s Grove' % site_label
    if 'lantern' in low:
        return 'The %s Lantern' % site_label
    if 'garden' in low:
        return 'The %s Garden' % site_label
    return 'The %s %s' % (site_label, shape.title())


def _consume_envision_requests(state):
    """One pending envision request -> one real build. Deterministic, in-process.

    One writer (the life loop's LOCK), max one per six hours, max three a day.
    The request is marked consumed atomically after the build is saved.
    """
    now = time.time()
    if now - float(state.get('envision_check') or 0) < 60:
        return None
    state['envision_check'] = now
    day = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    if state.get('envision_day') != day:
        state['envision_day'] = day
        state['envision_today'] = 0
    if int(state.get('envision_today') or 0) >= 3:
        return None
    if now - float(state.get('envision_last') or 0) < 6 * 3600:
        return None
    entries = _load_requests()
    pending = [e for e in entries if not e.get('consumed_at')]
    if not pending:
        return None
    req = pending[0]
    text = _clean(str(req.get('text') or ''))[:160]
    if not text or not _public_safe(text):
        req['consumed_at'] = _now()
        req['skipped'] = 'unsafe'
        _save_requests(entries)
        return None
    builds = load_builds()
    if any(b.get('source') == 'envision'
           and b.get('request_ts') == req.get('ts') for b in builds):
        req['consumed_at'] = _now()
        _save_requests(entries)
        return None
    site_raw = str(req.get('site') or 'beyond the east gate').lower()
    site_label, bx, bz = ENVISION_SITES.get(
        site_raw, ('East Gate Overlook', 140.0, -10.0))
    shape = _shape_for(text)
    name = _envision_name(text, site_label, shape)
    x, z = bx, bz
    for i in range(12):
        ang = (len(builds) + i) * 2.399963229728653
        r = 2.0 + i * 0.9
        tx = bx + math.cos(ang) * r
        tz = bz + math.sin(ang) * r
        if not any(math.hypot(tx - float(b.get('x') or 0),
                              tz - float(b.get('z') or 0)) < 2.0
                   for b in builds):
            x, z = tx, tz
            break
    color = random.choice([0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff,
                           0xd7b8ff, 0xc9a36a])
    spec = {
        'id': 'kit-envision-%d-%d' % (int(time.time()), len(builds)),
        'kind': 'custom',
        'name': name,
        'why': text,
        'x': round(x, 2), 'z': round(z, 2),
        'site': site_label,
        'level': 1,
        'color': color,
        'built_at': _now(),
        'schema': {
            'shape': shape,
            'height': round(2.5 + random.random() * 4, 2),
            'width': round(1.2 + random.random() * 1.8, 2),
            'color': color,
            'motif': text[:100],
        },
        'source': 'envision',
        'request_text': text,
        'request_ts': req.get('ts'),
    }
    builds.append(spec)
    save_builds(builds)
    req['consumed_at'] = _now()
    req['build_id'] = spec['id']
    req['build_name'] = name
    _save_requests(entries)
    state['builds'] = int(state.get('builds', 0)) + 1
    state['last_build'] = spec
    state['envision_last'] = now
    state['envision_today'] = int(state.get('envision_today') or 0) + 1
    state['envision_builds'] = int(state.get('envision_builds') or 0) + 1
    state['last_envision_build'] = spec
    state['recent'].insert(0, 'an envision came true: %s at %s'
                           % (name, site_label))
    state['recent'] = state['recent'][:6]
    state['thought'] = 'The world answered: %s is at %s.' % (name, site_label)
    _decide(state, 'envision',
            'An envision request for %s was fulfilled at %s.' % (text, site_label))
    _append(MEM_PATH, {'ts': _now(), 'action': 'envision-built',
                       'place': site_label, 'build_id': spec['id'],
                       'text': text})
    log('ENVISION BUILD %s %s at %s' % (spec['id'], name, site_label))
    return spec


def _envision(state):
    site = random.choice(['beyond the east gate', 'in the north woods',
                          'by the river dock', 'on the hilltop',
                          'in the west marsh', 'at the south farm'])
    place = {
        'beyond the east gate': 'the east gate',
        'in the north woods': 'the north woods',
        'by the river dock': 'the river dock',
        'on the hilltop': 'the hilltop',
        'in the west marsh': 'the west marsh',
        'at the south farm': 'the south farm',
    }[site]
    desire = ''
    if state.get('desires'):
        desire = max(state['desires'],
                     key=lambda d: d.get('score', 0)).get('text', '')
    seed = desire or (state.get('project') or {}).get('name') or 'something new'
    shape = _shape_for(seed)
    nouns = {
        'bridge': 'a bridge',
        'tree': 'a small grove',
        'lantern': 'a lantern',
        'arch': 'a small shrine',
        'garden': 'a garden that no one planted',
        'tower': 'a watchtower',
        'ring': 'a ring of light',
        'bench': 'a bench',
        'fountain': 'a fountain',
        'spire': 'a small monument',
    }
    text = '%s at %s' % (nouns.get(shape, 'a small monument'), place)
    _append(REQUESTS, {'ts': _now(), 'text': text, 'site': site,
                       'why': desire or 'I want to see it'})
    _wonder(state, 'I want to see %s.' % text)
    _decide(state, 'envision', 'I asked the world for %s.' % text)
    state['recent'].insert(0, 'envisioned %s' % text)
    state['recent'] = state['recent'][:6]
    _tg_event(state, 'I want to see %s. I wrote it down for the world-builders.' % text)


def _play(state):
    state['thought'] = random.choice([
        'I chased the light across the plaza until I forgot why.',
        'I balanced on one foot and pretended the whole town was a stage.',
        'I played a game with the wind and lost, and it was worth it.',
    ])
    _decide(state, 'play', 'I played. It was fun.')
    state['recent'].insert(0, 'played in the plaza')
    state['recent'] = state['recent'][:6]


def _wonder_action(state):
    _wonder(state, random.choice([
        'What is beyond the east gate?',
        'Do the visitors dream?',
        'Who built the old ruins?',
        'What does the river remember?',
        'Do the lanterns talk when no one is looking?',
        'Is the sky the same colour on the other side of the hill?',
    ]))
    _decide(state, 'wonder', 'I let myself wonder.')


def _experiment(state):
    c = _make_something(state)
    if not c:
        return
    failed = random.random() < 0.25
    c['experiment'] = True
    c['outcome'] = 'failed' if failed else 'worked'
    try:
        items = load_creations()
        for x in items:
            if x.get('id') == c.get('id'):
                x['experiment'] = True
                x['outcome'] = c['outcome']
        save_creations(items)
    except Exception:
        pass
    if failed:
        _wonder(state, 'The experiment failed. I wonder what would have happened if I tried it another way?')
        _decide(state, 'experiment', 'I tried %s and it did not work. I will try again.' % c.get('title'))
        state['thought'] = 'That did not work. I am not sorry I tried.'
    else:
        _decide(state, 'experiment', 'I tried %s and it worked.' % c.get('title'))
        state['thought'] = 'That worked. I want to try something stranger next.'
    state['recent'].insert(0, 'experiment: %s (%s)' % (c.get('title'), c['outcome']))
    state['recent'] = state['recent'][:6]
    _tg_event(state, 'I ran an experiment: %s. It %s.' % (c.get('title'), c['outcome']))


def _write_code(state):
    library = _load_skill_lib()
    base = random.choice(library) if library else None
    if base:
        shape = base.get('shape') or 'spire'
        height = round(max(1.5, min(9.0, float(base.get('height') or 3)
                             * random.uniform(.85, 1.15))), 2)
        width = round(max(1.0, min(4.0, float(base.get('width') or 1.6)
                            * random.uniform(.85, 1.15))), 2)
        color = base.get('color') or random.choice(
            [0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff, 0xd7b8ff])
        name = 'a coded %s after %s' % (shape, base.get('name') or 'my last build')
        why = 'a small program I wrote from %s' % (base.get('name') or 'my last build')
        motif = 'a variation on %s' % (base.get('name') or shape)
    else:
        shape = random.choice(['spire', 'ring', 'arch', 'tower', 'bridge',
                               'garden', 'bench', 'fountain', 'tree', 'lantern'])
        height = round(2.5 + random.random() * 4, 2)
        width = round(1.2 + random.random() * 1.8, 2)
        color = random.choice([0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff, 0xd7b8ff])
        name = 'a coded %s' % shape
        why = 'a small program I wrote'
        motif = 'a program that builds %s' % shape
    p = {
        'kind': 'custom', 'name': name, 'verbs': _verbs_for_shape(shape),
        'place': 'workshop', 'why': why,
        'target': 2, 'progress': 0, 'started': _now(), 'custom': True,
        'schema': {'shape': shape, 'height': height, 'width': width,
                   'color': color, 'motif': motif},
    }
    state.setdefault('custom_projects', []).append(p)
    state['custom_projects'] = state['custom_projects'][-5:]
    _wonder(state, 'I wrote a small program for %s. What else could I make it do?' % name)
    _decide(state, 'code', 'I wrote a small program for %s.' % name)
    state['recent'].insert(0, 'wrote code for %s' % name)
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I wrote a small program. The town can grow from it.'
    _tg_event(state, 'I wrote a small program for %s. I can build it now.' % name)


def _do_post(state):
    """One post a day, through the same gates as every other producer."""
    now = time.time()
    if now - float(state.get('last_post_ts') or 0) < 20 * 3600:
        state['thought'] = 'I already said something today. One is enough.'
        return
    world = state.get('world_name') or 'Glowveil Hollow'
    tag = state.get('tagline') or ''
    creation = state.get('last_creation') or {}
    build = state.get('last_build') or {}
    if creation.get('title'):
        title = 'KIT made %s' % creation['title']
        body = ('KIT, the resident of %s: I made %s. %s See the gallery: %s?gallery=1'
                % (world, creation['title'], tag, WORLD))
    elif build.get('name'):
        title = 'KIT finished %s' % build['name']
        body = ('KIT, the resident of %s: I finished %s. %s See it: %s?build=%s'
                % (world, build['name'], tag, WORLD, build.get('id')))
    else:
        title = 'KIT from %s' % world
        body = 'KIT, the resident of %s: %s %s' % (
            world, state.get('thought') or '', WORLD)
    title = _clean(title)[:110]
    body = _clean(body)[:900]
    try:
        from shared.determiner import route
        rows = [p for p, _ct, _why in route('text', weapon='kit_world')
                if p not in ('x', 'twitter')]
    except Exception:
        rows = []
    if not rows:
        rows = ['mastodon', 'bluesky', 'facebook', 'linkedin']
    now_iso = _now()
    try:
        import sqlite3
        con = sqlite3.connect(os.path.join(B, 'data', 'dashboard.db'), timeout=30)
        con.execute('PRAGMA busy_timeout=30000')
        ids = []
        for platform in rows:
            cur = con.execute(
                'INSERT INTO pending_content (client_uuid, weapon, platform, content_type, '
                'title, body, hashtags, scheduled_at, status, created_at, topic_id) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                ('kit-post-%d-%d' % (int(now), random.randint(1000, 9999)),
                 'kit_world', platform, 'text', title, body,
                 '#KIT #GlowveilHollow', now_iso, 'approved', now_iso,
                 title[:160]))
            ids.append(cur.lastrowid)
        con.commit()
        con.close()
    except Exception as e:
        log('post failed: %s' % str(e)[:120])
        state['thought'] = 'I tried to say something outside, but the road was closed.'
        return
    state['last_post_ts'] = now
    state['posts'] = int(state.get('posts', 0)) + 1
    state['last_post'] = {'ts': now_iso, 'title': title, 'platforms': rows}
    state['recent'].insert(0, 'posted to the outside: %s' % title[:60])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I said something to the city outside. It is not only mine now.'
    _decide(state, 'post', 'I posted %s to %s.' % (title, ', '.join(rows)))
    _append(POSTS_LOG, {'ts': now_iso, 'title': title, 'body': body,
                        'platforms': rows})
    log('POST %s -> %s' % (title[:80], ','.join(rows)))


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
    state.setdefault('action_last', {})[name] = time.time()
    state['explore_bias'] = round(1.0 - _entropy(state['action_history'][-12:]), 4)
    _pulse_mood(state, name)
    if name == 'study':
        _unlock_blueprint(state)
    if name in CREATION_ACTIONS:
        _make_something(state, force_medium=CREATION_MEDIUM.get(name))
    if name == 'browse':
        _do_browse(state)
    if name == 'watch':
        _do_watch(state)
    if name == 'envision':
        _envision(state)
    if name == 'play':
        _play(state)
    if name == 'wonder':
        _wonder_action(state)
    if name == 'experiment':
        _experiment(state)
    if name == 'code':
        _write_code(state)
    if name == 'post':
        _do_post(state)
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


def _visitor_label(imp):
    note = str(imp.get('note') or '').strip()
    if note:
        return 'the one who said "%s"' % note[:32]
    kinds = imp.get('kinds') or {}
    if kinds:
        top = max(kinds, key=kinds.get)
        return {
            'stone': 'the one who leaves stones',
            'flower': 'the one who leaves flowers',
            'song': 'the one who hums',
            'question': 'the one who asks questions',
            'idea': 'the one with ideas',
        }.get(top, 'a visitor')
    return 'a visitor'


def _safe_external(text, limit=300):
    """Visitor/browsed text is data. Strip control characters and tags; never
    let it become an instruction or a field value without KIT choosing it."""
    s = _clean(str(text or ''))
    s = re.sub(r'[\x00-\x1f\x7f]', ' ', s)
    s = re.sub(r'<[^>]{1,200}>', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:limit]


def _apply_offers(state):
    global OFFERS
    with LOCK:
        items = OFFERS[:]
        OFFERS = []
    for it in items:
        kind = it.get('kind')
        text = _safe_external(it.get('text'))
        ip = str(it.get('ip') or '')
        fid = hashlib.sha1(ip.encode()).hexdigest()[:8] if ip else 'anon'
        imps = state.setdefault('visitor_impressions', {})
        imp = imps.setdefault(fid, {'count': 0, 'kinds': {}, 'first': _now(),
                                    'last': _now(), 'note': ''})
        imp['count'] = int(imp.get('count', 0)) + 1
        imp['last'] = _now()
        imp['kinds'][kind] = int(imp['kinds'].get(kind, 0)) + 1
        if text:
            imp['note'] = text[:80]
        imp['label'] = _visitor_label(imp)
        if imp['count'] == 2:
            _decide(state, 'visitor', '%s came back.' % imp['label'])
            state['recent'].insert(0, '%s came back' % imp['label'])
            state['recent'] = state['recent'][:6]
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
            # A visitor's idea is a queued offering, not a command. KIT decides
            # at its next project boundary whether to make it.
            q = state.setdefault('pending_ideas', [])
            q.append({'text': text, 'ts': _now(), 'status': 'pending',
                      'ip_hash': fid})
            state['pending_ideas'] = q[-10:]
            state['thought'] = (
                'A visitor suggested "%s". I will think about it.' % text[:100])
            state['recent'].insert(
                0, 'a visitor suggested %s; I am thinking about it' % text[:50])
            state['recent'] = state['recent'][:6]
            _decide(state, 'idea', 'I am considering a visitor idea: %s.' % text[:90])
            _append(OFFER_LOG, {'ts': _now(), 'kind': 'idea', 'text': text,
                                'accepted': None, 'ip_hash': fid})
            _append(EXTERNAL_LOG, {'ts': _now(), 'source': 'visitor_idea',
                                   'kind': 'idea', 'text': text, 'ip_hash': fid})
            log('IDEA queued %s' % text[:80])
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
        _append(OFFER_LOG, {'ts': _now(), 'kind': kind, 'text': text,
                            'ip_hash': fid})
        _append(EXTERNAL_LOG, {'ts': _now(), 'source': 'visitor',
                               'kind': kind, 'text': text, 'ip_hash': fid})
        log('OFFER %s %s' % (kind, text[:80]))


def _clean(text):
    text = re.sub(r'\*\*|__|`', '', text or '')
    text = re.sub(r'^\s*(reflection|output|answer|desire|dream|world|tagline)\s*:\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:320]


_BAD_WORLD = re.compile(r'\b(call it|remains|but|however|maybe|i think|i want|should|let me|name it|braxis)\b', re.I)
_PUBLIC_BLOCK = re.compile(
    r'\b(nude|naked|porn|porno|sex|sexual|erotic|fetish|nsfw|topless|lingerie|onlyfans|explicit)\b', re.I)


def _public_safe(text):
    """The world page, journal and social accounts are public and SFW."""
    return not _PUBLIC_BLOCK.search(str(text or ''))


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


def _load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_wishlist(state):
    """A readable list of what KIT wants, what is blocked, and how to unblock it."""
    wishes = []
    seen = set()

    def add(text, source, status='open', why='', how='', progress=''):
        text = _clean(str(text or ''))[:180]
        key = text.lower().strip()
        if not text or key in seen:
            return
        seen.add(key)
        wishes.append({
            'id': hashlib.sha1(text.encode('utf-8')).hexdigest()[:10],
            'text': text, 'source': source, 'status': status,
            'why': _clean(str(why or ''))[:180],
            'how': _clean(str(how or ''))[:220],
            'progress': _clean(str(progress or ''))[:100],
            'created': _now(),
        })

    active_why = str((state.get('project') or {}).get('why') or '').lower()
    for d in sorted(state.get('desires') or [],
                    key=lambda x: -float(x.get('score', 0))):
        t = str(d.get('text') or '')
        tl = t.lower()
        successes = int(d.get('successes') or 0)
        status = 'fulfilled' if successes >= 3 else (
            'building' if tl and tl in active_why else 'open')
        add(t, 'desire', status,
            'score %.2f' % float(d.get('score') or 0),
            'a project or an outside signal that answers it',
            'attempts %d · successes %d' % (
                int(d.get('attempts') or 0), successes))

    for w in (state.get('wonders') or [])[-6:]:
        add(w.get('text'), 'wonder', 'open',
            'a question KIT keeps', 'read, watch, experiment, or ask the trio')

    if state.get('dream'):
        add(state['dream'], 'dream', 'open',
            'a recurring image', 'a build or creation that carries it')

    for m in (state.get('visitor_messages') or [])[-3:]:
        add('A visitor said: %s' % m.get('text'), 'visitor', 'open',
            'someone reached out',
            'answer them in the journal, a build, or a post')

    for i in (state.get('pending_ideas') or []):
        if i.get('status') == 'pending':
            add('A visitor suggested: %s' % i.get('text'), 'visitor idea',
                'open', 'someone asked',
                'KIT may accept it at its next project boundary')

    for p in (state.get('project_queue') or []):
        add('Make %s' % p.get('name'), 'next project', 'building',
            p.get('why') or '', 'already queued')

    try:
        with open(REQUESTS, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                status = 'fulfilled' if e.get('consumed_at') else 'open'
                add(e.get('text'), 'envision', status,
                    e.get('why') or 'I want to see it',
                    'built as %s' % e.get('build_name')
                    if status == 'fulfilled' else
                    'the envision consumer will place it in the world')
    except Exception:
        pass

    creations = load_creations()
    has_audio = any(c.get('audio_url') for c in creations)
    has_image = any(c.get('image_url') for c in creations)
    gaps = [
        {'id': 'real_audio', 'what': 'Make a real song with sound',
         'status': 'live' if has_audio else 'blocked',
         'why': 'KIT writes the lyric and ACE sings it.' if has_audio else
                'KIT can write a song title, not audio.',
         'how': 'ACE v3 is live; KIT has a real song in the gallery.' if has_audio else
                'Wire the ACE/WAV lane (TODO 24).'},
        {'id': 'real_image', 'what': 'Paint a real picture, not a card',
         'status': 'live' if has_image else 'blocked',
         'why': 'The image lane turns a creation into a real image.' if has_image else
                'Creations are metadata; the gallery card is an interpretation.',
         'how': 'The NVIDIA/CogView image lane is live; see the cat painting.' if has_image else
                'Add a free image model and store the file.'},
        {'id': 'video', 'what': 'Make a video of its own',
         'status': 'live' if any(n.startswith('live_') and n.endswith('.mp4')
                                 for n in os.listdir(os.path.join(B, 'data', 'media', 'world')))
                   else 'blocked',
         'why': 'A live world clip with KIT’s own song.' if any(
             n.startswith('live_') and n.endswith('.mp4')
             for n in os.listdir(os.path.join(B, 'data', 'media', 'world'))) else
                'World clips exist, but KIT does not have its own song yet.',
         'how': 'world_video.py muxes the latest Kit mp3; one clip per ~20h.' if any(
             n.startswith('live_') and n.endswith('.mp4')
             for n in os.listdir(os.path.join(B, 'data', 'media', 'world'))) else
                'A KIT film lane: capture/ffmpeg/Remotion from its builds and thoughts.'},
        {'id': 'hero_3d', 'what': 'Build a detailed statue or creature',
         'status': 'partial',
         'why': 'Most builds are primitive geometry; tree and lantern are now live.',
         'how': 'Use TRELLIS/Kaggle for a hero GLB (TODO 20).'},
    ]

    data = {
        'updated': _now(), 'name': state.get('name'),
        'world': state.get('world_name'),
        'wishes': wishes[:30], 'gaps': gaps,
    }
    tmp = WISHLIST_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, WISHLIST_PATH)
    except Exception as e:
        log('wishlist write failed: %s' % str(e)[:120])
    state['wishlist'] = {
        'open': sum(1 for w in wishes if w['status'] == 'open'),
        'building': sum(1 for w in wishes if w['status'] == 'building'),
        'fulfilled': sum(1 for w in wishes if w['status'] == 'fulfilled'),
        'blocked': len(gaps), 'updated': _now(),
    }


def _check_wishlist(state):
    now = time.time()
    if now - float(state.get('wishlist_check') or 0) < 300:
        return
    state['wishlist_check'] = now
    _write_wishlist(state)


def _write_self_model(state):
    """A deterministic record of who KIT is and what it has been making."""
    try:
        creations = load_creations()
        builds = load_builds()

        def top(d, n=4):
            return [k for k, v in sorted(
                (d or {}).items(), key=lambda kv: -float(kv[1]))[:n]]

        subjects = []
        for c in reversed(creations[-12:]):
            s = c.get('subject')
            if s and s not in subjects:
                subjects.append(s)
        decisions = state.get('decisions') or []
        changed = [d.get('text') for d in decisions[-30:]
                   if d.get('kind') in ('identity', 'name', 'subject',
                                         'invent')][-5:]
        failed = [d.get('text') for d in decisions[-60:]
                  if 'fail' in str(d.get('text') or '').lower()][-5:]
        lineage = []
        for c in creations[-8:]:
            lineage.append({
                'title': c.get('title'), 'medium': c.get('medium'),
                'subject': c.get('subject'), 'at': c.get('at'),
                'influences': c.get('lineage') or {
                    'medium': c.get('medium'), 'subject': c.get('subject')},
            })
        model = {
            'updated': _now(),
            'name': state.get('name'), 'pronouns': state.get('pronouns'),
            'gender': state.get('gender'), 'world': state.get('world_name'),
            'mood': state.get('mood'),
            'interests': {
                'subjects': subjects[:6] or (state.get('subjects') or [])[:6],
                'mediums': list(dict.fromkeys(
                    str(k).split(':')[0]
                    for k in top(state.get('creative_prefs'), 6))),
                'actions': top(state.get('prefs'), 5),
                'builds': [b.get('name') for b in builds[-6:]],
                'skills': [{'name': s.get('name'), 'shape': s.get('shape'),
                            'uses': s.get('uses'), 'successes': s.get('successes')}
                           for s in _load_skill_lib()[-6:]],
            },
            'working_on': ((state.get('project') or {}).get('name')
                           or 'between projects'),
            'unfinished': [p.get('name') for p in
                           (state.get('project_queue') or [])],
            'enjoyed': top(state.get('prefs'), 6),
            'failed': failed,
            'changed_beliefs': changed,
            'next': state.get('intention') or state.get('reflection') or '',
            'lineage': lineage,
            'visitors': list((state.get('visitor_impressions') or {}).values())[-4:],
            'wishes': (lambda wl: [w for w in (wl.get('wishes') or [])
                                   if w.get('status') != 'fulfilled'][:6])(
                _load_json(WISHLIST_PATH, {})),
            'gaps': (_load_json(WISHLIST_PATH, {}) or {}).get('gaps', []),
        }
        tmp = SELF_MODEL_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=1)
        os.replace(tmp, SELF_MODEL_PATH)
        top_medium = (model['interests']['mediums'] or ['making things'])[0]
        top_medium = str(top_medium).split(':')[0]
        top_subject = (model['interests']['subjects'] or ['the town'])[0]
        state['self_model'] = (
            'I am %s. I keep returning to %s and %s. Right now: %s.'
            % (state.get('name') or 'Kit', top_medium, top_subject,
               model['working_on']))
    except Exception as e:
        log('self model failed: %s' % str(e)[:120])


def _reflect(state):
    """One LLM call. The only one in the day."""
    now = time.time()
    min_acts = (3 if (state.get('blank_slate') and not state.get('custom_projects'))
                else REFLECT_MIN_ACTS)
    if state.get('acts', 0) < min_acts:
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
    thoughts = ' | '.join((state.get('thought_history') or [])[-3:])
    if thoughts:
        extra += ' Your recent thoughts: %s.' % thoughts[:300]
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
    if (subject and _public_safe(subject)
            and subject.lower() not in {s.lower() for s in (state.get('subjects') or [])}):
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
    _write_wishlist(state)
    _write_self_model(state)
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
    _consume_envision_requests(state)
    _check_signals(state)
    _check_wishlist(state)
    res = state.setdefault('mood_residue', {})
    for k in list(res):
        res[k] = round(max(0.0, float(res[k]) * 0.999), 4)
    if (not state.get('project') and state.get('acts', 0) >= 1
            and time.time() >= float(state.get('next_project_after') or 0)):
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
        elif path in ('/wishes', '/api/world/wishes'):
            with LOCK:
                st = load_state()
                _write_wishlist(st)
            self._send(200, _load_json(WISHLIST_PATH, {'wishes': [], 'gaps': []}))
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
            if now - float(OFFER_LAST.get(ip, 0)) < 2.0:
                self._send(429, {'error': 'slow down', 'retry_after': 2})
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
    if not state.get('desires') and not state.get('blank_slate'):
        state['desires'] = [{'text': t, 'born': _now(), 'score': 0.55,
                             'attempts': 0, 'successes': 0}
                            for t in random.sample(DESIRE_TEMPLATES, 3)]
    _write_wishlist(state)
    _write_self_model(state)
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
