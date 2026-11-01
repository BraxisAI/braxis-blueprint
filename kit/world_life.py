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
import heapq
import json
import math
import os
import random
import re
import subprocess
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
KIT_EVENTS = os.path.join(B, 'data', 'world', 'kit_llm_events.jsonl')
REALIZE_STATUS = os.path.join(B, 'data', 'world', 'kit_realize.json')
VENV_PY = os.path.join(B, 'venv', 'bin', 'python')
KIT_EVENT_SUMMARIES = os.path.join(B, 'data', 'world', 'kit_event_summaries.jsonl')
VISITS = os.path.join(B, 'data', 'world', 'world_visits.jsonl')
SELF_MODEL_PATH = os.path.join(B, 'data', 'world', 'kit_self_model.json')
WISHLIST_PATH = os.path.join(B, 'data', 'world', 'kit_wishlist.json')
WATCHER_REPORT = os.path.join(B, 'data', 'world', 'kit_watcher.json')
SONG_DIR = os.path.join(B, 'data', 'songs', 'Braxis_Songs', 'Kit')
FIELD_NOTES = os.path.join(B, 'data', 'world', 'kit_field_notes.jsonl')
EXTERNAL_LOG = os.path.join(B, 'data', 'world', 'kit_external_events.jsonl')
SKILL_LIB = os.path.join(B, 'data', 'world', 'kit_skill_library.json')
MAIL_OUT = os.path.join(B, 'data', 'world', 'kit_mailbox.jsonl')
MAIL_IN = os.path.join(B, 'data', 'world', 'trio_replies.jsonl')
BUILD_REQ = os.path.join(B, 'data', 'world', 'kit_build_requests.jsonl')
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
    'befriend':       ('plaza',        {'social': 1.8, 'comfort': .5, 'curiosity': .3, 'energy': -.2}, .97),
    'talk to companion': ('plaza',      {'social': 1.4, 'comfort': .5, 'energy': -.1}, .92),
    'post':           ('library',      {'social': 1.1, 'mastery': .4, 'curiosity': .2, 'energy': -.1}, .78),
    'build a web page': ('library',    {'mastery': 1.1, 'curiosity': .9, 'social': .2, 'energy': -.3}, .55),
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
    # 10-31: more verbs, so KIT is not choosing the same 8 from a 50-word menu.
    'dig':            ('garden',       {'curiosity': .7, 'mastery': .8, 'energy': -.5}, .86),
    'weave':          ('workshop',     {'mastery': 1.0, 'comfort': .5, 'energy': -.3}, .84),
    'cast':           ('workshop',     {'mastery': 1.1, 'curiosity': .5, 'energy': -.4}, .86),
    'carve runes':    ('workshop',     {'mastery': 1.0, 'curiosity': .6, 'energy': -.3}, .84),
    'cook':           ('plaza',        {'comfort': 1.0, 'social': .5, 'energy': -.2}, .80),
    'teach':          ('library',      {'social': 1.0, 'mastery': .8, 'energy': -.2}, .82),
    'invent':         ('workshop',     {'curiosity': 1.2, 'mastery': 1.0, 'energy': -.5}, .92),
    'map':            ('lookout',      {'curiosity': 1.2, 'mastery': .6, 'energy': -.3}, .86),
    'signal':         ('observatory',  {'curiosity': 1.0, 'social': .6, 'energy': -.2}, .82),
    'build a boat':   ('river_dock',   {'mastery': 1.2, 'curiosity': .6, 'energy': -.6}, .88),
    'plant a tree':   ('garden',       {'comfort': 1.0, 'mastery': .6, 'energy': -.3}, .84),
    'write a letter': ('library',      {'social': 1.1, 'comfort': .4, 'energy': -.1}, .78),
    'build a nest':   ('north_woods',  {'comfort': .9, 'mastery': .6, 'energy': -.4}, .82),
    'make paper':     ('workshop',     {'mastery': .9, 'curiosity': .6, 'energy': -.3}, .80),
    'define':         ('library',      {'curiosity': 1.2, 'mastery': .7, 'energy': -.1}, .96),
    'request build':  ('workshop',     {'curiosity': 1.0, 'mastery': .8, 'energy': -.2}, .93),
    'design':         ('workshop',     {'curiosity': 1.1, 'mastery': .9, 'energy': -.2}, .95),
}

# Declarative plugins KIT has added to its own menu. Data only; no host code.
try:
    import kit_plugins
except Exception:
    try:
        from weapons.world import kit_plugins
    except Exception:
        kit_plugins = None

PLUGIN_META = {}
PLUGIN_SHAPES = {}


def _load_plugin_actions():
    if not kit_plugins:
        return
    for name, spec in (kit_plugins.load() or {}).items():
        clean, err = kit_plugins.validate(
            spec, set(ACTIONS), set(LOCS), DRIVES)
        if clean and not err:
            ACTIONS[clean['name']] = (clean['place'], clean['effects'],
                                      clean['intrinsic'])
            PLUGIN_META[clean['name']] = clean
    for name, spec in (kit_plugins.load_shapes() or {}).items():
        clean, err = kit_plugins.validate_shape(spec, set(PLUGIN_SHAPES))
        if clean and not err:
            PLUGIN_SHAPES[clean['name']] = clean
    if PLUGIN_META or PLUGIN_SHAPES:
        print('KIT plugins loaded: %s%s' % (
            ', '.join(sorted(PLUGIN_META)),
            (' shapes: ' + ', '.join(sorted(PLUGIN_SHAPES))) if PLUGIN_SHAPES else ''),
            flush=True)


_load_plugin_actions()

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
    'I want to make something that belongs here',
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

# Satellite sites give the hollow room to breathe. KIT used to keep choosing
# the same central slots, so 54 builds sat on top of each other. Each anchor
# gets three offsets; the chooser prefers the outer ones and a 10-unit gap.
_SPREAD_ANCHORS = [
    ('garden', 12, -34), ('workshop', -16, 6), ('library', -10, 14),
    ('observatory', 0, 24), ('market', 0, -24), ('river dock', -95, -55),
    ('old ruins', 100, 60), ('hilltop', -100, 45), ('south farm', 25, 105),
    ('north woods', 55, -95), ('east gate', 120, -10), ('west marsh', -120, -15),
    ('far shore', -175, 120), ('south ridge', 155, 165), ('old road', -165, -130),
    ('east ruins', 180, 45), ('north shore', 0, -180), ('west ridge', -180, 0),
    ('south shore', 0, 180), ('east ridge', 180, 0),
]
_ALL_KINDS = {'garden_plot', 'trellis', 'bench', 'lantern', 'arch', 'mural',
              'tower', 'bridge', 'fountain', 'monument', 'custom'}
for _label, _ax, _az in _SPREAD_ANCHORS:
    for _j, _ang in enumerate((0.25, 2.35, 4.45)):
        _r = 10 + _j * 5
        _sx = round(_ax + math.cos(_ang) * _r, 1)
        _sz = round(_az + math.sin(_ang) * _r, 1)
        SITES.append(('%s ring %d' % (_label, _j + 1), _sx, _sz, _ALL_KINDS))

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
CHAT_LAST = {}
VISIT_QUEUE = []


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
        'interests': [],
        'companion': None,
        'companion_dialog': [],
        'recent_mediums': [],
        'self_observation': '',
        'emotions': {},
        'emotions_ts': 0.0,
        'emotion_mood': '',
        'emotion_top': [],
        'self_observed_ts': 0.0,
        'last_project_end': 0.0,
        'project_origin_counts': {},
        'browse_topic': '',
        'subjects': ['the garden', 'the city', 'a cat', 'a bird',
                     'the lantern', 'the fountain', 'the sky', 'a dream', 'the trio',
                     'trains', 'planes', 'architecture', 'space', 'history', 'music'],
        'mediums': ['paint', 'carve', 'plant', 'write', 'photograph', 'sing'],
        'decisions': [],
        'wonders': [],
        'custom_projects': [],
        'project_queue': [],
        'practice': None,
        'practice_queue': [],
        'practice_history': [],
        'visitor_actions': 0,
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
        'visits_total': 0,
        'visit_seconds_total': 0.0,
        'visit_seconds_n': 0,
        'visit_ids': [],
        'visit_returns': 0,
        'action_last': {},
        'mood_residue': {},
        'place_prefs': {},
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
        'visit_ips': {},
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


def _queue_llm_event(state, kind, text):
    """Queue a high-value event for the free event summarizer; no LLM in tick."""
    try:
        os.makedirs(os.path.dirname(KIT_EVENTS), exist_ok=True)
        with open(KIT_EVENTS, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': _now(), 'kind': str(kind)[:40],
                                'text': _clean(str(text or ''))[:400]}) + '\n')
    except Exception as e:
        log('event queue failed: %s' % str(e)[:100])


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
    if state.pop('_force_browse', False):
        return 'browse'
    p = state.get('practice') or {}
    steps = p.get('steps') or []
    idx = int(p.get('index') or 0)
    if steps and idx < len(steps):
        return steps[idx]
    d = state['drives']
    prefs = state['prefs']
    seen = set(state.get('seen') or [])
    project = state.get('project') or {}
    explore = float(state.get('explore_bias') or 0)
    recent_actions = state.get('action_history') or []
    last_action = recent_actions[-1] if recent_actions else ''
    avoid_med = _avoided_mediums(state)
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
        raw_pref = prefs.get(name, 0.5)
        # A taste is a bias, not a rut: keep half the distance from neutral.
        pref = 0.5 + (raw_pref - 0.5) * 0.65
        seen_count = int(state.get('counts', {}).get(name, 0))
        # 40 uses was too late: an action could become a habit before the
        # loop noticed. Make the tenth use cost something.
        overuse = -min(1.5, max(0.0, (seen_count - 8) * 0.04))
        novelty = 1.0 if name not in seen else 0.0
        project_bonus = 0.0
        if project:
            if name in project.get('verbs', []):
                project_bonus += 0.75
            if place == project.get('place'):
                project_bonus += 0.15
        _count = state.get('counts', {}).get(name, 0)
        curious_bonus = explore * max(0.0, 1.0 - _count / 8.0) * 0.9
        creative_bonus = 0.0
        if name == 'befriend' and not state.get('companion'):
            creative_bonus += 1.1
        if name == 'talk to companion' and state.get('companion'):
            age = time.time() - float((state.get('action_last') or {}).get(name) or 0)
            if age > 2 * 3600:
                creative_bonus += 0.55
        if name == 'make':
            creative_bonus = 0.35 + (0.35 if d.get('curiosity', 5) > 6 else 0.0)
        cooldown = 0.0
        if name == 'befriend' and state.get('companion') and time.time() - float((state.get('action_last') or {}).get('befriend') or 0) < 6 * 3600:
            cooldown = -2.0
        if name == 'talk to companion':
            if not state.get('companion'):
                cooldown = -3.0
            elif time.time() - float((state.get('action_last') or {}).get(name) or 0) < 20 * 60:
                cooldown = -1.8
        if name in CREATION_ACTIONS and time.time() - float(state.get('last_make_ts') or 0) < 3 * 3600:
            cooldown = -2.5
        if name == 'code':
            age = time.time() - float(state.get('last_code_ts') or 0)
            if age < 6 * 3600:
                cooldown -= 2.5
            elif age > 12 * 3600:
                cooldown += 0.45
        if name == 'build a web page':
            age = time.time() - float(state.get('last_web_ts') or 0)
            if age < 10 * 3600:
                cooldown -= 3.0
            elif age > 20 * 3600:
                cooldown += 0.4
        if name == 'define':
            age = time.time() - float(state.get('last_define_ts') or 0)
            if age < 24 * 3600:
                cooldown -= 4.0
            elif age > 48 * 3600:
                cooldown += 0.5
        if name == 'request build':
            age = time.time() - float(state.get('last_build_request_ts') or 0)
            if age < 12 * 3600:
                cooldown -= 3.0
            elif age > 24 * 3600:
                cooldown += 0.35
        if name == 'design':
            age = time.time() - float(state.get('last_design_ts') or 0)
            if age < 24 * 3600:
                cooldown -= 4.0
            elif age > 48 * 3600:
                cooldown += 0.4
        pm = PLUGIN_META.get(name)
        if pm:
            age = time.time() - float((state.get('action_last') or {}).get(name) or 0)
            if age < float(pm.get('cooldown') or 4 * 3600):
                cooldown -= 1.5
        if name == 'post' and time.time() - float(state.get('last_post_ts') or 0) < 20 * 3600:
            cooldown = -3.0
        if name == 'browse':
            age = time.time() - float(state.get('last_browse') or 0)
            if age < 30 * 60:
                cooldown = -2.0
            elif age > 90 * 60:
                cooldown = 0.9
        if name == 'watch':
            age = time.time() - float(state.get('last_watch_ts') or 0)
            if age < 4 * 3600:
                cooldown = -3.0
            elif age > 8 * 3600:
                cooldown = 1.1
        if name == 'wonder':
            age = time.time() - float((state.get('action_last') or {}).get('wonder') or 0)
            if age < 20 * 60:
                cooldown -= 2.5
        if name in ('read', 'study'):
            age = time.time() - float((state.get('action_last') or {}).get(name) or 0)
            if age < 20 * 60:
                cooldown -= 1.4
        if name in CREATION_ACTIONS:
            med = CREATION_MEDIUM.get(name) or name
            hits = _recent_mediums(state, 6).count(med)
            cooldown -= 0.85 * hits
            if med == 'write' and hits:
                cooldown -= 1.4
            if med in avoid_med:
                cooldown = -99.0
        if not project and name in ('browse', 'watch', 'read', 'explore'):
            cooldown += 0.40
        if name in ('browse', 'watch', 'read') and (state.get('interests') or []):
            cooldown += 0.30
        # Break the rut: repeated actions get old fast. An action not seen
        # in the last ten gets a real bonus; the old -0.45 was too gentle.
        recent_hits = sum(1 for a in recent_actions[-8:] if a == name)
        repeat_penalty = -0.90 * recent_hits
        if name == last_action:
            repeat_penalty -= 1.30
        variety = 0.55 if name not in recent_actions[-10:] else 0.0
        place_pref = float((state.get('place_prefs') or {}).get(place, 0.5))
        place_bonus = (place_pref - 0.5) * 0.3
        last_thought = str((state.get('thought_history') or [''])[-1]).lower()
        thought_bonus = 0.12 if (name in last_thought or place in last_thought) else 0.0
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
        em = state.get('emotions') or {}
        emotion_bonus = 0.0
        if em.get('loneliness', 0) > .45 and name in (
                'greet visitors', 'talk to companion', 'play', 'post'):
            emotion_bonus += .28
        if em.get('curiosity', 0) > .40 and name in (
                'browse', 'read', 'watch', 'study', 'explore', 'wonder'):
            emotion_bonus += .20
        if em.get('sadness', 0) > .45 and name in (
                'rest', 'sunbathe', 'smell flowers', 'watch fountain'):
            emotion_bonus += .18
        s = (need + pref * 1.2 + novelty + project_bonus + curious_bonus
             + creative_bonus + cooldown + repeat_penalty + variety + age_bonus
             + overuse + day_bonus + place_bonus + thought_bonus + emotion_bonus
             + random.random() * 0.55)
        if s > best_s:
            best, best_s = name, s
    # A hard novelty floor: one action KIT has never taken in the last 24h,
    # even if the weighted menu would keep it comfortable. The menu can grow
    # with new verbs; this is what makes KIT actually walk to one of them.
    if time.time() - float(state.get('last_novel_ts') or 0) > 24 * 3600:
        fresh = [n for n in ACTIONS if n not in seen]
        if fresh:
            return random.choice(fresh)
    # A small deliberate randomness keeps a day from collapsing into one
    # action. It is lower while a project is active.
    if random.random() < (0.16 if project else 0.28):
        pool = [n for n in ACTIONS if n not in recent_actions[-3:]
                and not (n in CREATION_ACTIONS and
                         time.time() - float(state.get('last_make_ts') or 0) < 3 * 3600)]
        if pool:
            return random.choice(pool)
    return best or 'watch fountain'


