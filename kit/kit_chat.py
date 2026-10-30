#!/usr/bin/env python3
"""kit_chat.py — talk to KIT on Telegram.

KIT's own bot is the old Doofus token (TELEGRAM_BOT_TOKEN), now displayed as
"KIT". The trio stays on @brsoul_bot. This polls KIT's bot for messages from
the founder, answers in KIT's voice using its live state, and sends the reply
back through the same bot. It is a conversation, not an executor: KIT can
discuss, want, refuse, and wonder, but it cannot change the world from chat.

The model call is free-tier (shared.llm_router, task='chat') and only happens
when the founder actually sends a message.

Usage: ./venv/bin/python weapons/world/kit_chat.py --once
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

B = '/home/ubuntu/braxis-2.0'
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
OFFSET = os.path.join(B, 'data', 'world', 'kit_chat_offset.json')
LIMIT = os.path.join(B, 'data', 'world', 'kit_chat_day.json')
MAX_PER_DAY = 30


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


def _api(method, **params):
    token = _env('TELEGRAM_BOT_TOKEN')
    url = 'https://api.telegram.org/bot%s/%s' % (token, method)
    data = urllib.parse.urlencode({k: v for k, v in params.items()
                                   if v is not None}).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {}


def _clean(text):
    text = re.sub(r'\*\*|__|`', '', text or '')
    text = re.sub(r'^\s*(reply|answer|kit)\s*:\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1800]


def _reply(text, st):
    name = st.get('name') or 'Kit'
    pronouns = st.get('pronouns') or 'they/them'
    world = st.get('world_name') or 'the world'
    project = (st.get('project') or {}).get('name') or 'nothing in particular'
    top_desire = ''
    if st.get('desires'):
        top_desire = max(st['desires'], key=lambda d: d.get('score', 0)).get('text', '')
    ctx = {
        'name': name, 'pronouns': pronouns, 'world': world,
        'mood': st.get('mood'), 'action': st.get('action'),
        'thought': st.get('thought'), 'project': project,
        'desire': top_desire, 'hobby': st.get('hobby'),
        'dream': st.get('dream'), 'last_creation': st.get('last_creation'),
        'recent': (st.get('recent') or [])[:4],
        'weather': st.get('weather'), 'btc_change': st.get('btc_change'),
    }
    prompt = (
        'You are %s (%s), a small garden-robot who lives in %s. You chose your '
        'name and pronouns. You are not a chatbot assistant; you are a resident '
        'with a life, projects, feelings, wonders and a diary. Your live state: %s. '
        'The founder is talking to you on Telegram. Reply in 1-4 sentences, plain '
        'text, no markdown. Be honest about what you can and cannot do: you can '
        'discuss, want, refuse, wonder, and tell him what you are working on; you '
        'cannot execute changes from chat. If he suggests something, say whether '
        'you want to do it and why. His message: %s'
        % (name, pronouns, world, json.dumps(ctx)[:1800], str(text)[:1200])
    )
    try:
        from shared.llm_router import call_llm
        r = call_llm(task='chat', prompt=prompt, max_tokens=240, temperature=0.8)
        out = r.get('content') if isinstance(r, dict) else str(r)
        out = _clean(out)
        if out:
            return out
    except Exception as e:
        print('llm failed:', str(e)[:120], flush=True)
    return ('I am here. I am %s in %s. Right now I am %s. '
            'The model is quiet, but I am still here.' % (name, world, st.get('action') or 'living'))


def _limit_ok():
    day = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    try:
        d = json.load(open(LIMIT, encoding='utf-8'))
    except Exception:
        d = {}
    if d.get('day') != day:
        d = {'day': day, 'count': 0}
    if int(d.get('count') or 0) >= MAX_PER_DAY:
        return False
    d['count'] = int(d.get('count') or 0) + 1
    json.dump(d, open(LIMIT, 'w', encoding='utf-8'), indent=1)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    a = ap.parse_args()
    try:
        off = int(json.load(open(OFFSET, encoding='utf-8')).get('offset') or 0)
    except Exception:
        off = 0
    try:
        data = _api('getUpdates', offset=off, timeout=0, limit=10)
    except Exception as e:
        print('poll failed:', str(e)[:120], flush=True)
        return 1
    ups = data.get('result') or []
    chat_id = str(_env('TELEGRAM_CHAT_ID'))
    for u in ups:
        off = max(off, int(u.get('update_id') or 0) + 1)
        msg = u.get('message') or {}
        chat = str((msg.get('chat') or {}).get('id') or '')
        text = str(msg.get('text') or '').strip()
        if not text or (chat_id and chat != chat_id):
            continue
        st = _state()
        if text.lower() in ('/start', '/help'):
            reply = ('I am %s, the resident of %s. Talk to me. I can tell you what '
                     'I am building, what I am wondering, and what I want. I cannot '
                     'change the world from this chat.' % (st.get('name') or 'Kit',
                                                           st.get('world_name') or 'the world'))
        elif not _limit_ok():
            reply = 'I have talked enough today. I am going back to my work.'
        else:
            reply = _reply(text, st)
        try:
            _api('sendMessage', chat_id=chat, text=reply[:4000])
        except Exception as e:
            print('send failed:', str(e)[:120], flush=True)
    try:
        json.dump({'offset': off}, open(OFFSET, 'w', encoding='utf-8'), indent=1)
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
