#!/usr/bin/env python3
"""kit_diary.py — one honest diary post a day from KIT's actual reflection."""
import argparse
import datetime as dt
import json
import os
import sqlite3
import uuid

B = '/home/ubuntu/braxis-2.0'
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
DB = os.path.join(B, 'data', 'dashboard.db')
DAYFILE = os.path.join(B, 'data', 'world', 'kit_diary_day.json')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    state = _load(STATE, {})
    today = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    day = _load(DAYFILE, {})
    if day.get('day') == today:
        print('diary already posted today')
        return 0
    reflection = str(state.get('reflection') or '').strip()
    if not reflection:
        print('no reflection yet')
        return 1
    world = state.get('world_name') or 'Glowveil Hollow'
    dream = str(state.get('dream') or '').strip()
    body = ('KIT’s diary — %s\n\n%s' % (world, reflection[:700]))
    if dream:
        body += '\n\nDream: %s' % dream[:180]
    body += '\n\nSee the world: %s' % WORLD
    title = ('KIT’s diary — %s' % today)[:110]
    print('title:', title)
    print('body:', body)
    if a.dry:
        return 0
    try:
        from shared.determiner import route
        rows = [p for p, _c, _w in route('text', weapon='kit_world')
                if p not in ('x', 'twitter')]
    except Exception:
        rows = []
    if not rows:
        rows = ['linkedin', 'bluesky', 'mastodon', 'facebook']
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    con = sqlite3.connect(DB, timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    ids = []
    for platform in rows:
        cur = con.execute(
            'INSERT INTO pending_content (client_uuid, weapon, platform, content_type, '
            'title, body, hashtags, scheduled_at, status, created_at, topic_id) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()), 'kit_world', platform, 'text', title, body[:900],
             '#KIT #GlowveilHollow #Diary', now, 'approved', now, title[:160]))
        ids.append(cur.lastrowid)
        print('  queue', platform)
    con.commit()
    con.close()
    _save(DAYFILE, {'day': today, 'ids': ids})
    print('queued', ids)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