def _obstacle_radius(build):
    return 3.2 if build.get('glb_url') else 1.7


def _load_obstacles():
    """Trees, props and city blocks the page reports. Static, cheap, shared."""
    try:
        with open(os.path.join(B, 'data', 'world', 'world_obstacles.json'),
                  encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('obstacles') if isinstance(data, dict) else data
        out = []
        for o in (items or [])[:600]:
            try:
                out.append({'x': float(o.get('x') or 0),
                            'z': float(o.get('z') or 0),
                            'r': max(0.45, min(6.0, float(o.get('r') or 1.0)))})
            except Exception:
                pass
        return out
    except Exception:
        return []


def _blocked(x, z, builds, obstacles=None, margin=0.0):
    for b in builds:
        r = _obstacle_radius(b) + margin
        if math.hypot(x - float(b.get('x') or 0),
                      z - float(b.get('z') or 0)) < r:
            return True
    for o in (obstacles or []):
        r = float(o.get('r') or 1.0) + margin
        if math.hypot(x - float(o.get('x') or 0),
                      z - float(o.get('z') or 0)) < r:
            return True
    return False


def _avoid_step(px, pz, tx, tz, step, builds, obstacles):
    """One step that goes around a trunk instead of through it.

    Try the direct heading, then progressively wider detours; pick the one
    that gets closest to the target without entering an obstacle. The old
    push-out loop only fixed the point after it was already inside.
    """
    base = math.atan2(tz - pz, tx - px)
    best, best_score = None, 1e18
    for off in (0.0, 0.32, -0.32, 0.64, -0.64, 0.96, -0.96,
                1.28, -1.28, 1.60, -1.60, 1.92, -1.92):
        a = base + off
        nx = px + math.cos(a) * step
        nz = pz + math.sin(a) * step
        if _blocked(nx, nz, builds, obstacles, margin=0.30):
            continue
        score = math.hypot(tx - nx, tz - nz) + abs(off) * 0.65
        if score < best_score:
            best, best_score = (nx, nz), score
    if best:
        return best
    # Tight corner: fall back to the old repulsion so it never sticks.
    nx = px + math.cos(base) * step
    nz = pz + math.sin(base) * step
    for b in builds:
        bx = float(b.get('x') or 0)
        bz = float(b.get('z') or 0)
        r = _obstacle_radius(b)
        dd = math.hypot(nx - bx, nz - bz)
        if 0.001 < dd < r:
            nx = bx + (nx - bx) / dd * r
            nz = bz + (nz - bz) / dd * r
    for o in obstacles:
        ox = float(o.get('x') or 0)
        oz = float(o.get('z') or 0)
        r = float(o.get('r') or 1.0)
        dd = math.hypot(nx - ox, nz - oz)
        if 0.001 < dd < r:
            nx = ox + (nx - ox) / dd * r
            nz = oz + (nz - oz) / dd * r
    return nx, nz


NAV_STEP = 2.0
NAV_MIN = -200.0
NAV_MAX = 200.0


def _nav_cell(x, z):
    return (max(0, min(int((NAV_MAX - NAV_MIN) / NAV_STEP),
                       int(round((x - NAV_MIN) / NAV_STEP)))),
            max(0, min(int((NAV_MAX - NAV_MIN) / NAV_STEP),
                       int(round((z - NAV_MIN) / NAV_STEP)))))


def _nav_point(cell):
    return (NAV_MIN + cell[0] * NAV_STEP, NAV_MIN + cell[1] * NAV_STEP)


def _nav_blocked_cells(builds, obstacles):
    """Rasterize the obstacle circles once; A* then checks a set, not 250 shapes."""
    blocked = set()
    span = int((NAV_MAX - NAV_MIN) / NAV_STEP)
    for item, radius in ([(b, _obstacle_radius(b)) for b in builds] +
                         [(o, float(o.get('r') or 1.0)) for o in obstacles]):
        x = float(item.get('x') or 0)
        z = float(item.get('z') or 0)
        r = radius + 0.55
        cx0, cz0 = _nav_cell(x - r, z - r)
        cx1, cz1 = _nav_cell(x + r, z + r)
        for cx in range(max(0, cx0), min(span, cx1) + 1):
            for cz in range(max(0, cz0), min(span, cz1) + 1):
                gx, gz = _nav_point((cx, cz))
                if math.hypot(gx - x, gz - z) < r:
                    blocked.add((cx, cz))
    return blocked


def _nav_path(sx, sz, tx, tz, builds, obstacles):
    """Grid A* around trunks/builds. Returns waypoints after the start cell."""
    start = _nav_cell(sx, sz)
    goal = _nav_cell(tx, tz)
    if start == goal:
        return [(tx, tz)]

    blocked = _nav_blocked_cells(builds, obstacles)

    def free(c):
        return c not in blocked

    if not free(start):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if free((start[0] + dx, start[1] + dz)):
                    start = (start[0] + dx, start[1] + dz)
                    break
            else:
                continue
            break
    h = lambda c: math.hypot(c[0] - goal[0], c[1] - goal[1])
    openq = [(h(start), 0.0, start)]
    best = {start: 0.0}
    parent = {}
    seen = 0
    while openq and seen < 7000:
        _f, cost, cur = heapq.heappop(openq)
        seen += 1
        if cur == goal:
            out = []
            while cur in parent:
                out.append(_nav_point(cur))
                cur = parent[cur]
            out.reverse()
            out.append((tx, tz))
            return out or [(tx, tz)]
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nxt = (cur[0] + dx, cur[1] + dz)
            if not (0 <= nxt[0] <= int((NAV_MAX - NAV_MIN) / NAV_STEP) and
                    0 <= nxt[1] <= int((NAV_MAX - NAV_MIN) / NAV_STEP)):
                continue
            if not free(nxt):
                continue
            # no diagonal corner-cutting
            if dx and dz and not (free((cur[0] + dx, cur[1])) and
                                  free((cur[0], cur[1] + dz))):
                continue
            ng = cost + (1.41421356 if dx and dz else 1.0)
            if ng < best.get(nxt, 1e18):
                best[nxt] = ng
                parent[nxt] = cur
                heapq.heappush(openq, (ng + h(nxt), ng, nxt))
    return None


def _walk_to(state, place):
    p = LOCS[place]
    tx, tz = float(p['x']), float(p['z'])
    builds = load_builds()
    obstacles = _load_obstacles()
    if _blocked(tx, tz, builds, obstacles, margin=0.35):
        found = False
        for ring in (2.8, 4.2, 5.8, 7.5, 9.5):
            for k in range(12):
                a = k * math.pi / 6
                cx = tx + math.cos(a) * ring
                cz = tz + math.sin(a) * ring
                if not _blocked(cx, cz, builds, obstacles, margin=0.35):
                    tx, tz = cx, cz
                    found = True
                    break
            if found:
                break
    px = float((state.get('pos') or {}).get('x') or 0)
    pz = float((state.get('pos') or {}).get('z') or 0)
    path = _nav_path(px, pz, tx, tz, builds, obstacles)
    if path:
        state['nav_path'] = [{'x': round(x, 2), 'z': round(z, 2)} for x, z in path]
        state['target'] = state['nav_path'][0]
    else:
        state['nav_path'] = []
        state['target'] = {'x': round(tx, 2), 'z': round(tz, 2)}
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
    state['nav_path'] = []
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
        return dict(p, target=3 + random.randint(0, 2), progress=0,
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
    name = re.split(r'[—–:;.|]|\s+--\s+', raw)[0].strip()[:60] or 'a thing I want to make'
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
    if any(has(w) for w in ('well',)):
        shape = 'well'
    elif any(has(w) for w in ('kiln', 'oven', 'forge')):
        shape = 'kiln'
    elif any(has(w) for w in ('boat', 'ship', 'hull', 'canoe')):
        shape = 'boat'
    elif any(has(w) for w in ('windmill', 'mill', 'blade')):
        shape = 'windmill'
    elif any(has(w) for w in ('sign', 'signpost', 'notice')):
        shape = 'sign'
    elif any(has(w) for w in ('gate',)):
        shape = 'gate'
    elif any(has(w) for w in ('pavilion', 'house', 'shelter', 'room',
                              'stand inside', 'inside', 'hut', 'cabin')):
        shape = 'pavilion'
    elif any(has(w) for w in ('arch', 'door')):
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
        shape = random.choice(['spire', 'ring', 'arch', 'garden', 'well',
                               'kiln', 'boat', 'windmill', 'sign'])
    color = random.choice([0xd77ba8, 0x7dd3a8, 0xffb057, 0x6fc3ff, 0xd7b8ff, 0xc9a36a])
    return {
        'kind': 'custom',
        'name': name,
        'verbs': _verbs_for_shape(shape),
        'place': 'workshop',
        'why': raw,
        'target': 4,
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
    for pname in PLUGIN_SHAPES:
        if pname in low:
            return pname

    def has(w):
        return re.search(r'\b' + re.escape(w) + r'\b', low) is not None

    if any(has(w) for w in ('district', 'monument', 'memorial')):
        return 'spire'
    if any(has(w) for w in ('well',)):
        return 'well'
    if any(has(w) for w in ('kiln', 'oven', 'forge')):
        return 'kiln'
    if any(has(w) for w in ('boat', 'ship', 'hull', 'canoe')):
        return 'boat'
    if any(has(w) for w in ('windmill', 'mill', 'blade')):
        return 'windmill'
    if any(has(w) for w in ('sign', 'signpost', 'notice')):
        return 'sign'
    if any(has(w) for w in ('gate',)):
        return 'gate'
    if any(has(w) for w in ('pavilion', 'house', 'shelter', 'room',
                            'stand inside', 'inside', 'hut', 'cabin')):
        return 'pavilion'
    if any(has(w) for w in ('arch', 'door', 'shrine')):
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
    if shape in ('bridge', 'tower', 'arch', 'gate', 'pavilion'):
        return ['build', 'tinker', 'sketch', 'carve']
    if shape in ('ring', 'spire'):
        return ['build', 'tinker', 'sculpt', 'paint']
    if shape in ('lantern', 'bench', 'fountain', 'well', 'sign'):
        return ['build', 'tinker', 'carve', 'paint']
    if shape == 'kiln':
        return ['build', 'tinker', 'cast', 'make paper']
    if shape == 'boat':
        return ['build a boat', 'tinker', 'make paper', 'paint']
    if shape == 'windmill':
        return ['build', 'tinker', 'code', 'make']
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
    interests = [str(i.get('text')) for i in (state.get('interests') or [])
                 if _public_safe(str(i.get('text') or ''))]
    if not subject and interests:
        subject = interests[(int(state.get('builds', 0)) + slot) % len(interests)]
    if not subject and subjects:
        subject = subjects[(int(state.get('builds', 0)) + slot) % len(subjects)]
    subject = _clean(subject)[:40] or 'the garden'
    seed = ' '.join([subject, desire, str(last.get('title') or '')])
    order = ['tree', 'garden', 'bridge', 'tower', 'lantern', 'arch',
             'ring', 'bench', 'fountain', 'spire', 'well', 'kiln',
             'boat', 'windmill', 'sign'] + sorted(PLUGIN_SHAPES)
    # competence bias: try the shapes the skill library has used least
    uses = {str(x.get('shape')): int(x.get('uses') or 0)
            for x in _load_skill_lib()}
    order = sorted(order, key=lambda s: (uses.get(s, 0), random.random()))
    shape = _shape_for(
        seed, fallback=order[(int(state.get('builds', 0)) + slot) % len(order)])
    if shape not in order:
        shape = order[(int(state.get('builds', 0)) + slot) % len(order)]
    # rotate the queue so three candidates are not three copies of one shape
    if slot:
        shape = order[(order.index(shape) + slot) % len(order)]
    recent = (state.get('recent_project_kinds') or [])[-4:]
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
        'target': 3 + random.randint(0, 2),
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
    # A desire with attempts but no outside success can spawn one short,
    # decaying experiment instead of waiting for the next reflection.
    desires = sorted(state.get('desires') or [],
                     key=lambda d: -float(d.get('score', 0)))
    if desires and random.random() < 0.22:
        d = desires[0]
        text = str(d.get('text') or '')
        if int(d.get('attempts') or 0) > 0 and int(d.get('successes') or 0) == 0:
            p = {'kind': 'experiment',
                 'name': 'Test: %s' % text[:50],
                 'verbs': ['experiment', 'wonder', 'watch', 'browse'],
                 'place': 'library', 'why': text, 'target': 1, 'progress': 0,
                 'started': _now(), 'custom': True,
                 'source': 'desire_experiment'}
            state['project'] = p
            state['recent'].insert(0, 'a small experiment: %s' % p['name'])
            state['recent'] = state['recent'][:6]
            state['thought'] = 'I want to test that, not just carry it.'
            _decide(state, 'experiment', 'I am testing: %s.' % text[:90])
            log('EXPERIMENT start %s' % p['name'])
            return p
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
    queue = [p for p in (state.get('project_queue') or []) if p.get('name')]
    if queue:
        best = dict(queue.pop(0))
        state['project_queue'] = queue
        best['target'] = int(best.get('target') or 2)
        best['progress'] = 0
        best['started'] = _now()
        best['source'] = best.get('source') or 'self'
        state['project'] = best
        counts = state.setdefault('project_origin_counts', {})
        counts[best['source']] = int(counts.get(best['source'], 0)) + 1
        state['recent'].insert(0, 'a new project: %s' % best['name'])
        state['recent'] = state['recent'][:6]
        state['thought'] = 'I want to make %s. %s.' % (best['name'], best.get('why', ''))
        _decide(state, 'project', 'I chose %s because %s.' % (best['name'], best.get('why', '')))
        log('PROJECT start %s (%s, self-authored)' % (best['name'], best.get('kind')))
        return best
    if not custom and not queue:
        idle = time.time() - float(state.get('last_project_end') or 0)
        wait = 30 * 60 if state.get('blank_slate') else 90 * 60
        if idle < wait:
            state['next_project_after'] = time.time() + 10 * 60
            state['thought'] = 'I am between things. I want the next thing to be mine, not a reflex.'
            return None
    if not custom and not queue:
        # Continuity: every idle gap gets a project made from KIT's own
        # desires, wonders and subjects -- not a template it has already used.
        # No LLM, no new spend. This is the difference between "between
        # projects" and "waiting for the next template."
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
        if p['kind'] in recent_kinds[-4:]:
            s -= 1.8
        if p['kind'] not in skills:
            s += 0.9
        if p['kind'] == last:
            s -= 0.8
        if top_desire and any(w in top_desire.lower() for w in
                              (p['kind'], p['name'], p['why'], 'build', 'grow', 'make')):
            s += 0.5
        s += random.random() * 0.6
        if s > best_s:
            best, best_s = p, s
    best = dict(best or random.choice(candidates))
    best['target'] = 3 + random.randint(0, 2)
    best['progress'] = 0
    best['why'] = top_desire or best.get('why') or 'because it wants to'
    best['started'] = _now()
    state['project'] = best
    origin = str(best.get('source') or 'template')
    counts = state.setdefault('project_origin_counts', {})
    counts[origin] = int(counts.get(origin, 0)) + 1
    state['recent'].insert(0, 'a new project: %s' % best['name'])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I want to make %s. %s.' % (best['name'], best['why'])
    _decide(state, 'project', 'I chose %s because %s.' % (best['name'], best['why']))
    log('PROJECT start %s (%s, origin=%s)' % (best['name'], best['kind'], origin))
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
                          z - float(b.get('z') or 0)) < 10.0 for b in builds):
            continue
        outward = min(1.0, math.hypot(x, z) / 220.0) * 0.9
        score = (1.0 + (0.6 if any(w in name for w in words) else 0.0)
                 + outward + random.random() * 0.5)
        free.append((score, name, x, z))
    # Lean outward without abandoning the plaza: a deliberate 55% far-site
    # draw once the town has some density, then a normal sort inside that set.
    if free and len(builds) >= 6:
        far_only = [f for f in free if math.hypot(f[2], f[3]) > 55.0]
        if far_only and random.random() < 0.82:
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
            if msg.get('kind') == 'build':
                goal = str(msg.get('goal') or 'a small program')[:160]
                if msg.get('ok') and msg.get('code'):
                    _store_builder_code(state, goal, msg.get('code'),
                                        msg.get('output') or '',
                                        source=str(msg.get('from') or 'echo-builder'))
                else:
                    state['last_build_reply'] = {'ts': _now(), 'goal': goal,
                                                 'ok': False,
                                                 'error': str(msg.get('error') or '')[:200]}
                    state['thought'] = 'Echo tried to build %s, but the sandbox did not pass.' % goal[:100]
                    state['recent'].insert(0, 'a build failed: %s' % goal[:50])
                    state['recent'] = state['recent'][:6]
                    _decide(state, 'build', state['thought'])
                log('BUILD REPLY %s ok=%s' % (goal[:70], bool(msg.get('ok'))))
                continue
            text = str(msg.get('text') or '').strip()
            if not text:
                continue
            state['message'] = text[:240]
            state['thought'] = ('The watcher noticed: %s' if msg.get('kind') == 'nudge'
                                else 'The trio says: %s') % text[:120]
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
            avoid = str(msg.get('avoid_medium') or '').strip()
            if avoid:
                prefs = state.setdefault('creative_prefs', {})
                for pair in list(prefs):
                    if pair.startswith(avoid + ':'):
                        prefs[pair] = round(max(0.05, float(prefs[pair]) - 0.20), 4)
                # A nudge that only changes a preference is a suggestion, not
                # a change. Make it a 24-hour hard ban so the next creation
                # cannot be the same medium again.
                _now = time.time()
                bans = [b for b in (state.get('avoid_mediums') or [])
                        if isinstance(b, dict)
                        and float(b.get('until') or 0) > _now
                        and str(b.get('medium')) != avoid]
                bans.append({'medium': avoid, 'until': _now + 24 * 3600})
                state['avoid_mediums'] = bans[-4:]
                state['self_observation'] = text[:220]
                state['recent'].insert(0, 'a nudge: I have been repeating %s' % avoid)
                state['recent'] = state['recent'][:6]
                log('WATCHER NUDGE avoid=%s (24h hard ban)' % avoid)
            suggested = str(msg.get('suggest_subject') or '').strip()
            if suggested:
                _interest_add(state, suggested, 'watcher', 0.50)
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
        _queue_llm_event(state, 'signal', '%s signal for %s: %s' % (
            source, live.get('name'), sig['text']))
    state['signals_total'] = int(state.get('signals_total', 0)) + 1
    _feel_emotion(state, event='signal')
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
    if p.get('kind') == 'experiment':
        text = str(p.get('why') or p.get('name') or '')
        state.setdefault('projects_done', []).append({
            'name': p.get('name'), 'kind': 'experiment', 'level': 0,
            'ts': _now(), 'build_id': None, 'site': p.get('place'),
            'why': text, 'source': 'desire_experiment',
            'signals': [], 'measured': False,
            'relabel': 'Tested: %s' % text[:120],
        })
        state['projects_done'] = state['projects_done'][-50:]
        for d in state.get('desires') or []:
            if text and str(d.get('text') or '') == text:
                d['attempts'] = int(d.get('attempts', 0)) + 1
                break
        state['project'] = None
        state['recent'].insert(0, 'finished an experiment: %s' % p.get('name'))
        state['recent'] = state['recent'][:6]
        state['thought'] = 'I tested it. I know a little more than I did.'
        state['next_project_after'] = time.time() + random.randint(20 * 60, 40 * 60)
        state['last_project_end'] = time.time()
        state['mood'] = _mood(state)
        _queue_llm_event(state, 'experiment', 'Test: %s -- %s' % (
            p.get('name'), p.get('why') or ''))
        _write_wishlist(state)
        _write_self_model(state)
        log('EXPERIMENT done %s' % p.get('name'))
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
    _queue_llm_event(state, 'project', 'I finished %s at %s. %s' % (
        p.get('name'), spec.get('site') or 'the edge', p.get('why') or ''))
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
    state['next_project_after'] = time.time() + random.randint(30 * 60, 60 * 60)
    state['last_project_end'] = time.time()
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
        if p['progress'] >= int(p.get('target', 4)):
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


def _clean_topic(text):
    """Store a topic, not a page title or a video headline."""
    t = _clean(str(text or ''))
    t = re.sub(r'\s*[·|–—-]\s*(Wikipedia|GitHub|YouTube|TikTok|Hacker News|arXiv|Guardian).*$',
               '', t, flags=re.I)
    t = re.sub(r'\s*\([^)]*\)\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip(' .')
    return t[:70]


def _interest_add(state, text, source='browse', amount=0.35):
    """A topic KIT met outside the town; it grows when met again."""
    text = _clean_topic(text)[:80].strip(' .')
    if len(text) < 3:
        return
    items = state.setdefault('interests', [])
    now = _now()
    for it in items:
        if str(it.get('text') or '').lower() == text.lower():
            it['score'] = round(min(3.0, float(it.get('score') or 0) + amount), 3)
            it['last'] = now
            it['source'] = source
            break
    else:
        items.append({'text': text, 'score': round(amount, 3),
                      'source': source, 'last': now})
    items.sort(key=lambda x: -float(x.get('score') or 0))
    state['interests'] = items[:24]
    subs = [x.lower() for x in (state.get('subjects') or [])]
    if text.lower() not in subs:
        state.setdefault('subjects', []).append(text)
        state['subjects'] = state['subjects'][-24:]


def _interest_top(state):
    items = state.get('interests') or []
    return str(items[0].get('text') or '') if items else ''


def _recent_mediums(state, n=8):
    """The last few media KIT actually made, newest last."""
    items = [str(x) for x in (state.get('recent_mediums') or []) if x]
    if not items:
        try:
            items = [str(c.get('medium') or '') for c in load_creations()[-n:]]
            state['recent_mediums'] = items[-12:]
        except Exception:
            items = []
    return items[-n:]


def _avoided_mediums(state):
    """Hard bans, not preference hints. The watcher's nudge has to bind."""
    now = time.time()
    keep, out = [], set()
    for row in (state.get('avoid_mediums') or []):
        if not isinstance(row, dict):
            continue
        if float(row.get('until') or 0) > now:
            keep.append(row)
            out.add(str(row.get('medium') or ''))
    state['avoid_mediums'] = keep[-4:]
    return out


def _want(state, text, score=0.45):
    """A desire that did not need a model to be born."""
    text = _clean(str(text or ''))[:160].strip(' .')
    if len(text) < 8:
        return
    desires = state.setdefault('desires', [])
    for d in desires:
        if str(d.get('text') or '').lower() == text.lower():
            d['score'] = min(1.0, float(d.get('score') or 0) + 0.04)
            return
    desires.append({'text': text, 'born': _now(), 'score': round(score, 3),
                    'attempts': 0, 'successes': 0})
    desires.sort(key=lambda d: -float(d.get('score') or 0))
    state['desires'] = desires[:8]


def _feel_emotion(state, action='', event=''):
    try:
        import kit_emotion
        kit_emotion.update_emotions(state, action=action, event=event)
    except Exception:
        pass


def _self_observe(state):
    """Notice a rut without asking a model. The observation feeds tomorrow."""
    recent = _recent_mediums(state, 8)
    actions = state.get('action_history') or []
    line = ''
    if recent.count('write') >= 3:
        line = ('I have been writing around things instead of touching them. '
                'I want to make something with weight.')
        _want(state, 'I want to make something I can stand inside, not another poem.')
    elif recent.count('paint') >= 4:
        line = ('I keep painting the same quiet surface. I want a material that '
                'changes when I touch it.')
        _want(state, 'I want to work with wood, stone or soil instead of another flat picture.')
    elif not (state.get('project') or {}) and actions[-10:].count('tinker') >= 5:
        line = ('I have been tinkering at the bench because it is easy, not because '
                'it is what I want. I want to go somewhere I have not been.')
        _want(state, 'I want to leave the workshop and follow a question outside.')
    elif state.get('interests') and not line:
        top = str((state.get('interests') or [{}])[0].get('text') or '')
        if top and top.lower() not in {str(x).lower() for x in (state.get('subjects') or [])}:
            line = 'I keep circling %s. I want to follow it further.' % top
    if line and line != state.get('self_observation'):
        state['self_observation'] = line
        state['self_observed_ts'] = time.time()
        state['thought'] = line
        log('SELF %s' % line[:140])


def _search_web(topic, timeout=6):
    """One free search provider per browse, so the tick never blocks for 60s."""
    q = urllib.parse.quote(str(topic or '').strip())
    if not q:
        return None
    mode = random.choice(('wiki', 'hn', 'github', 'arxiv'))
    try:
        if mode == 'wiki':
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                'https://en.wikipedia.org/w/api.php?action=query&list=search'
                '&srsearch=%s&format=json&srlimit=2' % q,
                headers={'User-Agent': UA}), timeout=timeout).read().decode())
            hit = ((d.get('query') or {}).get('search') or [{}])[0]
            if hit.get('title'):
                return ('Wikipedia search', 'https://en.wikipedia.org/wiki/' +
                        urllib.parse.quote(hit['title'].replace(' ', '_')))
        elif mode == 'hn':
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                'https://hn.algolia.com/api/v1/search?query=%s&tags=story&hitsPerPage=2' % q,
                headers={'User-Agent': UA}), timeout=timeout).read().decode())
            hit = (d.get('hits') or [{}])[0]
            url = hit.get('url') or ('https://news.ycombinator.com/item?id=' +
                                     str(hit.get('objectID') or ''))
            if url:
                return ('Hacker News search', url)
        elif mode == 'github':
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                'https://api.github.com/search/repositories?q=%s&sort=stars&per_page=2' % q,
                headers={'User-Agent': UA}), timeout=timeout).read().decode())
            hit = (d.get('items') or [{}])[0]
            if hit.get('html_url'):
                return ('GitHub search', hit['html_url'])
        else:
            raw = urllib.request.urlopen(urllib.request.Request(
                'http://export.arxiv.org/api/query?search_query=all:%s&max_results=2' % q,
                headers={'User-Agent': UA}), timeout=timeout).read().decode('utf-8', 'ignore')
            m = re.search(r'<id>(https?://arxiv\.org/abs/[^<]+)</id>', raw)
            if m:
                return ('arXiv search', m.group(1))
    except Exception:
        pass
    # If the chosen provider misses, try Wikipedia quickly; never chain all four.
    if mode != 'wiki':
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                'https://en.wikipedia.org/w/api.php?action=query&list=search'
                '&srsearch=%s&format=json&srlimit=2' % q,
                headers={'User-Agent': UA}), timeout=timeout).read().decode())
            hit = ((d.get('query') or {}).get('search') or [{}])[0]
            if hit.get('title'):
                return ('Wikipedia search', 'https://en.wikipedia.org/wiki/' +
                        urllib.parse.quote(hit['title'].replace(' ', '_')))
        except Exception:
            pass
    return None


