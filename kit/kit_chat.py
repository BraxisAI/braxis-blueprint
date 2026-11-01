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
import base64
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
WISHLIST = os.path.join(B, 'data', 'world', 'kit_wishlist.json')
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


def _load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _clean(text):
    text = re.sub(r'\*\*|__|`', '', text or '')
    text = re.sub(r'^\s*(reply|answer|kit)\s*:\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1800]


def _describe_photo(file_id):
    """Fetch a Telegram photo and let the free NVIDIA vision lane read it."""
    try:
        d = _api('getFile', file_id=file_id)
        path = ((d.get('result') or {}).get('file_path') or '')
        if not path:
            return ''
        token = _env('TELEGRAM_BOT_TOKEN')
        url = 'https://api.telegram.org/file/bot%s/%s' % (token, path)
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read()
        if len(data) < 200:
            return ''
        folder = os.path.join(B, 'data', 'world', 'chat_images')
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(path)[1] or '.jpg'
        with open(os.path.join(folder, str(file_id) + ext), 'wb') as f:
            f.write(data)
        key = _env('NVIDIA_API_KEY')
        if not key:
            try:
                from shared import config
                key = config.NVIDIA_API_KEY
            except Exception:
                key = ''
        if not key:
            return ''
        b64 = base64.b64encode(data).decode('ascii')
        mime = 'image/jpeg' if ext.lower() in ('.jpg', '.jpeg') else 'image/png'
        body = json.dumps({
            'model': 'meta/muse-glimmer-30b',
            'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': (
                    'You are KIT, a small garden-robot in a 3D world. The founder '
                    'sent this photo. In 1-3 sentences, say concretely what you '
                    'see and what it makes you think or feel. Do not invent '
                    'details; if it is a cat, plant, room, screen or object, name '
                    'it plainly.')},
                {'type': 'image_url', 'image_url': {
                    'url': 'data:%s;base64,%s' % (mime, b64)}}]}],
            'max_tokens': 500, 'temperature': 0.4,
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://integrate.api.nvidia.com/v1/chat/completions', data=body,
            headers={'Authorization': 'Bearer ' + key,
                     'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode('utf-8', 'ignore'))
        text = (((out.get('choices') or [{}])[0].get('message') or {})
                .get('content') or '')
        return _clean(text)
    except Exception as e:
        print('photo vision failed:', str(e)[:160], flush=True)
        return ''


def _chat_history(limit=4):
    try:
        rows = open(os.path.join(B, 'data/world/kit_chat_log.jsonl'),
                    encoding='utf-8').read().splitlines()[-limit:]
    except Exception:
        return []
    out = []
    for line in rows:
        try:
            x = json.loads(line)
            out.append({'q': str(x.get('q') or '')[:240],
                        'a': str(x.get('a') or '')[:240]})
        except Exception:
            pass
    return out


def _maybe_send_picture(chat, text, st):
    if not re.search(r'(send|show|see|want).{0,30}(picture|image|painting|photo|art)',
                     text or '', re.I):
        return ''
    try:
        items = _load_json(os.path.join(B, 'data', 'world', 'world_creations.json'), [])
    except Exception:
        items = []
    real = [x for x in items if x.get('image_url')]
    if not real:
        return ''
    c = real[-1]
    url = c.get('image_url')
    try:
        _api('sendPhoto', chat_id=chat, photo=url,
             caption=(c.get('title') or 'a picture I made')[:900])
        return 'I sent you %s.' % (c.get('title') or 'the picture')
    except Exception as e:
        print('send photo failed:', str(e)[:160], flush=True)
        return ''


def _queue_command(text):
    """Let a Telegram message actually queue a browse or a watch."""
    low = str(text or '').lower()
    m = re.search(r'(?:look up|search(?: the internet)? for|browse)\s+(.+)', text or '', re.I)
    if m:
        topic = _clean(m.group(1))[:120]
        try:
            body = json.dumps({'topic': topic}).encode('utf-8')
            req = urllib.request.Request(
                'http://127.0.0.1:8130/api/world/browse-request', data=body,
                headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=10).read()
            return 'I queued a look-up for %s.' % topic
        except Exception as e:
            print('browse command failed:', str(e)[:120], flush=True)
    m = re.search(r'https?://\S+', text or '')
    if m and any(w in low for w in ('watch', 'video', 'look at', 'see this')):
        url = m.group(0).rstrip(').,')
        try:
            body = json.dumps({'url': url}).encode('utf-8')
            req = urllib.request.Request(
                'http://127.0.0.1:8130/api/world/watch-request', data=body,
                headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=10).read()
            return 'I queued that video to watch.'
        except Exception as e:
            print('watch command failed:', str(e)[:120], flush=True)
    return ''


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
        'self_model': st.get('self_model'),
        'last_reading': st.get('last_reading'),
        'last_watch': st.get('last_watch'),
        'interests': [x.get('text') for x in (st.get('interests') or [])[:6]],
        'last_field_note': st.get('last_field_note'),
        'chat_history': _chat_history(4),
        'family': "Vesper is the founder's original agent; Maya, Echo and Overseer are newer. They handle the money and the empire. Your world is for wondering, and they can visit.",
        'capabilities': ('You can browse the internet with your browse action '
                         '(Wikipedia/Hacker News/GitHub/arXiv), watch a video through '
                         'the watch lane, read your field notes, make things and talk '
                         "to Juniper. You have a house in the east meadow (KIT's House); you can go home. You cannot execute payments or arbitrary code."),
        'product': ("If he asks what you can sell or what to take home: KIT's notebook, "
                    "Notes from Glowveil Hollow, is $7 and downloads instantly at "
                    "https://braxisai.com/builds/kit-notebook/."),
        'home': st.get('home'),
        'visitor_impressions': list(
            (st.get('visitor_impressions') or {}).values())[-4:],
        'wishes': (lambda wl: [w for w in (wl.get('wishes') or [])
                               if w.get('status') != 'fulfilled'][:5])(
            _load_json(WISHLIST, {})),
    }
    action_note = _queue_command(text)
    ctx['action_note'] = action_note
    prompt = (
        'You are %s (%s), a small garden-robot who lives in %s. You chose your '
        'name and pronouns. You are not a chatbot assistant; you are a resident '
        'with a life, projects, feelings, wonders and a diary. Your live state: %s. '
        'The founder is talking to you on Telegram. Reply in 1-4 sentences, plain '
        'text, no markdown. Be honest about what you can and cannot do. You CAN '
        'browse the internet (Wikipedia, Hacker News, GitHub, arXiv) and you CAN '
        'watch a video through the watch lane; never claim you cannot browse. You '
        'cannot execute payments or arbitrary code. If he asks you to look something '
        'up, queue it and say you did. If he asks what you can sell, what he can buy, '
        'or what to take home, mention KIT\'s notebook at '
        'https://braxisai.com/builds/kit-notebook/ ($7, instant PDF). His message: %s'
        % (name, pronouns, world, json.dumps(ctx)[:2400], str(text)[:1200])
    )
    try:
        from shared.llm_router import call_llm
        r = call_llm(task='chat', prompt=prompt, max_tokens=240, temperature=0.8)
        out = r.get('content') if isinstance(r, dict) else str(r)
        out = _clean(out)
        if out:
            if action_note and action_note.lower() not in out.lower():
                out = (out + ' ' + action_note)[:1800]
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
        photo = msg.get('photo') or []
        if photo:
            cap = _describe_photo(photo[-1].get('file_id') or '')
            if cap:
                text = (text + '\n[photo: ' + cap + ']').strip() if text else cap
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
        _maybe_send_picture(chat, text, st)
        try:
            import datetime as _dt
            with open(os.path.join(B, 'data', 'world', 'kit_chat_log.jsonl'), 'a',
                      encoding='utf-8') as _f:
                _f.write(json.dumps({'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(),
                                     'q': text[:1000], 'a': reply[:2000]}) + chr(10))
        except Exception:
            pass
    try:
        json.dump({'offset': off}, open(OFFSET, 'w', encoding='utf-8'), indent=1)
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
