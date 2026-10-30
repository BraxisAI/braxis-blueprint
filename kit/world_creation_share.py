#!/usr/bin/env python3
"""world_creation_share.py — turn one of KIT's creations into a gallery card,
share it, and optionally make a real Printify poster.

This is the missing half of the gallery: the page shows the creation, this
script makes it leave the page. It is deterministic (PIL, no LLM), honest
("a gallery card", not "a photograph of the thing"), and capped.

Usage:
  ./venv/bin/python weapons/world/world_creation_share.py --scan --dry
  ./venv/bin/python weapons/world/world_creation_share.py --creation art-...
  ./venv/bin/python weapons/world/world_creation_share.py --creation art-... --pod
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import sqlite3
import sys
import urllib.request
import uuid

from PIL import Image, ImageDraw, ImageFont

B = '/home/ubuntu/braxis-2.0'
DB = os.path.join(B, 'data', 'dashboard.db')
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
SHARED = os.path.join(B, 'data', 'world', 'shared_creations.json')
DAYFILE = os.path.join(B, 'data', 'world', 'creation_share_day.json')
PODS = os.path.join(B, 'data', 'world', 'kit_pod_products.json')
MEDIA = os.path.join(B, 'data', 'media', 'world', 'creations')
PUBLIC = 'https://braxisai.com/media/world/creations/'
WORLD = 'https://braxisai.com/world/'
STORE = 'https://braxis-trading-co.printify.me'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


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


def _rgb(color):
    c = int(color or 0xd7b8ff)
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def _font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def _wrap(draw, text, font, maxw):
    words = str(text or '').split()
    lines, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or ['']


def make_card(creation, state):
    """A 1200x1600 gallery card. Art is an abstract interpretation, labelled."""
    W, H = 1200, 1600
    base = _rgb(creation.get('color'))
    img = Image.new('RGB', (W, H), (9, 12, 20))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(9 * (1 - t * .7) + base[i] * (t * .55)) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    rnd = random.Random(str(creation.get('id') or 'kit'))
    art = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(art)
    medium = str(creation.get('medium') or 'paint')
    for i in range(10):
        x = rnd.randint(80, W - 80)
        y = rnd.randint(110, int(H * .54))
        r = rnd.randint(45, 210)
        col = base + (rnd.randint(45, 95),)
        if medium in ('carve', 'photograph'):
            ad.rectangle([x - r, y - r, x + r, y + r], outline=col, width=max(2, r // 18))
        elif medium in ('write', 'sing'):
            ad.line([(x - r, y), (x + r, y)], fill=col, width=max(2, r // 12))
        else:
            ad.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img = Image.alpha_composite(img.convert('RGBA'), art).convert('RGB')
    d = ImageDraw.Draw(img)

    # a dark panel keeps the title readable over the art
    panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([54, int(H * .58), W - 54, H - 54], fill=(8, 10, 16, 205))
    img = Image.alpha_composite(img.convert('RGBA'), panel).convert('RGB')
    d = ImageDraw.Draw(img)

    title = str(creation.get('title') or creation.get('subject') or 'a creation')
    maxw = W - 220
    size = 104
    lines = []
    while size >= 44:
        f = _font(size, True)
        lines = _wrap(d, title, f, maxw)
        if len(lines) <= 3 and all(d.textlength(l, font=f) <= maxw for l in lines):
            break
        size -= 4
    f = _font(size, True)
    y = int(H * .61)
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text(((W - tw) / 2, y), line, font=f, fill=(238, 240, 246))
        y += int(size * 1.14)

    sub = '%s · %s · level %s' % (
        medium, creation.get('subject') or 'something of its own',
        creation.get('level') or 1)
    fs = _font(34, False)
    tw = d.textlength(sub, font=fs)
    d.text(((W - tw) / 2, y + 10), sub, font=fs, fill=(170, 182, 200))

    # honest label: this is a card, not the physical object
    note = 'KIT’s gallery card · an abstract interpretation'
    fn = _font(26, False)
    tw = d.textlength(note, font=fn)
    d.text(((W - tw) / 2, y + 70), note, font=fn, fill=(140, 150, 168))

    d.text((54, 54), 'KIT', font=_font(34, True), fill=(255, 212, 121))
    wname = str(state.get('world_name') or 'Glowveil Hollow')
    fw = _font(24, False)
    tw = d.textlength(wname, font=fw)
    d.text((W - 54 - tw, 60), wname, font=fw, fill=(215, 184, 255))
    d.line([(54, H - 116), (W - 54, H - 116)], fill=(255, 212, 121, 180), width=2)
    d.text((54, H - 96), 'braxisai.com/world', font=_font(24, False),
           fill=(170, 182, 200))
    fw = _font(24, False)
    tw = d.textlength('made by KIT', font=fw)
    d.text((W - 54 - tw, H - 96), 'made by KIT', font=fw, fill=(170, 182, 200))

    os.makedirs(MEDIA, exist_ok=True)
    cid = re.sub(r'[^A-Za-z0-9_-]', '_', str(creation.get('id') or 'creation'))
    path = os.path.join(MEDIA, 'creation_%s.png' % cid)
    img.save(path, 'PNG')
    return path


def _caption(creation, state, pod_url=''):
    world = state.get('world_name') or 'Glowveil Hollow'
    title = creation.get('title') or 'a creation'
    cap = ('KIT made %s in %s. A gallery card from the resident’s own work. '
           'See it: %s?gallery=1' % (title, world, WORLD))
    if pod_url:
        cap += ' Print: %s' % pod_url
    return cap


def _queue(creation, image_url, state, pod_url=''):
    from shared.determiner import route
    cap = _caption(creation, state, pod_url)
    title = ('KIT made %s' % (creation.get('title') or 'a creation'))[:110]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    rows, plan = [], []
    try:
        for platform, ctype, why in route('image', weapon='kit_world',
                                          image_url=image_url):
            if platform in ('x', 'twitter'):
                continue
            rows.append((platform, ctype, why))
            plan.append({'platform': platform, 'kind': ctype, 'why': why})
    except Exception as e:
        print('decider failed, fallback:', str(e)[:120])
    if not rows:
        rows = [('facebook', 'image', 'fallback'), ('instagram', 'image', 'fallback'),
                ('linkedin', 'image', 'fallback'), ('mastodon', 'image', 'fallback'),
                ('bluesky', 'image', 'fallback')]
        plan = [{'platform': p, 'kind': c, 'why': w} for p, c, w in rows]
    con = sqlite3.connect(DB, timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    ids = []
    for platform, ctype, why in rows:
        cur = con.execute(
            'INSERT INTO pending_content (client_uuid, weapon, platform, content_type, '
            'title, body, image_url, hashtags, scheduled_at, status, created_at, topic_id) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()), 'kit_world', platform, 'image', title, cap[:900],
             image_url, '#KIT #GlowveilHollow #AIart', now, 'approved', now,
             title[:160]))
        ids.append(cur.lastrowid)
        print('  queue %-10s %-6s — %s' % (platform, 'image', why[:100]))
    con.commit()
    con.close()
    return ids, plan, cap


def _create_pod(creation, card_path):
    """Create and publish one real poster. Returns (product_id, url) or (None, '')."""
    try:
        from shared import printify as pf
        shop = pf.shop_by_channel('storefront')
        if not shop:
            print('POD: no storefront shop')
            return None, ''
        bp, prov, variants = pf.catalog('Satin Posters')
        if not bp or not prov or not variants:
            print('POD: poster blueprint unavailable')
            return None, ''
        with open(card_path, 'rb') as f:
            up = pf.upload_bytes(f.read(), name='kit_%s.png'
                                 % re.sub(r'[^A-Za-z0-9_-]', '_',
                                          str(creation.get('id') or 'creation')))
        image_id = (up or {}).get('id')
        if not image_id:
            print('POD: upload failed', str(up)[:200])
            return None, ''
        title = ('KIT’s Gallery — %s' % (creation.get('title') or 'a creation'))[:90]
        desc = ('A gallery card from KIT, the resident of Glowveil Hollow. '
                'KIT is a small garden-robot that chooses its own work; this is '
                'an abstract interpretation of “%s”. Printed on a satin poster.'
                % (creation.get('title') or creation.get('subject') or 'a creation'))
        prod = pf.create_product(shop, bp, prov, variants, image_id, title, desc,
                                 2499, ['kit', 'ai art', 'poster', 'glowveil hollow'])
        pid = (prod or {}).get('id')
        if not pid:
            print('POD: create failed', str(prod)[:200])
            return None, ''
        pf.publish(shop, pid)
        ext = (prod or {}).get('external') or {}
        url = ext.get('handle') or ('%s/product/%s' % (STORE, ext.get('id') or pid))
        pods = _load(PODS, [])
        pods.append({'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                     'creation_id': creation.get('id'), 'title': title,
                     'product_id': pid, 'url': url, 'price_cents': 2499})
        _save(PODS, pods[-100:])
        # stamp the creation record so the gallery can show a print link
        items = _load(CREATIONS, [])
        for c in items:
            if c.get('id') == creation.get('id'):
                c['pod_url'] = url
                c['pod_product_id'] = pid
        _save(CREATIONS, items)
        print('POD: published', pid, url)
        return pid, url
    except Exception as e:
        print('POD failed:', str(e)[:240])
        return None, ''


def _today():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--creation', default='')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--pod', action='store_true')
    a = ap.parse_args()
    creations = _load(CREATIONS, [])
    state = _load(STATE, {})
    shared = set(_load(SHARED, []))
    day = _load(DAYFILE, {})
    if day.get('day') != _today():
        day = {'day': _today(), 'count': 0}
    if a.creation:
        c = next((x for x in creations if x.get('id') == a.creation), None)
        if not c:
            print('no such creation:', a.creation)
            return 1
    elif a.scan:
        if int(day.get('count') or 0) >= 2:
            print('daily creation-share cap reached (2)')
            return 0
        fresh = [x for x in creations
                 if x.get('id') not in shared and int(x.get('level') or 0) >= 3]
        if not fresh:
            print('nothing new to share')
            return 0
        c = max(fresh, key=lambda x: str(x.get('at') or ''))
    else:
        print('use --scan or --creation <id>')
        return 1

    print('creation:', c.get('id'), '|', c.get('title'), '| level', c.get('level'))
    card = make_card(c, state)
    print('card:', card, os.path.getsize(card), 'bytes')
    url = PUBLIC + os.path.basename(card)
    if a.dry:
        print('image url:', url)
        print('caption:', _caption(c, state))
        return 0

    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            if r.status != 200:
                print('image not served:', r.status, url)
                return 1
    except Exception as e:
        print('image not served:', e, url)
        return 1

    pod_url = ''
    if a.pod:
        _pid, pod_url = _create_pod(c, card)
    ids, plan, cap = _queue(c, url, state, pod_url)
    shared.add(c.get('id'))
    _save(SHARED, sorted(shared))
    day['count'] = int(day.get('count') or 0) + 1
    _save(DAYFILE, day)
    print('queued rows:', ids)
    print('image:', url)
    if pod_url:
        print('pod:', pod_url)
    print('caption:', cap)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