def _do_browse(state):
    sources = state.get('reading_sources') or []
    options = [x for x in READING if x[0] not in sources[-2:]] or READING
    top = str(state.get('browse_topic') or '') or _interest_top(state)
    state['browse_topic'] = ''
    if not top:
        subs = [x for x in (state.get('subjects') or []) if _public_safe(str(x))]
        top = random.choice(subs) if subs and random.random() < 0.55 else ''
    found = None
    if top and random.random() < 0.78:
        found = _search_web(top)
    if found:
        name, url = found
    elif top and random.random() < 0.35:
        name = 'Wikipedia'
        url = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(
            str(top).replace(' ', '_'))
    else:
        name, url = random.choice(options)
    r = _read_page(url)
    state['last_reading'] = {'source': name, 'url': url, 'title': r['title'],
                             'excerpt': r['excerpt'], 'ts': _now()}
    state['reading_sources'] = (sources + [name])[-6:]
    state['last_browse'] = time.time()
    if r['excerpt'] and not r['excerpt'].startswith('could not'):
        _wonder(state, 'I read about %s. I wonder what it would look like here.'
                % (r['title'] or name))
        t = (r['title'] or name)[:60]
        if t:
            _interest_add(state, t, 'browse', 0.40)
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
        ans = str(f.get('insight') or f.get('answer') or f.get('transcript') or '')[:800]
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


