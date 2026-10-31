#!/usr/bin/env python3
"""kit_image.py — make a real image for one KIT creation via free Pollinations.

The gallery card is a designed interpretation; this is the actual painted image.
One per run, max one a day when scheduled. Writes image_url onto the creation.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import urllib.parse
import urllib.request

from PIL import Image

B = '/home/ubuntu/braxis-2.0'
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
MEDIA = os.path.join(B, 'data', 'media', 'world', 'creations')
PUBLIC = 'https://braxisai.com/media/world/creations/'
DAYFILE = os.path.join(B, 'data', 'world', 'creation_image_day.json')
POLL = 'https://image.pollinations.ai/prompt/{}?width=1024&height=1280&nologo=true&seed={}'


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
    ap.add_argument('--creation', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    items = _load(CREATIONS, [])
    state = _load(STATE, {})
    if a.creation:
        c = next((x for x in items if x.get('id') == a.creation), None)
    else:
        bad_topics = ('hacker news', 'github', 'wikipedia', 'arxiv',
                      'factor xiii', 'aquifer', 'trending repositories')
        fresh = [x for x in items if not x.get('image_url')
                 and x.get('medium') != 'code'
                 and not any(b in (str(x.get('title','')) + ' ' +
                                   str(x.get('subject',''))).lower()
                             for b in bad_topics)]
        c = fresh[-1] if fresh else None
    if not c:
        print('no creation without an image')
        return 1
    world = state.get('world_name') or 'Glowveil Hollow'
    title = c.get('title') or 'a creation'
    subject = c.get('subject') or 'something of its own'
    medium = c.get('medium') or 'paint'
    prompt = ('%s. %s in %s, %s style, painterly, warm, soft light, original '
              'artwork, no text, no watermark, no signature, no frame.'
              % (title, subject, world, medium))
    seed = int(hashlib.sha1(str(c.get('id')).encode()).hexdigest()[:8], 16) % 1000000
    url = POLL.format(urllib.parse.quote(prompt), seed)
    print('creation:', c.get('id'), '|', title)
    print('prompt:', prompt)
    print('url:', url)
    if a.dry:
        return 0
    data = None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'm3', os.path.join(B, 'weapons', 'meme_three.py'))
        m3 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m3)
        data = m3.flux(prompt)
    except Exception as e:
        print('image engine failed:', str(e)[:180])
    if not data:
        print('no image returned')
        return 1
    if len(data) < 20000:
        print('image too small:', len(data))
        return 1
    os.makedirs(MEDIA, exist_ok=True)
    cid = re.sub(r'[^A-Za-z0-9_-]', '_', str(c.get('id') or 'creation'))
    path = os.path.join(MEDIA, 'creation_%s_art.jpg' % cid)
    try:
        img = Image.open(io.BytesIO(data)).convert('RGB')
        img.thumbnail((1200, 1500))
        img.save(path, 'JPEG', quality=92)
    except Exception:
        with open(path, 'wb') as f:
            f.write(data)
    img_url = PUBLIC + os.path.basename(path)
    for x in items:
        if x.get('id') == c.get('id'):
            x['image_url'] = img_url
            x['image_prompt'] = prompt
            x['image_created'] = dt.datetime.now(dt.timezone.utc).isoformat(
                timespec='seconds')
    _save(CREATIONS, items)
    print('IMAGE', path, len(data), 'bytes')
    print('URL', img_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
