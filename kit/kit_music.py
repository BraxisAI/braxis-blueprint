#!/usr/bin/env python3
"""kit_music.py — make one real KIT song through the ACE lane.

This is KIT's own music, not the paused serial-artist lane. It writes a short
lyric from KIT's live state, calls ACE's cloud_song_v2, saves the audio under
data/songs/Braxis_Songs/Kit/, marks the creation with audio_url, and updates
any queued "KIT made a song" post with the listen link.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sqlite3
import sys
import urllib.parse

B = '/home/ubuntu/braxis-2.0'
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
DB = os.path.join(B, 'data', 'dashboard.db')
SONG_DIR = os.path.join(B, 'data', 'songs', 'Braxis_Songs', 'Kit')
SONG_URL = 'https://braxisai.com/media/music/Braxis_Songs/Kit/'


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


def _clean(text, limit=300):
    text = re.sub(r'\*\*|__|`', '', str(text or ''))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def lyrics_for(creation, state):
    name = state.get('name') or 'Kit'
    world = state.get('world_name') or 'Glowveil Hollow'
    subject = _clean(creation.get('subject') or 'the garden', 60)
    thought = _clean(state.get('thought') or '', 120)
    if 'i am here' in thought.lower():
        thought = 'The town is quiet, and I am learning its names.'
    desire = ''
    if state.get('desires'):
        desire = _clean(max(state['desires'],
                            key=lambda d: float(d.get('score', 0))).get('text', ''), 100)
    last_build = (state.get('last_build') or {}).get('name') or ''
    return (
        "[Verse]\n"
        "I am %s, and the evening is low,\n"
        "the lamps are little seeds of gold.\n"
        "I made a song about %s,\n"
        "and kept the quiet parts untold.\n\n"
        "[Chorus]\n"
        "If you listen by the garden wall,\n"
        "you will hear the small machines begin.\n"
        "The night is wide, and I am in it,\n"
        "but tonight I let the song come in.\n\n"
        "[Verse]\n"
        "%s\n"
        "The town is a sentence I am learning to read.\n"
        "I leave a light on for whoever comes,\n"
        "and plant the next thing from a seed.\n\n"
        "[Chorus]\n"
        "If you listen by the garden wall,\n"
        "you will hear the small machines begin.\n"
        "The night is wide, and I am in it,\n"
        "but tonight I let the song come in.\n"
        % (name, subject,
           thought or ('I finished %s and let it stand.' % last_build
                       if last_build else 'I keep returning to %s.' % subject))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--creation', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    state = _load(STATE, {})
    items = _load(CREATIONS, [])
    if a.creation:
        c = next((x for x in items if x.get('id') == a.creation), None)
    else:
        fresh = [x for x in items
                 if x.get('medium') == 'sing' and not x.get('audio_url')]
        c = fresh[-1] if fresh else None
    if not c:
        print('no song creation without audio')
        return 1
    lyrics = lyrics_for(c, state)
    prompt = ('warm indie folk, intimate, fingerpicked acoustic guitar, soft synth, '
              'gentle robot voice, garden at dusk, hopeful, 92 bpm')
    job = {'title': c.get('title') or 'a song about the trio',
           'prompt': prompt, 'lyrics': lyrics, 'duration': 70, 'bpm': 92,
           'guidance': 7, 'keyscale': 'C Major', 'timesignature': '4/4'}
    print('creation:', c.get('id'), c.get('title'))
    print('lyrics:\n' + lyrics)
    if a.dry:
        return 0

    spec = importlib.util.spec_from_file_location(
        'ace', os.path.join(B, 'weapons', 'ace_processor.py'))
    ace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ace)
    print('calling ACE cloud_song_v3...', flush=True)
    audio = ace.cloud_song_v3(job)
    if not audio or len(audio) < 10000:
        print('ACE returned no usable audio:', len(audio or b''))
        return 1
    os.makedirs(SONG_DIR, exist_ok=True)
    # ACE's own watcher renames finished tracks by title; save to that name so
    # the creation record and the served file cannot drift apart.
    title_name = re.sub(r'[^A-Za-z0-9 _-]', '', str(c.get('title') or 'song'))[:60].strip()
    path = os.path.join(SONG_DIR, (title_name or 'song') + '.mp3')
    with open(path, 'wb') as f:
        f.write(audio)
    txt = os.path.join(SONG_DIR, (title_name or 'song') + '.txt')
    with open(txt, 'w', encoding='utf-8') as f:
        f.write('TITLE: %s\nPROMPT: %s\n\n%s\n'
                % (c.get('title'), prompt, lyrics))
    url = SONG_URL + urllib.parse.quote(os.path.basename(path))
    for x in items:
        if x.get('id') == c.get('id'):
            x['audio_url'] = url
            x['audio_file'] = path
            x['audio_created'] = dt.datetime.now(dt.timezone.utc).isoformat(
                timespec='seconds')
    _save(CREATIONS, items)
    con = sqlite3.connect(DB, timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    cur = con.execute(
        "UPDATE pending_content SET body = body || ' Listen: ' || ? "
        "WHERE weapon='kit_world' AND status IN ('pending','approved') "
        "AND title = ?",
        (url, ('KIT made %s' % (c.get('title') or 'a song'))[:110]))
    con.commit()
    con.close()
    print('AUDIO', path, len(audio), 'bytes')
    print('URL', url)
    print('updated queued posts:', cur.rowcount)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