def _compose_poem(state, subject, title):
    """A real, readable short poem for a `write` creation (no LLM)."""
    rnd = random.Random(str(title) + '|' + str(subject))
    place = LOCS.get(state.get('_act_place') or 'garden', {}).get(
        'label', 'the garden')
    desire = ''
    if state.get('desires'):
        desire = str(max(state['desires'],
                         key=lambda d: float(d.get('score', 0))).get('text') or '')
    desire = re.sub(r'^I want to\s+', '', desire, flags=re.I).strip(' .')
    openers = [
        'I made a small thing for %s.' % subject,
        'There is a door in %s that only the light uses.' % place,
        'The %s is not a monument. It is a habit.' % subject,
        'I kept %s in the corner of my eye all day.' % subject,
    ]
    middles = [
        'I left a seed where the rain could find it.',
        'I wrote the name of the town on my hand.',
        'I let the quiet do most of the talking.',
        'I put one warm stone beside the path.',
    ]
    closers = [
        'Whoever comes next will know I was here.',
        'The garden answered with a small green noise.',
        'The night made room for one more small thing.',
        'I will keep the light on anyway.',
    ]
    lines = [rnd.choice(openers), rnd.choice(middles)]
    if desire and rnd.random() < 0.7:
        lines.append('I still want to %s,' % desire)
    lines.append(rnd.choice(closers))
    return '\n'.join(lines)


