#!/usr/bin/env python3
"""world_share.py — put KIT's builds in front of people.

The founder: "we need a way to share this with the world and social media and
shit!!"

On a new build this opens https://braxisai.com/world/?build=<id>&capture=1 in
headless Chromium, waits for the scene, takes a clean 1080x1080 frame, checks
that the image is actually served, and queues honest posts through the existing
pending_content drains (facebook, instagram, linkedin, x). No invented numbers,
no fake claims, no static-video upload to TikTok.

Usage:
  ./venv/bin/python weapons/world/world_share.py --scan
  ./venv/bin/python weapons/world/world_share.py --build kit-...
  ./venv/bin/python weapons/world/world_share.py --scan --dry
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.request
import uuid

B = '/home/ubuntu/braxis-2.0'
DB = os.path.join(B, 'data', 'dashboard.db')
BUILDS = os.path.join(B, 'data', 'world', 'world_builds.json')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
SHARED = os.path.join(B, 'data', 'world', 'shared_builds.json')
MEDIA = os.path.join(B, 'data', 'media', 'world')
PUBLIC = 'https://braxisai.com/media/world/'
WORLD = 'https://braxisai.com/world/'


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


def capture(build):
    """A clean frame of the build. Returns the local path."""
    from playwright.sync_api import sync_playwright
    os.makedirs(MEDIA, exist_ok=True)
    out = os.path.join(MEDIA, 'build_%s.png' % build['id'].replace('/', '_'))
    url = '%s?build=%s&capture=1' % (WORLD, build['id'])
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True,
                              args=['--use-gl=swiftshader', '--enable-webgl',
                                    '--ignore-gpu-blocklist'])
        pg = b.new_page(viewport={'width': 1080, 'height': 1080})
        pg.goto(url, wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(9000)
        pg.screenshot(path=out)
        b.close()
    return out


def caption(build, state):
    world = state.get('world_name') or 'Braxis World'
    tag = state.get('tagline') or ''
    extra = (' %s' % tag) if tag else ''
    return ("KIT finished %s in %s.%s See it: %s?build=%s"
            % (build.get('name') or build.get('kind'), world, extra,
               WORLD, build['id']))


def queue(build, image_url, state):
    cap = caption(build, state)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    title = ('KIT built %s' % (build.get('name') or build.get('kind')))[:110]
    bodies = {
        'facebook': cap + ' Built in the open.',
        'instagram': cap + ' 🌱',
        'linkedin': 'A small robot is building a world in public. ' + cap,
        'x': cap,
        'bluesky': cap,
        'mastodon': cap,
        'youtube': cap,
        'tiktok': cap,
    }
    rows = []
    plan = []
    try:
        from shared.determiner import route
        for platform, ctype, why in route('image', weapon='kit_world', image_url=image_url):
            rows.append((platform, ctype, bodies.get(platform, cap),
                         image_url if ctype == 'image' else None, why))
            plan.append({'platform': platform, 'kind': ctype, 'why': why})
        seen = {r[0] for r in rows}
        for platform, ctype, why in route('text', weapon='kit_world'):
            if platform not in seen:
                rows.append((platform, ctype, bodies.get(platform, cap), None, why))
                plan.append({'platform': platform, 'kind': ctype, 'why': why})
    except Exception as e:
        print('decider failed, fallback routing:', str(e)[:120])
        rows = [
            ('facebook', 'image', bodies['facebook'], image_url, 'fallback'),
            ('instagram', 'image', bodies['instagram'], image_url, 'fallback'),
            ('linkedin', 'image', bodies['linkedin'], image_url, 'fallback'),
            ('x', 'text', bodies['x'], None, 'fallback'),
        ]
        plan = [{'platform': p, 'kind': c, 'why': w} for p, c, _b, _i, w in rows]
    try:
        with open(os.path.join(B, 'data', 'world', 'share_plan.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'build': build.get('id'), 'ts': now, 'plan': plan}, f, indent=1)
    except Exception:
        pass
    con = sqlite3.connect(DB, timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    ids = []
    for platform, ctype, body, img, why in rows:
        cur = con.execute(
            'INSERT INTO pending_content (client_uuid, weapon, platform, content_type, '
            'title, body, image_url, hashtags, scheduled_at, status, created_at, topic_id) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()), 'kit_world', platform, ctype, title, body[:900],
             img, '#BraxisWorld #AI #3D', now, 'approved', now, title[:160]))
        ids.append(cur.lastrowid)
        print('  queue %-10s %-6s — %s' % (platform, ctype, why[:100]))
    con.commit()
    con.close()
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', default='')
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    builds = _load(BUILDS, [])
    shared = set(_load(SHARED, []))
    if not isinstance(builds, list):
        builds = []
    if a.build:
        build = next((b for b in builds if b.get('id') == a.build), None)
        if not build:
            print('no such build:', a.build)
            return 1
    elif a.scan:
        fresh = [b for b in builds if b.get('id') not in shared]
        if not fresh:
            print('nothing new to share')
            return 0
        build = sorted(fresh, key=lambda b: b.get('built_at', ''))[-1]
    else:
        print('use --scan or --build <id>')
        return 1
    state = _load(STATE, {})
    print('share:', build.get('id'), build.get('kind'), build.get('name'))
    print('caption:', caption(build, state))
    if a.dry:
        return 0
    img = capture(build)
    if not os.path.exists(img) or os.path.getsize(img) < 5000:
        print('capture failed:', img)
        return 1
    url = PUBLIC + os.path.basename(img)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            if r.status != 200:
                print('image not served:', r.status, url)
                return 1
    except Exception as e:
        print('image not served:', e, url)
        return 1
    ids = queue(build, url, state)
    shared.add(build['id'])
    _save(SHARED, sorted(shared))
    print('queued rows:', ids, 'image:', url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
