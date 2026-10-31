#!/usr/bin/env python3
"""kit_watch_vm.py — KIT's eyes, on the VM.

The estate watch chain was built for YouTube: the PC fetches from a residential
IP, then the VM watches the file. KIT's first two requests were TikTok, and they
sat in the queue because the PC lane only drains twice a day. But the VM's
yt-dlp can fetch TikTok directly (verified: 1.2 MB, 38s). This worker uses that
path, watches one video with the local `watch-skill`, and posts the result back
to KIT's state through /api/world/watch-result.

YouTube is different: the VM is bot-walled, so a YouTube item is watched only
if the PC already pushed its file into data/watch_inbox/<id>.mp4.

Run: venv/bin/python weapons/world/kit_watch_vm.py [--force]
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

B = '/home/ubuntu/braxis-2.0'
INBOX = os.path.join(B, 'data', 'watch_inbox')
WATCHLIST = os.path.join(B, 'data', 'world', 'kit_watchlist.json')
WATCHED = os.path.join(B, 'data', 'watched_videos.json')
SEEN = os.path.join(B, 'data', 'world', 'kit_watch_vm_seen.json')
YTDLP = os.path.join(B, 'venv', 'bin', 'yt-dlp')
PY = os.path.join(B, 'venv', 'bin', 'python')
ASK = ('What is in this video, in plain concrete detail, and what could a '
       'small robot gardener who lives in a 3D world take from it?')

TT = re.compile(r'tiktok\.com/@[^/]+/video/(\d+)')
YT = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))([\w-]{6,})')


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _id(url):
    m = TT.search(str(url or ''))
    if m:
        return 'tt' + m.group(1)
    m = YT.search(str(url or ''))
    return m.group(1) if m else ''


def _watch_entry(path):
    for f in reversed(_load(WATCHED, [])):
        if str(f.get('file') or '') == path:
            text = (str(f.get('answer') or '').strip()
                    or str(f.get('insight') or '').strip()
                    or str(f.get('transcript') or '').strip())
            if 'closest indexed moments are:' in text:
                text = ('Indexed moments from the video:' +
                        text.split('closest indexed moments are:', 1)[1]
                        .split('If the answer should be visible', 1)[0].strip())
            if text:
                return text[:1500]
    return ''


def _download(url, path):
    os.makedirs(INBOX, exist_ok=True)
    cmd = [YTDLP, '-f', 'mp4', '-o', path, '--no-playlist',
           '--no-warnings', url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError((r.stderr or r.stdout or 'download failed')[-300:])


def _watch(path):
    r = subprocess.run([PY, os.path.join(B, 'weapons', 'watch_video.py'),
                        '--file', path, '--ask', ASK],
                       cwd=B, capture_output=True, text=True, timeout=480)
    text = _watch_entry(path)
    if not text:
        raise RuntimeError((r.stderr or r.stdout or 'watch failed')[-300:])
    return text


def _post(rec):
    body = json.dumps(rec).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8130/api/world/watch-result', data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main(force=False):
    state = {}
    try:
        with urllib.request.urlopen('http://127.0.0.1:8130/api/world/state',
                                    timeout=10) as r:
            state = json.load(r)
    except Exception:
        pass
    items = _load(WATCHLIST, [])
    if not isinstance(items, list):
        items = []
    last = state.get('last_watch') or {}
    candidates = []
    if last.get('url') and not last.get('result'):
        candidates.append({'url': last['url'], 'title': last.get('title') or ''})
    candidates += [x for x in items if isinstance(x, dict) and x.get('url')]
    seen = _load(SEEN, {})
    if not isinstance(seen, dict):
        seen = {}
    for item in candidates:
        url = str(item.get('url') or '')
        vid = _id(url)
        if not vid:
            continue
        title = str(item.get('title') or vid)
        path = os.path.join(INBOX, vid + '.mp4')
        is_tiktok = bool(TT.search(url))
        if not os.path.exists(path) and is_tiktok:
            print('fetch', vid, title[:70], flush=True)
            try:
                _download(url, path)
            except Exception as e:
                print('  download failed:', str(e)[:200], flush=True)
                continue
        if not os.path.exists(path):
            print('skip (no local file, PC/YouTube lane):', vid, flush=True)
            continue
        old = seen.get(vid) or {}
        if not force and old.get('posted'):
            continue
        text = _watch_entry(path)
        if not text:
            print('watch', vid, title[:70], flush=True)
            try:
                text = _watch(path)
            except Exception as e:
                seen[vid] = {'ts': time.time(), 'error': str(e)[:240]}
                _save(SEEN, seen)
                print('  watch failed:', str(e)[:220], flush=True)
                continue
        rec = {'id': vid, 'title': title, 'url': url, 'result': text}
        try:
            _post(rec)
        except Exception as e:
            print('  post failed:', str(e)[:200], flush=True)
            continue
        seen[vid] = {'ts': time.time(), 'posted': True, 'title': title}
        _save(SEEN, seen)
        print('posted', vid, title[:70], flush=True)
        return 0
    print('no eligible watch item', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main('--force' in sys.argv))