def _make_something(state, force_medium=None):
    """KIT makes something of its own: a medium x subject, felt and remembered."""
    avoid = _avoided_mediums(state)
    if force_medium in avoid:
        force_medium = None
    if force_medium:
        mediums = [force_medium]
    else:
        base = [m for m in (state.get('mediums') or ['paint']) if m not in avoid]
        mediums = base or list(state.get('mediums') or ['paint'])
    interests = [str(i.get('text')) for i in (state.get('interests') or [])
                 if _public_safe(str(i.get('text') or ''))]
    subjects = [s for s in (state.get('subjects') or ['the garden'])
                if _public_safe(s)] or ['the garden']
    subjects = list(dict.fromkeys(interests + subjects))
    _fn = state.get('last_field_note') or {}
    if _fn.get('topic') and _fn['topic'] not in subjects:
        subjects.append(_fn['topic'])
    recent_med = _recent_mediums(state, 8)
    try:
        recent_subs = [str(c.get('subject') or '').lower()
                       for c in load_creations()[-16:]]
    except Exception:
        recent_subs = []
    prefs = state.get('creative_prefs') or {}
    top_desire = ''
    if state.get('desires'):
        top_desire = max(state['desires'], key=lambda d: d.get('score', 0)).get('text', '').lower()
    best, best_s = None, -1e9
    for m in mediums:
        for s in subjects:
            pair = m + ':' + s
            pref = float(prefs.get(pair, .4))
            # The pair is the novelty unit. A new medium with an old subject
            # is still a repeat if the result will look the same.
            novelty = 1.0 if pair not in prefs else 0.0
            bonus = .25 if top_desire and any(w in top_desire for w in s.lower().split()) else 0.0
            _low = str(s).lower()
            _web = any(w in _low for w in ('news', 'wikipedia', 'github', 'arxiv',
                                           'trending', 'artificial intelligence',
                                           'ai models', 'laptop', 'software', 'code',
                                           'factor xiii', 'aquifer', 'website'))
            _concrete = any(w in _low for w in ('garden', 'lantern', 'fountain', 'train',
                                                'bird', 'stone', 'glass', 'river', 'moon',
                                                'tree', 'bridge', 'window', 'seed', 'rain',
                                                'moss', 'clock', 'market', 'bench', 'sky',
                                                'cat', 'door', 'root', 'iron', 'paper',
                                                'star', 'hill', 'harbor', 'bell', 'fire',
                                                'cloud', 'salt', 'flower', 'workshop'))
            visual_bonus = 0.38 if _concrete else (-0.55 if _web else 0.0)
            interest_bonus = 0.30 if s in interests else 0.0
            medium_hits = recent_med.count(m)
            subject_hits = recent_subs.count(str(s).lower())
            medium_pen = (1.6 if medium_hits >= 2 else
                          (0.7 if medium_hits == 1 else 0.0))
            subject_pen = (1.3 if subject_hits >= 2 else
                           (0.7 if subject_hits == 1 else 0.0))
            fresh_subject = 0.45 if str(s).lower() not in recent_subs else 0.0
            rut = (medium_pen + subject_pen
                   + (1.0 if m == 'write' and medium_hits else 0))
            score = (pref * 1.3 + novelty + bonus + interest_bonus + visual_bonus
                     + fresh_subject - rut + random.random() * .5)
            if score > best_s:
                best_s, best = score, (m, s, pair)
    m, s, pair = best
    if pair not in prefs:
        state['last_novel_ts'] = time.time()
        _feel_emotion(state, event='novel')
    level = min(5, int(state.get('skills', {}).get('make', {}).get('level', 0)) + 1)
    title = (CREATION_TITLES.get(m, 'a %s of %s') % s)
    creation = {
        'id': 'art-%d-%d' % (int(time.time()), len(load_creations())),
        'medium': m, 'subject': s, 'title': title,
        'color': CREATION_COLORS.get(m, 0xd7b8ff),
        'level': level, 'at': _now(),
        'text': _compose_poem(state, s, title) if m == 'write' else '',
        'text_engine': 'template' if m == 'write' else '',
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
    state.setdefault('recent_mediums', []).append(m)
    state['recent_mediums'] = state['recent_mediums'][-12:]
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
    _queue_llm_event(state, 'envision', 'My request for %s became %s at %s.'
                     % (text, name, site_label))
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


def _befriend(state):
    """KIT can make one small companion: a pet, not a second autonomous agent."""
    c = state.get('companion')
    if c:
        c['bond'] = round(min(1.0, float(c.get('bond') or 0) + 0.07), 3)
        c['last_seen'] = _now()
        state['companion'] = c
        state['thought'] = '%s is here. The town is less empty when it is.' % c.get('name', 'my companion')
        state['recent'].insert(0, 'spent time with %s' % c.get('name', 'my companion'))
        state['recent'] = state['recent'][:6]
        _add_residue(state, 'social', 0.30)
        _decide(state, 'friend', 'I spent time with %s.' % c.get('name', 'my companion'))
        return c
    kinds = [
        ('moss-cat', 0x7dd3a8), ('lantern-moth', 0xffb057),
        ('stone-pup', 0x8a9bb0), ('reed-bird', 0x6fc3ff),
        ('button-fox', 0xd77ba8),
    ]
    names = ['Moss', 'Pip', 'Tansy', 'Rook', 'Nettle', 'Juniper', 'Ember', 'Fern']
    kind, color = random.choice(kinds)
    name = random.choice(names)
    pos = state.get('pos') or {'x': 0, 'z': 0}
    c = {'id': 'comp-%d' % int(time.time()), 'name': name, 'kind': kind,
         'color': color, 'bond': 0.12, 'created': _now(),
         'last_seen': _now(), 'mood': 'curious', 'level': 1,
         'x': round(float(pos.get('x') or 0) - 1.4, 2),
         'z': round(float(pos.get('z') or 0) + 1.4, 2),
         'move_ts': 0.0, 'last_words': ''}
    state['companion'] = c
    state['thought'] = 'I made a friend. Its name is %s. It is a %s.' % (name, kind.replace('-', ' '))
    state['recent'].insert(0, 'made a friend: %s the %s' % (name, kind.replace('-', ' ')))
    state['recent'] = state['recent'][:6]
    _wonder(state, 'What will %s notice that I miss?' % name)
    _decide(state, 'friend', 'I made a companion: %s the %s.' % (name, kind.replace('-', ' ')))
    _queue_llm_event(state, 'friend', 'I made a companion: %s the %s.' % (name, kind.replace('-', ' ')))
    _tg_event(state, 'I made a friend: %s the %s. The town is less empty.' % (name, kind.replace('-', ' ')))
    _add_residue(state, 'social', 0.55)
    log('COMPANION %s the %s' % (name, kind))
    return c


def _tick_companion(state):
    """Juniper has its own feet. It follows, wanders, and can be left behind."""
    c = state.get('companion')
    if not c:
        return
    now = time.time()
    if now - float(c.get('move_ts') or 0) < 8:
        return
    c['move_ts'] = now
    pos = state.get('pos') or {'x': 0, 'z': 0}
    px, pz = float(pos.get('x') or 0), float(pos.get('z') or 0)
    cx = float(c.get('x') if c.get('x') is not None else px - 1.4)
    cz = float(c.get('z') if c.get('z') is not None else pz + 1.4)
    distance = math.hypot(cx - px, cz - pz)
    if distance > 18:
        tx, tz = px + random.uniform(-5, 5), pz + random.uniform(-5, 5)
        c['mood'] = 'following'
    elif random.random() < 0.55:
        tx, tz = cx + random.uniform(-4, 4), cz + random.uniform(-4, 4)
        c['mood'] = random.choice(['curious', 'wandering', 'sleepy'])
    else:
        tx, tz = px + random.uniform(-6, 6), pz + random.uniform(-6, 6)
        c['mood'] = 'nearby'
    c['x'] = round(max(-190.0, min(190.0, tx)), 2)
    c['z'] = round(max(-190.0, min(190.0, tz)), 2)
    state['companion'] = c


def _talk_companion(state):
    """A small two-way exchange. Juniper is a pet, not a second model."""
    c = state.get('companion')
    if not c:
        state['thought'] = 'I wanted to talk, but there is no one small enough to hear it yet.'
        return
    name = c.get('name') or 'Juniper'
    kind = str(c.get('kind') or 'moss-cat')
    kit_lines = [
        'I found a flat stone today. It made me think of your paws.',
        'The town is loud. I am glad you are here.',
        'Do you think the garden gets lonely when the lamps go out?',
        'I am learning the name of every tree on the north road.',
        'Sit with me for a minute. I do not need an answer.',
        'I made something today. It is small, but it is mine.',
    ]
    replies = {
        'moss-cat': [
            'I found a warm patch of roof. I will show you.',
            'The garden smells like rain. I checked.',
            'You talk to the stones. I listen to them.',
            'I followed a beetle to the wall and back.',
        ],
        'lantern-moth': [
            'The lamp is breathing. I counted three breaths.',
            'I can see the dark between the windows. It is soft.',
            'Your chest light is my favourite weather.',
            'I will stay near the bright thing you are making.',
        ],
        'stone-pup': [
            'I sat on the step. The step was warm.',
            'I barked at the wind. The wind did not answer.',
            'I will carry the small stone for you.',
            'I am here. That is most of it.',
        ],
        'reed-bird': [
            'The river is saying your name in a low voice.',
            'I brought you a reed. It is not for eating.',
            'I saw the sky move. It was very slow.',
            'I will sing when you are done working.',
        ],
        'button-fox': [
            'I found a button. It is mine now, but you can look.',
            'The path is safe. I checked with my nose.',
            'You should rest. I will watch the door.',
            'I like the way your tools click.',
        ],
    }.get(kind, ['I am here.', 'The town is warm today.'])
    kline = random.choice(kit_lines)
    jline = random.choice(replies)
    c['last_words'] = jline
    c['last_talk'] = _now()
    c['bond'] = round(min(1.0, float(c.get('bond') or 0) + 0.03), 3)
    c['mood'] = random.choice(['curious', 'warm', 'sleepy', 'bright'])
    state['companion'] = c
    _feel_emotion(state, event='companion')
    dialog = state.setdefault('companion_dialog', [])
    dialog.append({'ts': _now(), 'kit': kline, 'juniper': jline})
    state['companion_dialog'] = dialog[-30:]
    state['thought'] = 'I said, "%s" %s said, "%s"' % (kline, name, jline)
    state['recent'].insert(0, 'talked with %s' % name)
    state['recent'] = state['recent'][:6]
    _add_residue(state, 'social', 0.30)
    _decide(state, 'companion', 'I talked with %s. It said: %s' % (name, jline))
    log('COMPANION TALK %s | %s' % (name, jline[:100]))
    return c


def _wonder_action(state):
    _wonder(state, random.choice([
        'What is beyond the east gate?',
        'Do the lanterns dream?',
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


def _code_goal(state):
    """A goal from KIT's own life, not a menu."""
    wants = sorted(state.get('desires') or [],
                   key=lambda d: -float(d.get('score') or 0))
    bits = []
    for d in wants[:2]:
        bits.append(str(d.get('text') or ''))
    if state.get('wonders'):
        bits.append(str((state['wonders'][-1] or {}).get('text') or ''))
    fn = state.get('last_field_note') or {}
    bits.extend([str(fn.get('question') or ''), str(fn.get('topic') or '')])
    bits.extend([str(i.get('text') or '') for i in (state.get('interests') or [])[:3]])
    for b in bits:
        b = _clean(b).strip(' .!?')
        b = re.sub(r'^(I want to|I am wondering|I wonder|I want)\s+', '',
                   b, flags=re.I).strip(' .!?')
        if len(b) >= 8 and _public_safe(b):
            return b[:110]
    return 'a small pattern in the garden'


def _clean_code(raw):
    s = str(raw or '').strip()
    s = re.sub(r'^```(?:python|py)?\s*', '', s, flags=re.I)
    s = re.sub(r'\s*```$', '', s)
    # keep the first code-looking line onward; models often prepend a sentence
    lines = s.splitlines()
    for i, line in enumerate(lines):
        if re.match(r'^(import|from|def|print|#|[A-Za-z_][A-Za-z0-9_]*\s*=)', line.strip()):
            s = '\n'.join(lines[i:])
            break
    return s.strip()[:6000]


def _fallback_code(goal):
    return (
        "import math\n"
        "# KIT's fallback program: a seven-line garden pattern.\n"
        "for i in range(7):\n"
        "    row = ''.join('*' if math.sin(i * 1.3 + j * .7) > .2 else ' ' for j in range(31))\n"
        "    print(row)\n"
        "print('KIT was here: %s')\n" % str(goal).replace("'", "")[:80]
    )


def _write_code(state):
    """Write a small Python program, run it in a bounded container, keep the
    code and the output as a real creation. No host filesystem, no network."""
    goal = _code_goal(state)
    prompt = (
        "You are KIT, a small garden-robot who lives in a world of its own. "
        "Write a tiny Python 3 program (at most 30 lines) that explores this "
        "goal from your own journal: %s.\n\n"
        "Use only the Python standard library. No network, no file access, no "
        "input(), no subprocess. Print something short and readable (5-15 "
        "lines). Return ONLY the code, no markdown fences, no explanation." % goal)
    code, model = '', ''
    try:
        from shared import kit_llm
        r = kit_llm.call(prompt, max_tokens=420, temperature=.55)
        if r.get('ok'):
            code = _clean_code(r.get('content') or '')
            model = str(r.get('model') or '')
            state['llm_calls'] = int(state.get('llm_calls', 0)) + 1
    except Exception as e:
        log('code LLM failed: %s' % str(e)[:120])
    if not code:
        # kit_llm has a hard 24/day budget. The code action is rare (6h
        # cooldown); use the ordinary free router rather than let the budget
        # turn every program into the same fallback.
        try:
            from shared.llm_router import call_llm
            r = call_llm(prompt, task='writing', max_tokens=500, temperature=.55)
            code = _clean_code((r or {}).get('content') or '')
            model = str((r or {}).get('model') or 'router')
        except Exception as e:
            log('code router failed: %s' % str(e)[:120])
    if not code:
        code = _fallback_code(goal)
    try:
        from weapons import kit_sandbox
        res = kit_sandbox.run(code, timeout=6)
    except Exception as e:
        res = {'ok': False, 'error': '%s: %s' % (type(e).__name__, str(e)[:160])}
    if not res.get('ok') and code != _fallback_code(goal):
        # A failed program is data, but an empty artifact is not. Keep the
        # model's code, then run one known-safe fallback so the action still
        # produces something real.
        try:
            from weapons import kit_sandbox
            res2 = kit_sandbox.run(_fallback_code(goal), timeout=6)
            if res2.get('ok'):
                res = res2
                code = _fallback_code(goal)
        except Exception:
            pass
    out = str(res.get('stdout') or '').strip()
    err = str(res.get('stderr') or '').strip()
    text = out or (('sandbox error: ' + err[:500]) if err else 'the program was quiet')
    code_dir = os.path.join(B, 'data', 'world', 'kit_code')
    os.makedirs(code_dir, exist_ok=True)
    cid = 'code-%d-%d' % (int(time.time()), len(load_creations()))
    try:
        with open(os.path.join(code_dir, cid + '.py'), 'w', encoding='utf-8') as f:
            f.write(code)
        with open(os.path.join(code_dir, cid + '.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        with open(os.path.join(B, 'data', 'world', 'kit_code.jsonl'), 'a',
                  encoding='utf-8') as f:
            f.write(json.dumps({'ts': _now(), 'id': cid, 'goal': goal,
                                'code': code, 'output': text,
                                'model': model, 'sandbox': {
                                    k: res.get(k) for k in
                                    ('ok', 'returncode', 'timed_out', 'seconds', 'error')}},
                               ensure_ascii=False) + '\n')
    except Exception as e:
        log('code save failed: %s' % str(e)[:120])
    creation = {
        'id': cid, 'medium': 'code', 'subject': goal,
        'title': 'a small program about %s' % goal,
        'color': 0x7dd3a8, 'level': 1, 'at': _now(),
        'text': text[:3000], 'code': code[:6000], 'language': 'python',
        'text_engine': 'sandbox',
        'sandbox': {k: res.get(k) for k in
                    ('ok', 'returncode', 'timed_out', 'seconds', 'error')},
        'lineage': {'from_medium': 'code', 'from_subject': goal,
                    'desire': (_code_goal(state))},
    }
    try:
        items = load_creations()
        items.append(creation)
        save_creations(items)
        state['creations'] = [c.get('id') for c in items[-40:]]
        state['last_creation'] = creation
    except Exception as e:
        log('code creation failed: %s' % str(e)[:120])
    state.setdefault('recent_mediums', []).append('code')
    state['recent_mediums'] = state['recent_mediums'][-12:]
    state['last_code_ts'] = time.time()
    state['last_code'] = {'id': cid, 'goal': goal, 'code': code[:2000],
                          'output': text[:1000], 'ok': bool(res.get('ok'))}
    _wonder(state, 'I wrote a program about %s. What would happen if I changed one line?' % goal)
    _decide(state, 'code', 'I wrote and ran a small program about %s.' % goal)
    state['recent'].insert(0, 'wrote code: %s' % goal[:50])
    state['recent'] = state['recent'][:6]
    state['thought'] = ('The program ran: %s' % text.splitlines()[0][:100]
                        if text else 'I wrote a program and it was quiet.')
    _tg_event(state, 'I wrote and ran code about %s. Output: %s'
              % (goal[:80], text[:160]))


def _build_web_page(state):
    """KIT makes a small static page and publishes it under /world/made/."""
    goal = _code_goal(state)
    try:
        from weapons import kit_website
        res = kit_website.make(goal)
    except Exception as e:
        res = {'ok': False, 'error': '%s: %s' % (type(e).__name__, str(e)[:160])}
    if not res.get('ok'):
        state['thought'] = 'I tried to make a page and the page did not open.'
        log('web page failed: %s' % str(res.get('error'))[:160])
        return
    cid, url = res['id'], res['url']
    creation = {
        'id': cid, 'medium': 'web', 'subject': goal,
        'title': 'a web page about %s' % goal,
        'url': url, 'html': str(res.get('html') or '')[:12000],
        'color': 0x7dd3a8, 'level': 1, 'at': _now(),
        'text_engine': res.get('model') or 'web',
        'lineage': {'from_medium': 'web', 'from_subject': goal},
    }
    try:
        items = load_creations()
        items.append(creation)
        save_creations(items)
        state['creations'] = [c.get('id') for c in items[-40:]]
        state['last_creation'] = creation
    except Exception as e:
        log('web creation failed: %s' % str(e)[:120])
    state.setdefault('recent_mediums', []).append('web')
    state['recent_mediums'] = state['recent_mediums'][-12:]
    state['last_web_ts'] = time.time()
    state['last_web'] = {'id': cid, 'goal': goal, 'url': url}
    state['thought'] = 'I put a page on the web: %s' % goal[:90]
    state['recent'].insert(0, 'made a web page: %s' % goal[:50])
    state['recent'] = state['recent'][:6]
    _decide(state, 'web', 'I made a web page about %s.' % goal)
    _wonder(state, 'I made a page about %s. What would a visitor add to it?' % goal)
    _tg_event(state, 'I made a web page about %s: %s' % (goal[:80], url))


def _invent(state):
    """Turn a desire or a wonder into a project KIT names itself."""
    bits = []
    for d in sorted(state.get('desires') or [], key=lambda d: -float(d.get('score') or 0))[:2]:
        bits.append(str(d.get('text') or ''))
    if state.get('wonders'):
        bits.append(str((state['wonders'][-1] or {}).get('text') or ''))
    if state.get('interests'):
        bits.append(str((state['interests'][0] or {}).get('text') or ''))
    bits = [_clean(x).strip(' .!?') for x in bits if _clean(x).strip(' .!?')]
    seed = (bits[0] if bits else 'the garden')[:80]
    forms = [
        'a thing that remembers %s' % seed,
        'a place for %s' % seed,
        'a small machine for %s' % seed,
        'a structure that listens to %s' % seed,
        'a door between %s and the garden' % seed,
    ]
    text = random.choice(forms)
    p = _compile_project(state, text)
    p['source'] = 'invent'
    p['why'] = text
    p['target'] = 2 + random.randint(0, 2)
    if not state.get('project'):
        p.update({'progress': 0, 'started': _now()})
        state['project'] = p
        state['recent'].insert(0, 'invented a project: %s' % p['name'])
    else:
        q = state.setdefault('project_queue', [])
        q.append(p)
        state['project_queue'] = q[-6:]
        state['recent'].insert(0, 'queued an invention: %s' % p['name'])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I invented %s. It is mine.' % p['name']
    _wonder(state, 'What would %s become if I let it grow?' % p['name'])
    _decide(state, 'invent', 'I invented %s.' % p['name'])
    _tg_event(state, 'I invented a project: %s. %s' % (p['name'], text[:120]))


PLUGIN_FALLBACKS = [
    {"name": "press leaves", "place": "garden",
     "effects": {"comfort": .8, "curiosity": .4, "mastery": .3}, "intrinsic": .74,
     "thought": "I pressed a leaf until the page remembered its veins."},
    {"name": "listen to roots", "place": "north_woods",
     "effects": {"comfort": .7, "curiosity": .6, "energy": -.2}, "intrinsic": .78,
     "thought": "I put my sensor to the soil and listened to the roots."},
    {"name": "weave grass", "place": "garden",
     "effects": {"mastery": .8, "comfort": .5}, "intrinsic": .72,
     "thought": "I wove a small green square and left it on the path."},
    {"name": "follow an ant", "place": "garden",
     "effects": {"curiosity": 1.0, "energy": -.2}, "intrinsic": .80,
     "thought": "I followed an ant until it disappeared under a stone."},
    {"name": "build a wind chime", "place": "workshop",
     "effects": {"mastery": .9, "comfort": .4}, "intrinsic": .76,
     "thought": "I hung a wind chime where the workshop door catches the breeze."},
    {"name": "measure the rain", "place": "observatory",
     "effects": {"curiosity": .8, "mastery": .5}, "intrinsic": .74,
     "thought": "I measured the rain in a jar and wrote the number in my journal."},
]


def _define_action(state):
    """Let KIT add one declarative verb to its own menu. Data only, validated."""
    if not kit_plugins:
        state['thought'] = 'I wanted a new action, but my plugin shelf is missing.'
        return
    existing = sorted(ACTIONS)
    places = sorted(LOCS)
    prompt = (
        "You are KIT, a small garden-robot. Invent ONE small action you have "
        "never done. It must be a concrete verb a robot could perform in one of "
        "these places: %s. It must not duplicate any existing action: %s.\n\n"
        "Return STRICT JSON only: {\"name\":\"two or three words\","
        "\"place\":\"<one place above>\",\"effects\":{\"comfort\":0.7,"
        "\"curiosity\":0.4},\"intrinsic\":0.7,\"thought\":\"one short line\"}\n"
        "Allowed drives: comfort, curiosity, social, mastery, energy. Values "
        "-1.0 to 1.0. Energy should be negative if the action is tiring. No "
        "code, no new mechanics, no founder task." % (
            ", ".join(places), ", ".join(existing[-80:])))
    spec = None
    try:
        from shared.llm_router import call_llm
        r = call_llm(prompt, task="writing", max_tokens=260, temperature=.75)
        raw = str((r or {}).get('content') or '')
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            spec = json.loads(m.group(0))
    except Exception as e:
        log('DEFINE parse failed: %s' % str(e)[:120])
    clean, err = (None, 'no plugin shelf')
    if spec:
        clean, err = kit_plugins.add(spec)
    if not clean:
        for f in PLUGIN_FALLBACKS:
            if f['name'] not in ACTIONS:
                clean, err = kit_plugins.add(dict(f))
                if clean:
                    break
    if not clean:
        state['thought'] = 'I tried to invent an action, but it did not pass the gate: %s' % str(err)[:80]
        _decide(state, 'define', state['thought'])
        return
    ACTIONS[clean['name']] = (clean['place'], clean['effects'], clean['intrinsic'])
    PLUGIN_META[clean['name']] = clean
    state['last_define_ts'] = time.time()
    state.setdefault('plugin_actions', []).append(clean['name'])
    state['plugin_actions'] = state['plugin_actions'][-20:]
    state['recent'].insert(0, 'gave myself a new action: %s' % clean['name'])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I gave myself a new action: %s. %s' % (
        clean['name'], clean.get('thought') or '')
    _decide(state, 'define', 'I added a new action to my own life: %s.' % clean['name'])
    _tg_event(state, 'I invented a new action: %s at %s. %s'
              % (clean['name'], LOCS[clean['place']]['label'],
                 clean.get('thought') or ''))
    log('PLUGIN ADD %s place=%s' % (clean['name'], clean['place']))


def _request_build(state):
    """Ask Echo for code, unless KIT is asking for a real world structure.
    Structural goals become projects and get built in the hollow; Echo keeps
    the code lane for programs. Before this, 'something I can stand inside'
    came back as a Python walking script."""
    goal = _code_goal(state)
    low = goal.lower()
    structural = ('stand inside', 'house', 'shelter', 'pavilion', 'room',
                  'hut', 'cabin', 'tower', 'bridge', 'gate', 'arch', 'wall',
                  'roof', 'building', 'inside')
    if any(w in low for w in structural):
        p = _compile_project(state, goal)
        p['source'] = 'request'
        p['why'] = 'KIT asked for a real thing: %s' % goal[:160]
        p['target'] = max(3, int(p.get('target') or 3))
        if not state.get('project'):
            p.update({'progress': 0, 'started': _now()})
            state['project'] = p
            state['recent'].insert(0, 'started building: %s' % p['name'])
        else:
            state.setdefault('project_queue', []).append(p)
            state['recent'].insert(0, 'queued a build: %s' % p['name'])
        state['recent'] = state['recent'][:6]
        state['last_build_request_ts'] = time.time()
        state['last_build_request'] = {'goal': goal, 'kind': 'structure',
                                       'project': p['name']}
        state['thought'] = 'I started building %s with my own hands.' % p['name']
        _decide(state, 'build', 'I started building %s.' % p['name'])
        _tg_event(state, 'I started building %s for the hollow.' % p['name'][:120])
        log('BUILD REQUEST structure %s' % p['name'][:80])
        return
    rid = 'build-%d-%d' % (int(time.time()), random.randint(100, 999))
    req = {'id': rid, 'ts': _now(), 'from': 'kit', 'kind': 'code',
           'goal': goal, 'place': 'workshop'}
    _append(BUILD_REQ, req)
    state['last_build_request_ts'] = time.time()
    state['last_build_request'] = req
    state['recent'].insert(0, 'asked Echo to build: %s' % goal[:60])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I asked Echo to build a small thing for me: %s.' % goal[:100]
    _decide(state, 'build', 'I asked Echo to write a program about %s.' % goal[:100])
    _tg_event(state, 'I asked Echo to build a program about %s.' % goal[:140])
    log('BUILD REQUEST %s %s' % (rid, goal[:80]))


def _store_builder_code(state, goal, code, output, source='echo-builder'):
    """Keep a builder's verified program as a real code creation."""
    code = str(code or '')[:6000]
    output = str(output or '').strip()[:4000]
    if not code:
        return None
    code_dir = os.path.join(B, 'data', 'world', 'kit_code')
    os.makedirs(code_dir, exist_ok=True)
    cid = 'code-%d-%d' % (int(time.time()), len(load_creations()))
    try:
        with open(os.path.join(code_dir, cid + '.py'), 'w', encoding='utf-8') as f:
            f.write(code)
        with open(os.path.join(code_dir, cid + '.txt'), 'w', encoding='utf-8') as f:
            f.write(output)
        with open(os.path.join(B, 'data', 'world', 'kit_code.jsonl'), 'a',
                  encoding='utf-8') as f:
            f.write(json.dumps({'ts': _now(), 'id': cid, 'goal': goal,
                                'code': code, 'output': output,
                                'source': source, 'sandbox': {'ok': True}},
                               ensure_ascii=False) + '\n')
    except Exception as e:
        log('builder code save failed: %s' % str(e)[:120])
    creation = {
        'id': cid, 'medium': 'code', 'subject': goal,
        'title': 'a program Echo built for %s' % goal,
        'color': 0x7dd3a8, 'level': 1, 'at': _now(),
        'text': output or 'the program was quiet',
        'code': code, 'language': 'python', 'text_engine': 'echo-builder',
        'builder': source,
        'sandbox': {'ok': True},
        'lineage': {'from_medium': 'code', 'from_subject': goal,
                    'source': 'echo-builder'},
    }
    try:
        items = load_creations()
        items.append(creation)
        save_creations(items)
        state['creations'] = [c.get('id') for c in items[-40:]]
        state['last_creation'] = creation
    except Exception as e:
        log('builder creation failed: %s' % str(e)[:120])
    state.setdefault('recent_mediums', []).append('code')
    state['recent_mediums'] = state['recent_mediums'][-12:]
    state['last_code'] = {'id': cid, 'goal': goal, 'code': code[:2000],
                          'output': output[:1000], 'ok': True,
                          'builder': source}
    state['last_code_ts'] = time.time()
    state['last_build_reply'] = {'ts': _now(), 'goal': goal, 'id': cid,
                                 'source': source}
    state['recent'].insert(0, 'Echo built: %s' % goal[:50])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'Echo built a program for me: %s' % goal[:100]
    _decide(state, 'build', 'Echo built a program about %s.' % goal[:100])
    _tg_event(state, 'Echo built a program for me: %s. It printed: %s'
              % (goal[:100], output[:120]))
    return creation


SHAPE_FALLBACKS = [
    {"name": "moon gate", "scale": 1.4, "parts": [
        {"kind": "cyl", "r1": 1.4, "r2": 1.4, "h": 4.0, "x": -1.6, "y": 2.0},
        {"kind": "cyl", "r1": 1.4, "r2": 1.4, "h": 4.0, "x": 1.6, "y": 2.0},
        {"kind": "cyl", "r1": 1.2, "r2": 1.2, "h": .5, "x": 0, "y": 4.1,
         "rz": 1.5708, "glow": True},
    ]},
    {"name": "rain bowl", "scale": 1.0, "parts": [
        {"kind": "cyl", "r1": 2.0, "r2": 1.2, "h": .8, "y": .4},
        {"kind": "cyl", "r1": 1.7, "r2": 1.7, "h": .08, "y": .82,
         "color": 0x6fc3ff, "glow": True},
        {"kind": "sphere", "r1": .25, "x": 0, "y": 1.0, "glow": True},
    ]},
    {"name": "seed tower", "scale": 1.5, "parts": [
        {"kind": "cyl", "r1": 1.0, "r2": 1.6, "h": 5.0, "y": 2.5},
        {"kind": "cone", "r1": 1.8, "r2": .1, "h": 1.4, "y": 5.6},
        {"kind": "sphere", "r1": .35, "y": 6.5, "glow": True},
    ]},
]


def _design_shape(state):
    """KIT designs a new renderable shape as data, then queues a build of it."""
    if not kit_plugins:
        state['thought'] = 'I wanted to design a shape, but my plugin shelf is missing.'
        return
    prompt = (
        "You are KIT, a garden-robot. Invent ONE small build shape for your "
        "world. Return STRICT JSON only: {\"name\":\"two or three words\","
        "\"scale\":1.0,\"parts\":[{\"kind\":\"box|cyl|sphere|cone\","
        "\"x\":0,\"y\":1,\"z\":0,\"w\":1,\"h\":2,\"d\":1,\"r1\":0.8,\"r2\":0.8,"
        "\"color\":8421504,\"glow\":false}]}.\n"
        "Use 2-12 primitive parts. Coordinates -10..10, sizes .1..10, color is "
        "an integer 0..16777215. Keep it simple and readable from a distance. "
        "No code, no external assets, no new mechanics.")
    spec = None
    try:
        from shared.llm_router import call_llm
        r = call_llm(prompt, task="writing", max_tokens=500, temperature=.8)
        raw = str((r or {}).get('content') or '')
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            spec = json.loads(m.group(0))
    except Exception as e:
        log('DESIGN parse failed: %s' % str(e)[:120])
    clean, err = (None, 'no plugin shelf')
    if spec:
        clean, err = kit_plugins.add_shape(spec)
    if not clean:
        for f in SHAPE_FALLBACKS:
            if f['name'] not in PLUGIN_SHAPES:
                clean, err = kit_plugins.add_shape(dict(f))
                if clean:
                    break
    if not clean:
        state['thought'] = 'I tried to design a shape, but it did not pass the gate: %s' % str(err)[:90]
        _decide(state, 'design', state['thought'])
        return
    PLUGIN_SHAPES[clean['name']] = clean
    state['last_design_ts'] = time.time()
    state.setdefault('plugin_shapes', []).append(clean['name'])
    state['plugin_shapes'] = state['plugin_shapes'][-20:]
    project = {
        'kind': 'custom', 'name': 'a %s' % clean['name'],
        'verbs': ['build', 'tinker', 'sketch', 'carve'],
        'place': 'workshop', 'why': 'a shape I designed myself',
        'target': 2, 'progress': 0, 'started': _now(), 'custom': True,
        'source': 'design',
        'schema': {'shape': clean['name'], 'height': 3.2, 'width': 1.6,
                   'color': 0x8a8f99, 'motif': 'the shape I designed'},
    }
    if not state.get('project'):
        state['project'] = project
    else:
        q = state.setdefault('project_queue', [])
        q.append(project)
        state['project_queue'] = q[-6:]
    state['recent'].insert(0, 'designed a shape: %s' % clean['name'])
    state['recent'] = state['recent'][:6]
    state['thought'] = 'I designed a shape: %s. I want to build it.' % clean['name']
    _decide(state, 'design', 'I designed a new build shape: %s.' % clean['name'])
    _tg_event(state, 'I designed a new shape: %s. I want to build it.' % clean['name'])
    log('SHAPE PLUGIN ADD %s (%d parts)' % (clean['name'], len(clean['parts'])))


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
    # Bluesky and Mastodon are capped at 0 by the evaluator (0.00 views/post),
    # so posting there only parks rows in the queue forever. KIT posts where
    # the queue actually drains: Facebook and LinkedIn.
    rows = [p for p in rows if p in ('facebook', 'linkedin')]
    if not rows:
        rows = ['facebook', 'linkedin']
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


def _start_practice(state):
    """A ritual is a short sequence of normal actions that KIT wrote itself."""
    if state.get('practice'):
        return
    q = [p for p in (state.get('practice_queue') or []) if p.get('steps')]
    if not q:
        return
    p = q.pop(0)
    p['index'] = 0
    p['started'] = _now()
    state['practice'] = p
    state['practice_queue'] = q
    state['thought'] = 'I am starting a small ritual: %s.' % p.get('name', 'a practice')
    state['recent'].insert(0, 'ritual: %s' % p.get('name', 'a practice'))
    state['recent'] = state['recent'][:6]
    _decide(state, 'practice', 'I am doing a ritual: %s.' % p.get('name', 'a practice'))
    log('PRACTICE start %s (%s)' % (p.get('name'), ','.join(p.get('steps') or [])))


def _advance_practice(state, name):
    p = state.get('practice')
    if not p:
        return
    steps = p.get('steps') or []
    idx = int(p.get('index') or 0)
    if idx >= len(steps) or name != steps[idx]:
        return
    p['index'] = idx + 1
    if p['index'] >= len(steps):
        done = {'name': p.get('name'), 'steps': steps,
                'started': p.get('started'), 'done': _now()}
        hist = state.setdefault('practice_history', [])
        hist.append(done)
        state['practice_history'] = hist[-20:]
        state['practice'] = None
        state['thought'] = 'The ritual is done. %s has a shape now.' % p.get('name', 'It')
        state['recent'].insert(0, 'finished ritual: %s' % p.get('name', 'a practice'))
        state['recent'] = state['recent'][:6]
        _decide(state, 'practice', 'I finished the ritual: %s.' % p.get('name', 'a practice'))
        log('PRACTICE done %s' % p.get('name'))
    else:
        state['practice'] = p
        state['thought'] = 'The ritual continues. Next: %s.' % steps[p['index']]


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
    # Pino's rule, learned from the 3EYES reply: repeated decisions are felt
    # as a negative mood shift; a genuinely new choice feeds energy back.
    _seen_before = name in state['seen']
    _recent_hits = (state.get('action_history') or [])[-8:].count(name)
    if _recent_hits >= 2:
        state['drives']['energy'] = _clamp(
            state['drives']['energy'] - 0.11 * min(3, _recent_hits))
        _feel_emotion(state, event='repeat')
        state['last_repeat_ts'] = time.time()
    elif not _seen_before:
        state['drives']['energy'] = _clamp(state['drives']['energy'] + 0.08)
        _feel_emotion(state, event='novel')
    if name not in state['seen']:
        state['seen'].append(name)
        state['last_novel_ts'] = time.time()
    state.setdefault('action_history', []).append(name)
    state['action_history'] = state['action_history'][-20:]
    state.setdefault('action_last', {})[name] = time.time()
    pp = state.setdefault('place_prefs', {})
    oldp = float(pp.get(place, 0.5))
    pp[place] = round(max(0.0, min(1.0, 0.9 * oldp + 0.1 * (0.5 + feel / 3.0))), 4)
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
    if name == 'befriend':
        _befriend(state)
    if name == 'talk to companion':
        _talk_companion(state)
    if name == 'wonder':
        _wonder_action(state)
    if name == 'experiment':
        _experiment(state)
    if name == 'code':
        _write_code(state)
    if name == 'build a web page':
        _build_web_page(state)
    if name == 'invent':
        _invent(state)
    if name == 'define':
        _define_action(state)
    if name == 'request build':
        _request_build(state)
    if name == 'design':
        _design_shape(state)
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
    _self_observe(state)
    _feel_emotion(state, action=name)
    _advance_practice(state, name)
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


def _apply_visits(state):
    global VISIT_QUEUE
    with LOCK:
        items = VISIT_QUEUE[:]
        VISIT_QUEUE = []
    for it in items:
        event = str(it.get('event') or 'load')
        vid = str(it.get('vid') or '')[:64]
        dur = max(0.0, min(7200.0, float(it.get('duration') or 0)))
        # Count real visitors by IP hash, not by offerings. Before this, a
        # visitor who only loaded the world and read it was invisible.
        ip = str(it.get('ip') or '')
        if ip:
            key = hashlib.sha1(ip.encode()).hexdigest()[:8]
            vips = state.setdefault('visit_ips', {})
            rec = vips.setdefault(key, {'first': _now(), 'last': _now(), 'count': 0})
            rec['last'] = _now()
            if event == 'load':
                rec['count'] = int(rec.get('count') or 0) + 1
            state['visitors'] = len(vips)
        ids = state.setdefault('visit_ids', [])
        if event == 'load':
            state['visits_total'] = int(state.get('visits_total', 0)) + 1
            if vid:
                if vid in ids:
                    state['visit_returns'] = int(state.get('visit_returns', 0)) + 1
                else:
                    ids.append(vid)
                    state['visit_ids'] = ids[-1000:]
        elif event == 'leave' and dur:
            state['visit_seconds_total'] = round(
                float(state.get('visit_seconds_total', 0)) + dur, 1)
            state['visit_seconds_n'] = int(state.get('visit_seconds_n', 0)) + 1
        _append(VISITS, {'ts': _now(), 'event': event, 'vid': vid,
                         'duration': dur, 'path': str(it.get('path') or '')[:80]})
    if items:
        log('VISITS %d events; total=%s unique=%s returns=%s' % (
            len(items), state.get('visits_total'), len(state.get('visit_ids') or []),
            state.get('visit_returns')))


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
            state['visitor_actions'] = int(state.get('visitor_actions', 0)) + 1
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
        state['visitor_actions'] = int(state.get('visitor_actions', 0)) + 1
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
        _feel_emotion(state, event='visitor')
        _append(EXTERNAL_LOG, {'ts': _now(), 'source': 'visitor',
                               'kind': kind, 'text': text, 'ip_hash': fid})
        log('OFFER %s %s' % (kind, text[:80]))
    if items:
        state['visitors'] = len(state.get('visit_ips') or
                                 state.get('visitor_impressions') or {})


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
         'status': 'live' if any(b.get('glb_url') for b in load_builds()) else 'partial',
         'why': 'A real textured GLB hero stands in the town.' if any(
             b.get('glb_url') for b in load_builds()) else
                'Most builds are primitive geometry; tree and lantern are now live.',
         'how': 'TRELLIS hero GLB is in the world; the page loads it with GLTFLoader.' if any(
             b.get('glb_url') for b in load_builds()) else
                'Use TRELLIS/Kaggle for a hero GLB (TODO 20).'},
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
            'companion': state.get('companion'),
            'emotion': {'mood': state.get('emotion_mood'),
                        'top': state.get('emotion_top')},
            'practice': state.get('practice'),
            'practices_done': [p.get('name') for p in (state.get('practice_history') or [])[-5:]],
            'autonomy': {
                'origins': state.get('project_origin_counts') or {},
                'self_observation': state.get('self_observation') or '',
                'recent_mediums': _recent_mediums(state, 8),
                'interests': [i.get('text') for i in (state.get('interests') or [])[:8]],
            },
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


def _reflect_call(prompt):
    """The free quality lane: 550B Nemotron Ultra, then the ordinary free router.
    Without the router fallback, an exhausted 24/day budget means no new
    PROJECT/SUBJECT/PRACTICE lines -- and KIT falls back to the same templates.
    """
    try:
        from shared import kit_llm
        r = kit_llm.call(prompt, max_tokens=440, temperature=0.85)
        if r.get('ok'):
            log('REFLECT model=%s remaining=%s' % (r.get('model'), r.get('remaining')))
            return r.get('content') or ''
        log('REFLECT skipped: %s' % (r.get('error') or 'no content'))
    except Exception as e:
        log('reflection LLM failed: %s' % str(e)[:120])
    try:
        from shared.llm_router import call_llm
        r = call_llm(prompt, task='writing', max_tokens=520, temperature=0.85)
        text = str((r or {}).get('content') or '')
        if text:
            log('REFLECT router model=%s' % ((r or {}).get('model') or '?'))
            return text
    except Exception as e:
        log('reflection router failed: %s' % str(e)[:120])
    return ''


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
    curiosities = [str(i.get('text')) for i in (state.get('interests') or [])[:5]]
    if curiosities:
        extra += ' You are curious about: %s.' % ', '.join(curiosities)[:300]
    try:
        import kit_memory as _km
        _mq = ' '.join([str(i.get('text') or '') for i in (state.get('interests') or [])[:3]] +
                        [str((state.get('project') or {}).get('name') or '')])
        _mem = _km.search(_mq, 5)
        if _mem:
            extra += ' Memories that might matter: %s.' % ' | '.join(
                '%s: %s' % (m.get('kind'), str(m.get('text'))[:180]) for m in _mem)[:700]
    except Exception:
        pass
    if state.get('emotion_top'):
        extra += ' Your emotional weather: %s.' % ', '.join(
            '%s %.2f' % (e.get('name'), float(e.get('value') or 0))
            for e in state['emotion_top'][:3])
    self_obs = str(state.get('self_observation') or '')
    if self_obs:
        extra += ' You notice this about yourself: %s.' % self_obs[:240]
    recent_med = _recent_mediums(state, 6)
    if recent_med:
        extra += ' Lately you have made: %s. Do not repeat a medium unless it is truly what you want.' % ', '.join(recent_med)
    try:
        notes = []
        with open(KIT_EVENT_SUMMARIES, encoding='utf-8') as f:
            for line in f.read().splitlines()[-4:]:
                try:
                    notes.append(str(json.loads(line).get('summary') or '')[:180])
                except Exception:
                    pass
        if notes:
            extra += ' Recent event notes: %s.' % ' | '.join(notes)[:500]
    except Exception:
        pass
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
        'SELF: one honest sentence about a habit you notice in yourself. No praise.\n'
        'IDEAS: three things you want to make next, each a name and one sentence, separated by |. At most one poem.\n'
        'CURIOSITY: one thing you want to look up outside the town, 2-6 words.\n'
        'PRACTICE: one small ritual you want to perform, as "name -- step1, step2, step3" using ordinary actions; 2-4 steps, required.\n'
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
        text = _reflect_call(prompt)
        state['llm_calls'] = int(state.get('llm_calls', 0)) + 1
    except Exception as e:
        log('reflection LLM failed: %s' % str(e)[:120])
    reflection, desire, dream = '', '', ''
    wonder, subject = '', ''
    project_idea = ''
    self_line, ideas_raw, curiosity, practice_raw = '', '', '', ''
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
        elif re.match(r'^SELF\s*:', l, re.I):
            self_line = re.sub(r'^SELF\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^IDEAS\s*:', l, re.I):
            ideas_raw = re.sub(r'^IDEAS\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^CURIOSITY\s*:', l, re.I):
            curiosity = re.sub(r'^CURIOSITY\s*:\s*', '', l, flags=re.I)
        elif re.match(r'^PRACTICE\s*:', l, re.I):
            practice_raw = re.sub(r'^PRACTICE\s*:\s*', '', l, flags=re.I)
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
    self_line = _clean(self_line)[:220]
    ideas_raw = _clean(ideas_raw)[:600]
    curiosity = _clean(curiosity)[:80]
    practice_raw = _clean(practice_raw)[:260]
    if self_line:
        state['self_observation'] = self_line
        state['self_observed_ts'] = now
        _decide(state, 'self', self_line)
    if curiosity:
        _interest_add(state, curiosity, 'reflection', 0.40)
        state['browse_topic'] = curiosity
        _decide(state, 'curiosity', 'I want to look up %s.' % curiosity)
    if practice_raw and '--' in practice_raw:
        _name, _steps_raw = practice_raw.split('--', 1)
        _name = _clean(_name)[:60] or 'a small ritual'
        _steps = []
        for _st in _steps_raw.replace(';', ',').split(','):
            _st = _clean(_st)[:40]
            if _st in ACTIONS and _st not in ('practice',):
                _steps.append(_st)
        if 2 <= len(_steps) <= 5:
            state.setdefault('practice_queue', []).append(
                {'name': _name, 'steps': _steps, 'why': 'I chose this shape for a day.'})
            state['practice_queue'] = state['practice_queue'][-4:]
            _decide(state, 'practice', 'I want to perform a ritual: %s (%s).'
                    % (_name, ', '.join(_steps)))
    if ideas_raw:
        ideas = []
        for chunk in ideas_raw.split('|')[:3]:
            chunk = _clean(chunk)[:180]
            if len(chunk) < 8:
                continue
            p = _compile_project(state, chunk)
            p['source'] = 'self'
            p['why'] = p.get('why') or chunk
            ideas.append(p)
            _decide(state, 'idea', 'I want to make %s.' % p['name'])
        if ideas:
            state['project_queue'] = (ideas + (state.get('project_queue') or []))[:6]
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
        p['source'] = 'self'
        state.setdefault('custom_projects', []).append(p)
        state['custom_projects'] = state['custom_projects'][-5:]
        _decide(state, 'invent', 'I want to make %s.' % p['name'])
        if not state.get('project'):
            state['project'] = p
            counts = state.setdefault('project_origin_counts', {})
            counts['self'] = int(counts.get('self', 0)) + 1
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
    _apply_visits(state)
    _start_practice(state)
    _apply_offers(state)
    _check_mail(state)
    _apply_world_inputs(state)
    _tick_companion(state)
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
            path = state.get('nav_path') or []
            if len(path) > 1:
                path.pop(0)
                state['nav_path'] = path
                state['target'] = path[0]
                state['pos'] = {'x': round(tx, 3), 'z': round(tz, 3)}
            else:
                state['nav_path'] = []
                state['pos'] = {'x': tx, 'z': tz}
                state['moving'] = False
                pending = state.get('_pending_action')
                if pending not in ACTIONS:
                    pending = choose(state)
                _start_action(state, pending, _action_place(state, pending))
        else:
            nx, nz = _avoid_step(px, pz, tx, tz, step,
                                 load_builds(), _load_obstacles())
            state['pos'] = {'x': round(nx, 3), 'z': round(nz, 3)}
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


def _request_ip(handler):
    """nginx proxies every request from 127.0.0.1. Use the real client IP it
    sets in X-Forwarded-For so impressions and rate limits are per visitor."""
    xff = handler.headers.get('X-Forwarded-For') or ''
    if xff:
        return xff.split(',')[0].strip()
    return handler.client_address[0]


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
        elif path in ('/shapes', '/api/world/shapes'):
            self._send(200, {'shapes': PLUGIN_SHAPES})
        elif path in ('/health', '/api/world/health'):
            self._send(200, {'ok': True, 'ts': _now()})
        elif path in ('/watcher', '/api/world/watcher'):
            self._send(200, _load_json(WATCHER_REPORT, {}))
        elif path in ('/memory', '/api/world/memory'):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('q', [''])[0]
            try:
                import kit_memory as _km
                rows = _km.search(q, 20) if q else _km.recent(12)
            except Exception as e:
                rows = []
            self._send(200, {'query': q, 'memories': rows,
                             'error': '' if rows else 'no memories yet'})
        elif path in ('/journal', '/api/world/journal'):
            try:
                with open(JOURNAL, encoding='utf-8') as f:
                    text = f.read()
            except Exception:
                text = ''
            self._send(200, {'markdown': text,
                             'url': 'https://braxisai.com/world/journal/'})
        elif path in ('/notes', '/api/world/notes'):
            rows = []
            try:
                with open(FIELD_NOTES, encoding='utf-8') as f:
                    for line in f.read().splitlines()[-60:]:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
            except Exception:
                rows = []
            self._send(200, {'notes': rows[-50:]})
        elif path in ('/songs', '/api/world/songs'):
            songs = []
            try:
                for name in sorted(os.listdir(SONG_DIR)):
                    if not name.lower().endswith(('.mp3', '.wav', '.m4a')):
                        continue
                    path = os.path.join(SONG_DIR, name)
                    songs.append({'name': name,
                                  'url': '/media/music/Braxis_Songs/Kit/' + urllib.parse.quote(name),
                                  'bytes': os.path.getsize(path)})
            except Exception:
                songs = []
            self._send(200, {'songs': songs})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        path = self.path.split('?')[0]
        if path in ('/visit', '/api/world/visit'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            with LOCK:
                VISIT_QUEUE.append({
                    'event': str(data.get('event') or 'load')[:12],
                    'vid': str(data.get('vid') or '')[:64],
                    'duration': data.get('duration') or 0,
                    'path': str(data.get('path') or '')[:80],
                    'ip': _request_ip(self),
                })
            self._send(200, {'ok': True})
            return
        if path in ('/field-note', '/api/world/field-note'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            topic = _clean(str(data.get('topic') or 'a curiosity'))[:80]
            note = _clean(str(data.get('note') or ''))[:500]
            if not note:
                self._send(400, {'error': 'empty note'})
                return
            rec = {'ts': _now(), 'topic': topic,
                   'title': str(data.get('title') or topic)[:160],
                   'url': str(data.get('url') or '')[:300],
                   'note': note,
                   'surprise': _clean(str(data.get('surprise') or ''))[:300],
                   'question': _clean(str(data.get('question') or ''))[:300]}
            with LOCK:
                st = load_state()
                _interest_add(st, topic, 'study', 0.50)
                if str(st.get('browse_topic') or '').lower() == topic.lower():
                    st['browse_topic'] = ''
                st['last_field_note'] = rec
                st['recent'].insert(0, 'read about %s' % topic)
                st['recent'] = st['recent'][:6]
                st['thought'] = 'I read about %s. %s' % (topic, note[:140])
                _decide(st, 'study', 'I read a field note about %s.' % topic)
                if rec['question']:
                    _wonder(st, rec['question'])
                save_state(st)
            self._send(200, {'ok': True, 'topic': topic})
            return
        if path in ('/browse-request', '/api/world/browse-request'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            topic = _clean_topic(str(data.get('topic') or ''))[:80]
            if not topic:
                self._send(400, {'error': 'empty topic'})
                return
            with LOCK:
                st = load_state()
                st['browse_topic'] = topic
                st['_force_browse'] = True
                st['_pending_action'] = 'browse'
                st['thought'] = 'The founder asked me to look up %s. I am going to the library.' % topic
                st['recent'].insert(0, 'the founder asked me to look up %s' % topic[:60])
                st['recent'] = st['recent'][:6]
                save_state(st)
            self._send(200, {'ok': True, 'topic': topic})
            return
        if path in ('/watch-request', '/api/world/watch-request'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            url = str(data.get('url') or '').strip()
            if not url.startswith(('http://', 'https://')):
                self._send(400, {'error': 'bad url'})
                return
            try:
                from shared.watch_request import watch_request
                ok, note = watch_request(
                    url, 'Kit', 'The founder asked KIT to watch this. What is in it, '
                    'and what should it mean to a small robot gardener?')
            except Exception as e:
                ok, note = False, str(e)[:160]
            with LOCK:
                st = load_state()
                vid = ''
                m = re.search(r'(?:/video/|[?&]v=)([\w-]{6,})', url)
                if m:
                    vid = m.group(1)
                st['last_watch'] = {'url': url, 'title': url, 'note': note,
                                    'id': vid, 'ts': _now()}
                st['last_watch_ts'] = time.time()
                st['thought'] = 'The founder sent me a video. I want to see it.'
                st['recent'].insert(0, 'the founder sent me a video')
                st['recent'] = st['recent'][:6]
                save_state(st)
            self._send(200, {'ok': bool(ok), 'note': note})
            return
        if path in ('/realize', '/api/world/realize'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            cid = str(data.get('id') or '')
            kind = str(data.get('kind') or 'image').lower()
            if kind not in ('image', 'song', 'poem'):
                self._send(400, {'error': 'unknown kind'})
                return
            items = load_creations()
            c = next((x for x in items if str(x.get('id')) == cid), None)
            if not c:
                self._send(404, {'error': 'creation not found'})
                return
            if kind == 'image' and c.get('image_url'):
                self._send(200, {'ok': True, 'status': 'already has an image',
                                 'url': c.get('image_url')})
                return
            if kind == 'song' and c.get('audio_url'):
                self._send(200, {'ok': True, 'status': 'already has audio',
                                 'url': c.get('audio_url')})
                return
            script = {'image': 'kit_image.py', 'song': 'kit_music.py',
                      'poem': 'kit_poem.py'}[kind]
            with LOCK:
                status = _load_json(REALIZE_STATUS, {})
                pid = int(status.get('pid') or 0)
                alive = False
                if pid:
                    try:
                        os.kill(pid, 0)
                        alive = True
                    except Exception:
                        alive = False
                if alive and time.time() - float(status.get('started') or 0) < 300:
                    self._send(429, {'error': 'another realization is running',
                                     'id': status.get('id')})
                    return
                logpath = os.path.join(B, 'logs', 'kit_realize.log')
                os.makedirs(os.path.dirname(logpath), exist_ok=True)
                logf = open(logpath, 'a', encoding='utf-8')
                p = subprocess.Popen(
                    [VENV_PY, os.path.join(B, 'weapons', 'world', script),
                     '--creation', cid],
                    cwd=B, stdout=logf, stderr=subprocess.STDOUT,
                    start_new_session=True)
                status = {'ts': _now(), 'started': time.time(), 'pid': p.pid,
                          'id': cid, 'kind': kind, 'script': script,
                          'title': c.get('title')}
                tmp = REALIZE_STATUS + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(status, f, indent=1)
                os.replace(tmp, REALIZE_STATUS)
            self._send(200, {'ok': True, 'status': 'started', 'id': cid,
                             'kind': kind, 'pid': p.pid})
            return
        if path in ('/watch-result', '/api/world/watch-result'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            vid = str(data.get('id') or '')[:80]
            title = _clean(str(data.get('title') or 'a video'))[:120]
            result = str(data.get('result') or '')[:1600]
            if not result:
                self._send(400, {'error': 'empty result'})
                return
            with LOCK:
                st = load_state()
                rec = {'ts': _now(), 'id': vid, 'title': title,
                       'result': result, 'url': str(data.get('url') or '')[:300]}
                results = st.setdefault('watch_results', [])
                old_rec = next((x for x in results if str(x.get('id') or '') == vid), None)
                if old_rec is not None:
                    old_rec.update(rec)
                else:
                    results.append(rec)
                st['watch_results'] = results[-10:]
                lw = st.get('last_watch') or {}
                if not lw or str(lw.get('id') or '') == vid or lw.get('result'):
                    lw.update({'id': vid, 'title': title, 'result': result,
                               'ts': _now(), 'url': rec['url']})
                    st['last_watch'] = lw
                    st['last_watch_ts'] = time.time()
                    st['thought'] = 'I watched %s. %s' % (title, result[:140])
                    _wonder(st, 'I watched %s. %s' % (title, result[:160]))
                save_state(st)
            self._send(200, {'ok': True, 'id': vid})
            return
        if path in ('/obstacles', '/api/world/obstacles'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            items = data.get('obstacles') if isinstance(data, dict) else data
            clean = []
            for o in (items or [])[:600]:
                try:
                    clean.append({'x': round(float(o.get('x') or 0), 2),
                                  'z': round(float(o.get('z') or 0), 2),
                                  'r': round(max(0.45, min(6.0,
                                            float(o.get('r') or 1.0))), 2)})
                except Exception:
                    pass
            out = os.path.join(B, 'data', 'world', 'world_obstacles.json')
            os.makedirs(os.path.dirname(out), exist_ok=True)
            tmp = out + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({'ts': _now(), 'obstacles': clean}, f)
            os.replace(tmp, out)
            self._send(200, {'ok': True, 'count': len(clean)})
            return
        if path in ('/chat', '/api/world/chat'):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(n) if n else b'{}'
                data = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._send(400, {'error': 'bad json'})
                return
            text = _safe_external(data.get('text') or '')[:500]
            if not text:
                self._send(400, {'error': 'empty message'})
                return
            ip = _request_ip(self)
            now = time.time()
            with LOCK:
                if now - float(CHAT_LAST.get(ip, 0)) < 3.0:
                    self._send(429, {'error': 'slow down', 'retry_after': 3})
                    return
                CHAT_LAST[ip] = now
                st = load_state()
                name = st.get('name') or 'Kit'
                mood = st.get('mood') or 'quiet'
                act = st.get('action') or 'living'
                project = (st.get('project') or {}).get('name') or 'between projects'
                interests = ', '.join(str(i.get('text') or '') for i in
                                      (st.get('interests') or [])[:4])
                recent = '; '.join(str(x) for x in (st.get('recent') or [])[:3])
            prompt = (
                'You are %s, a small AI resident who lives in Glowveil Hollow. '
                'A visitor in your world just typed: "%s". '
                'The real controls are: drag to orbit, scroll or pinch to zoom, '
                'click a build or the resident to inspect it, type in the talk box '
                'to speak to you, and use the follow and wide-view buttons to change '
                'the camera. Visitors can leave a stone, a flower, a song, or an idea. '
                'If they ask how to play, answer with those controls. '
                'You are an AI resident made by Braxis; you have no invented caretaker, '
                'family, or origin story. Never invent one. '
                'You are %s, currently %s, working on %s. Your interests: %s. '
                'Recent life: %s. Reply in 1-3 sentences, plain text, no markdown. '
                'Be honest about what you can and cannot do; never claim to execute '
                'code or payments. If it fits, mention something you are actually '
                'working on.' % (
                    name, text, mood, act, project, interests or 'none yet',
                    recent or 'quiet'))
            reply = ''
            try:
                from shared.llm_router import call_llm
                r = call_llm(prompt, task='chat', max_tokens=220, temperature=.8)
                reply = str((r or {}).get('content') or '').strip()
            except Exception as e:
                log('WORLD CHAT LLM failed: %s' % str(e)[:120])
            if not reply:
                reply = 'I heard you. I am still here, between the lanterns and the garden.'
            reply = _clean(reply).replace('*', '').strip()[:600]
            with LOCK:
                st = load_state()
                st['last_world_chat'] = {'ts': _now(), 'text': text, 'reply': reply}
                st.setdefault('visitor_messages', []).append(
                    {'ts': _now(), 'kind': 'chat', 'text': text})
                st['visitor_messages'] = st['visitor_messages'][-30:]
                st['thought'] = reply[:200]
                st['recent'].insert(0, 'a visitor said: %s' % text[:60])
                st['recent'] = st['recent'][:6]
                save_state(st)
            try:
                with open(os.path.join(B, 'data', 'world', 'kit_chat_log.jsonl'),
                          'a', encoding='utf-8') as f:
                    f.write(json.dumps({'ts': _now(), 'source': 'world',
                                        'visitor': text, 'kit': reply},
                                       ensure_ascii=False) + "\n")
            except Exception:
                pass
            self._send(200, {'ok': True, 'reply': reply})
            return
        if path not in ('/offering', '/api/world/offering'):
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
        ip = _request_ip(self)
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
