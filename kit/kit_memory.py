#!/usr/bin/env python3
"""kit_memory.py — KIT's local episodic memory, searchable with SQLite FTS5.

It indexes the meaningful records that already exist (decisions, projects,
creations, builds, companion dialogue, watch results, wonders, field notes).
No embeddings, no network, no model call. `ensure()` rebuilds when the DB is
missing; `search()` is used by the daily reflection and the dashboard.

Run: venv/bin/python weapons/world/kit_memory.py --rebuild
     venv/bin/python weapons/world/kit_memory.py --search "trains"
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3

B = '/home/ubuntu/braxis-2.0'
DB = os.path.join(B, 'data', 'world', 'kit_memory.db')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
CREATIONS = os.path.join(B, 'data', 'world', 'world_creations.json')
BUILDS = os.path.join(B, 'data', 'world', 'world_builds.json')
NOTES = os.path.join(B, 'data', 'world', 'kit_field_notes.jsonl')


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB, timeout=20)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)')
    try:
        con.execute('CREATE VIRTUAL TABLE IF NOT EXISTS memories USING fts5('
                    'kind, text, ts UNINDEXED, ref UNINDEXED)')
    except sqlite3.OperationalError:
        # Fallback for a SQLite build without FTS5.
        con.execute('CREATE TABLE IF NOT EXISTS memories '
                    '(kind TEXT, text TEXT, ts TEXT, ref TEXT)')
    return con


def _add(con, kind, text, ts='', ref=''):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if len(text) < 3:
        return
    con.execute('INSERT INTO memories(kind, text, ts, ref) VALUES (?,?,?,?)',
                (str(kind)[:40], text[:4000], str(ts)[:40], str(ref)[:200]))


def rebuild():
    st = _load(STATE, {})
    creations = _load(CREATIONS, [])
    builds = _load(BUILDS, [])
    con = _conn()
    con.execute('DELETE FROM memories')
    for d in (st.get('decisions') or [])[-120:]:
        _add(con, 'decision', d.get('text'), d.get('ts'), d.get('kind'))
    for p in (st.get('projects_done') or [])[-60:]:
        _add(con, 'project', '%s — %s' % (p.get('name'), p.get('why') or p.get('relabel') or ''),
             p.get('ts'), p.get('build_id'))
    for b in builds[-80:]:
        _add(con, 'build', '%s at %s — %s' % (b.get('name'), b.get('site') or 'the edge',
                                                b.get('why') or ''), b.get('built_at'), b.get('id'))
    for c in creations[-120:]:
        text = c.get('text') or '%s — %s (%s)' % (
            c.get('title') or '', c.get('subject') or '', c.get('medium') or '')
        _add(con, 'creation', text, c.get('at'), c.get('id'))
    for x in (st.get('companion_dialog') or [])[-60:]:
        _add(con, 'companion', 'KIT: %s | %s: %s' % (
            x.get('kit'), (st.get('companion') or {}).get('name') or 'Juniper',
            x.get('juniper')), x.get('ts'), 'companion')
    for x in (st.get('watch_results') or [])[-20:]:
        _add(con, 'watch', '%s — %s' % (x.get('title'), x.get('result') or ''),
             x.get('ts'), x.get('id'))
    for w in (st.get('wonders') or [])[-60:]:
        _add(con, 'wonder', w.get('text'), w.get('ts'), 'wonder')
    if os.path.exists(NOTES):
        try:
            with open(NOTES, encoding='utf-8') as f:
                for line in f.read().splitlines()[-80:]:
                    try:
                        n = json.loads(line)
                    except Exception:
                        continue
                    _add(con, 'field note', '%s — %s %s' % (
                        n.get('topic'), n.get('note'), n.get('question') or ''),
                        n.get('ts'), n.get('url'))
        except Exception:
            pass
    con.commit()
    count = con.execute('SELECT count(*) FROM memories').fetchone()[0]
    con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES (?,?)',
                ('rebuilt', str(count)))
    con.commit()
    con.close()
    return count


def ensure():
    try:
        con = _conn()
        n = con.execute('SELECT count(*) FROM memories').fetchone()[0]
        con.close()
        if n == 0:
            return rebuild()
        # The state file changes every tick; rebuild when it is newer than the
        # index so new decisions/dialogue are searchable immediately.
        try:
            if os.path.getmtime(STATE) > os.path.getmtime(DB) + 1:
                return rebuild()
        except Exception:
            pass
        return n
    except Exception:
        return 0


def search(query, limit=8):
    terms = re.findall(r'[a-z0-9]{2,}', str(query or '').lower())[:10]
    if not terms:
        return []
    ensure()
    con = _conn()
    fts = ' OR '.join('"%s"' % t for t in terms)
    try:
        rows = con.execute(
            'SELECT kind, text, ts, ref FROM memories WHERE memories MATCH ? '
            'ORDER BY rank LIMIT ?', (fts, max(1, int(limit)))).fetchall()
    except Exception:
        rows = []
    con.close()
    return [{'kind': r[0], 'text': r[1], 'ts': r[2], 'ref': r[3]} for r in rows]


def recent(limit=8):
    ensure()
    con = _conn()
    try:
        rows = con.execute(
            'SELECT kind, text, ts, ref FROM memories ORDER BY rowid DESC LIMIT ?',
            (max(1, int(limit)),)).fetchall()
    except Exception:
        rows = []
    con.close()
    return [{'kind': r[0], 'text': r[1], 'ts': r[2], 'ref': r[3]} for r in rows]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--search', default='')
    a = ap.parse_args()
    if a.rebuild:
        print('indexed', rebuild())
    elif a.search:
        for row in search(a.search, 12):
            print('[%s] %s' % (row['kind'], row['text'][:240]))
    else:
        print('memories', ensure())
