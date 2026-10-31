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
MIN_GAP = 20 * 3600


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
        page.goto(WORLD + '?video=1', wait_until='domcontentloaded', timeout=60000)
        loaded_at = started
        ready = False
        try:
            page.wait_for_function("() => { const e=document.getElementById('load'); return !e || getComputedStyle(e).display === 'none'; }", timeout=60000)
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


def queue(video_url, state, with_audio=False):
    from shared.determiner import route
    world = state.get('world_name') or 'the world'
    action = state.get('action') or 'living'
    thought = state.get('thought') or ''
    cap = ('A 15-second window into %s. KIT is %s. %s The world is live: %s'
           % (world, action, thought[:180], WORLD))
    if with_audio:
        cap += ' With KIT’s own song.'
    title = ('Live from %s' % world)[:110]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    rows = []
    plan = []
    for platform, ctype, why in route('video', weapon='kit_world',
                                      image_url=video_url):
        if platform in ('x', 'twitter'):
            continue  # X is parked; do not queue dead rows.
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
        ids.append(cur.lastrowid)
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
    ids = queue(url, _state(), with_audio=bool(LAST_AUDIO))
    try:
        json.dump({'last': time.time(), 'video': url}, open(SHARED, 'w', encoding='utf-8'))
    except Exception:
        pass
    print('queued', ids, url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
