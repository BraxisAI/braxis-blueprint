#!/usr/bin/env python3
"""world_video.py — a window into the live world.

The founder: "I want to see posts of live feeds of the world... I think this
would get some attention."

This records a 15-second vertical clip of https://braxisai.com/world/?video=1
with Playwright, converts it to mp4, and queues it through the estate's
determiner. The world itself is live; the clip is a window into it. No static
slideshow, no fake "live" claim.

Usage:
  ./venv/bin/python weapons/world/world_video.py --force
  ./venv/bin/python weapons/world/world_video.py
"""
import argparse
import datetime as dt
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
import uuid

B = '/home/ubuntu/braxis-2.0'
DB = os.path.join(B, 'data', 'dashboard.db')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
MEDIA = os.path.join(B, 'data', 'media', 'world')
PUBLIC = 'https://braxisai.com/media/world/'
WORLD = 'https://braxisai.com/world/'
SHARED = os.path.join(B, 'data', 'world', 'live_shared.json')
MIN_GAP = 12 * 3600


def _state():
    try:
        with urllib.request.urlopen('https://braxisai.com/api/world/state',
                                    timeout=15) as r:
            return json.load(r)
    except Exception:
        try:
            return json.load(open(STATE, encoding='utf-8'))
        except Exception:
            return {}


LAST_AUDIO = ''


