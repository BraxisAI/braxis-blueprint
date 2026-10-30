#!/usr/bin/env python3
"""kit_improver.py — one weekly, non-applied improvement proposal for KIT.

Reads the current gap list and a little public GitHub/arXiv signal, then writes
one concrete proposal to data/world/kit_improver.json and kit_watcher.json.
No LLM, no auto-apply.
"""
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

B = '/home/ubuntu/braxis-2.0'
WISH = os.path.join(B, 'data', 'world', 'kit_wishlist.json')
WATCH = os.path.join(B, 'data', 'world', 'kit_watcher.json')
OUT = os.path.join(B, 'data', 'world', 'kit_improver.json')
UA = {'User-Agent': 'BraxisKitImprover/1.0'}


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


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def github_signal():
    try:
        q = urllib.parse.quote('autonomous agent memory 3d world')
        data = json.loads(_get(
            'https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=5'
            % q).decode())
        rows = data.get('items') or []
        if rows:
            r = rows[0]
            return {'source': 'github', 'name': r.get('full_name'),
                    'url': r.get('html_url'), 'desc': (r.get('description') or '')[:180]}
    except Exception:
        pass
    return None


def arxiv_signal():
    try:
        url = ('http://export.arxiv.org/api/query?search_query=all:%s&start=0&max_results=3'
               % urllib.parse.quote('autonomous agents intrinsic motivation'))
        root = ET.fromstring(_get(url))
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        entry = root.find('a:entry', ns)
        if entry is not None:
            return {'source': 'arxiv',
                    'name': (entry.findtext('a:title', default='', namespaces=ns) or '').strip()[:160],
                    'url': (entry.findtext('a:id', default='', namespaces=ns) or '').strip(),
                    'desc': 'recent paper signal'}
    except Exception:
        pass
    return None


def main():
    wish = _load(WISH, {})
    gaps = [g for g in (wish.get('gaps') or []) if g.get('status') != 'live']
    gap = gaps[0] if gaps else {'id': 'none', 'what': 'keep the resident growing',
                               'how': 'observe the next week of journals'}
    sig = github_signal() or arxiv_signal() or {
        'source': 'local', 'name': 'the current journals',
        'url': '', 'desc': 'no public signal reached'}
    proposal = {
        'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'gap': gap.get('id'),
        'title': 'Try %s for %s' % (sig.get('name'), gap.get('id')),
        'why': 'The gap list still says: %s (%s)' % (
            gap.get('how') or gap.get('why') or '', gap.get('status')),
        'signal': sig,
        'experiment': ('One small, reversible change in world_life.py; run for 24h; '
                       'measure the gap status and the action entropy; revert if flat.'),
        'auto_apply': False,
    }
    _save(OUT, proposal)
    watch = _load(WATCH, {})
    recs = watch.get('recommendations') or []
    recs.append({'ts': proposal['ts'], 'text': proposal['title'],
                 'why': proposal['why'], 'auto_apply': False})
    watch['recommendations'] = recs[-10:]
    watch['improver_updated'] = proposal['ts']
    _save(WATCH, watch)
    print(json.dumps(proposal, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