def capture():
    global LAST_AUDIO
    from playwright.sync_api import sync_playwright
    os.makedirs(MEDIA, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='worldvid-', dir=MEDIA)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True,
                              args=['--use-gl=swiftshader', '--enable-webgl',
                                    '--ignore-gpu-blocklist'])
        ctx = b.new_context(
            viewport={'width': 1080, 'height': 1920},
            record_video_dir=tmp,
            record_video_size={'width': 1080, 'height': 1920})
        page = ctx.new_page()
        started = time.time()
        page.goto(WORLD + '?video=1', wait_until='domcontentloaded', timeout=90000)
        loaded_at = started
        ready = False
        try:
            page.wait_for_function("() => { const e=document.getElementById('load'); return !e || getComputedStyle(e).display === 'none'; }", timeout=120000)
            loaded_at = time.time()
            ready = True
        except Exception as e:
            print('load gate timeout:', str(e)[:120])
        if not ready:
            print('world never finished loading; refusing to queue a loading-screen clip')
            ctx.close()
            b.close()
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        page.wait_for_timeout(15000)
        ctx.close()
        b.close()
    src = sorted(glob.glob(os.path.join(tmp, '*.webm')))
    if not src:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = os.path.join(MEDIA, 'live_%s.mp4' % ts)
    kits = sorted(glob.glob(os.path.join(
        B, 'data', 'songs', 'Braxis_Songs', 'Kit', '*.mp3')), key=os.path.getmtime)
    LAST_AUDIO = kits[-1] if kits else ''
    trim = max(0.0, loaded_at - started - 0.5)
    print('trim before world:', round(trim, 2), 's')
    cmd = ['ffmpeg', '-y']
    if trim > 0:
        cmd += ['-ss', '%.2f' % trim]
    cmd += ['-i', src[0]]
    if LAST_AUDIO:
        cmd += ['-i', LAST_AUDIO]
    cmd += ['-vf', 'scale=1080:1920', '-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    if LAST_AUDIO:
        cmd += ['-c:a', 'aac', '-b:a', '192k', '-shortest']
    else:
        cmd += ['-an']
    cmd += [out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(out):
        print('ffmpeg failed:', r.stderr[-300:])
        return None
    if os.path.getsize(out) < 100000:
        print('video too small / likely loading frame:', os.path.getsize(out))
        return None
    return out


def _story_caption(state):
    """A Pino-style episode caption: day number, one concrete beat, invitation.
    Facts only; the model may phrase, not invent."""
    world = state.get('world_name') or 'Glowveil Hollow'
    action = state.get('action') or 'living'
    project = (state.get('project') or {}).get('name') or 'between projects'
    last = state.get('last_creation') or {}
    last_build = state.get('last_build') or {}
    comp = state.get('companion') or {}
    thought = str(state.get('thought') or '')[:160]
    day = 1
    try:
        born = dt.datetime.fromisoformat(str(state.get('born')))
        if born.tzinfo is None:
            born = born.replace(tzinfo=dt.timezone.utc)
        day = max(1, (dt.datetime.now(dt.timezone.utc) - born).days + 1)
    except Exception:
        pass
    facts = ("Day %d in %s. KIT is %s. Project: %s. Latest creation: %s. "
             "Latest build: %s. Companion: %s the %s. Thought: %s"
             % (day, world, action, project,
                last.get('title') or last.get('medium') or 'none',
                last_build.get('name') or 'none',
                comp.get('name') or 'none', comp.get('kind') or 'companion',
                thought or 'none'))
    fallback = ("Day %d in %s: KIT is %s. The hollow is live at "
                "braxisai.com/world — leave a stone, a flower, or a song and "
                "KIT will find it. KIT's notebook: braxisai.com/builds/kit-notebook/"
                % (day, world, action))
    try:
        from shared.llm_router import call_llm
        prompt = (
            "Write ONE TikTok/Shorts caption for a 15-second vertical clip of a "
            "living 3D world. Narrator is the maker, not the robot. Use ONLY the "
            "facts below; do not invent numbers, visitors, events, or claims. "
            "First line is a hook with the day number and one concrete thing KIT "
            "did. Then one short human detail. End with one invitation to visit "
            "braxisai.com/world and leave a stone, flower, or song. Plain text, "
            "no hashtags, max 260 characters." + (chr(10) * 2) + "FACTS: " + facts)
        r = call_llm(prompt, task='writing', max_tokens=180, temperature=.7)
        text = str((r or {}).get('content') or '').strip()
        text = text.replace('**', '').strip()
        if len(text) >= 40 and 'braxisai.com/world' in text:
            if 'kit-notebook' not in text:
                text = text.rstrip() + " KIT's notebook: braxisai.com/builds/kit-notebook/"
            return text[:430]
    except Exception:
        pass
    return fallback


def queue(video_url, state, with_audio=False):
    from shared.determiner import route
    world = state.get('world_name') or 'the world'
    action = state.get('action') or 'living'
    thought = state.get('thought') or ''
    cap = _story_caption(state)
    if with_audio:
        cap += ' With KIT’s own song.'
    title = ('Live from %s' % world)[:110]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    rows = []
    plan = []
    for platform, ctype, why in route('video', weapon='kit_world',
                                      image_url=video_url):
        if platform not in ('tiktok', 'instagram', 'youtube', 'facebook'):
            continue  # dead/zero-cap platforms only park rows
        rows.append((platform, ctype, why))
        plan.append({'platform': platform, 'kind': ctype, 'why': why})
    if not rows:
        rows = [('tiktok', 'video', 'fallback')]
    con = sqlite3.connect(DB, timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    ids = []
    for platform, ctype, why in rows:
        cur = con.execute(
            'INSERT INTO pending_content (client_uuid, weapon, platform, content_type, '
            'title, body, image_url, hashtags, scheduled_at, status, created_at, topic_id) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()), 'kit_world', platform, ctype, title, cap[:900],
             video_url, '#BraxisWorld #AI #3D', now, 'approved', now, title[:160]))
        _id = cur.lastrowid
        if not _id:
            print('  DROPPED by story dedup: %s %s' % (platform, title[:60]))
            continue
        ids.append(_id)
        print('  queue %-10s %-6s — %s' % (platform, ctype, why[:100]))
    con.commit()
    con.close()
    try:
        with open(os.path.join(B, 'data', 'world', 'live_plan.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'video': video_url, 'ts': now, 'plan': plan}, f, indent=1)
    except Exception:
        pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    try:
        last = float(json.load(open(SHARED, encoding='utf-8')).get('last') or 0)
    except Exception:
        last = 0
    import time
    if not a.force and time.time() - last < MIN_GAP:
        print('live clip already shared in the last 20h')
        return 0
    mp4 = capture()
    if not mp4:
        return 1
    url = PUBLIC + os.path.basename(mp4)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            if r.status != 200:
                print('video not served:', r.status)
                return 1
    except Exception as e:
        print('video not served:', e)
        return 1
    # The world clip is only worth posting if a stranger can see the world.
    # Fail closed: no visual verdict means no post, not a silent pass.
    try:
        from shared.visual_critic import critique_video
        vc = critique_video(
            mp4,
            context=("A vertical short of Glowveil Hollow, a stylized 3D world. "
                     "KIT is a white robot resident; Juniper is a green moss-cat. "
                     "The world and its buildings should be clearly visible. "
                     "Reject UI panels, HUD overlays, a tree blocking the subject, "
                     "a mostly empty frame, or a clip that is a still image."))
        print('visual critic:', vc.get('score'), vc.get('ok'), vc.get('notes'))
        for d in (vc.get('defects') or []):
            print('  defect:', d)
        if not vc.get('ok'):
            print('world video rejected by visual critic')
            return 1
    except Exception as e:
        print('visual critic unavailable; refusing to post unseen:', str(e)[:160])
        return 1
    ids = queue(url, _state(), with_audio=bool(LAST_AUDIO))
    try:
        json.dump({'last': time.time(), 'video': url}, open(SHARED, 'w', encoding='utf-8'))
    except Exception:
        pass
    print('queued', ids, url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
