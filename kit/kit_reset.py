#!/usr/bin/env python3
"""kit_reset.py — archive KIT's life and start a fresh one.

A normal reset keeps the authored starting blueprints (garden row, bench,
lantern), so KIT will still choose one of those three first. A **blank slate**
removes them: the first project must be one KIT writes in its own reflection,
compiled into a custom schema. That is the real test of option generation.

Nothing is deleted. Everything is copied to data/world/kit_life_<ts>/ first.

Usage:
  ./venv/bin/python weapons/world/kit_reset.py --blank --keep-identity --yes
  ./venv/bin/python weapons/world/kit_reset.py --yes
  ./venv/bin/python weapons/world/kit_reset.py            # plan only
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

B = '/home/ubuntu/braxis-2.0'
sys.path.insert(0, B)
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
BUILDS = os.path.join(B, 'data', 'world', 'world_builds.json')
FILES = [
    'world_life.json', 'world_life_memory.jsonl', 'world_life_journal.md',
    'world_builds.json', 'world_creations.json', 'kit_mailbox.jsonl',
    'trio_replies.jsonl', 'kit_telegram.json', 'world_offerings.jsonl',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blank', action='store_true',
                    help='no starting blueprints; only self-invented projects')
    ap.add_argument('--keep-identity', action='store_true',
                    help='keep the name, pronouns, gender, world name and tagline')
    ap.add_argument('--restore', default='',
                    help='restore a previous data/world/kit_life_* archive')
    ap.add_argument('--soft', action='store_true',
                    help='blank slate of OPTIONS while keeping a curated set of builds')
    ap.add_argument('--keep-per-kind', type=int, default=2,
                    help='when --soft, keep this many of each repeated kind (default 2)')
    ap.add_argument('--remove-kind', default='',
                    help='comma-separated build kinds to remove, keeping everything else')
    ap.add_argument('--yes', action='store_true', help='actually do it')
    a = ap.parse_args()
    if a.restore:
        src = os.path.expanduser(a.restore)
        print('restore from', src)
        if not a.yes:
            print('plan only. add --yes to restore.')
            return 0
        subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'braxis-world-life'], check=False)
        for name in FILES:
            p = os.path.join(src, name)
            if os.path.exists(p):
                shutil.copy2(p, os.path.join(B, 'data', 'world', name))
        subprocess.run(['sudo', '-n', 'systemctl', 'start', 'braxis-world-life'], check=False)
        print('restored', src)
        return 0
    if a.soft:
        try:
            builds = json.load(open(BUILDS, encoding='utf-8'))
        except Exception:
            builds = []
        thin_kinds = {'bench', 'lantern', 'garden_plot', 'fountain'}
        groups = {}
        keep = []
        for b in builds:
            k = b.get('kind')
            if k in thin_kinds:
                groups.setdefault(k, []).append(b)
            else:
                keep.append(b)
        for k, rows in groups.items():
            rows.sort(key=lambda b: (b.get('level') or 0, b.get('built_at') or ''), reverse=True)
            keep.extend(rows[:max(0, a.keep_per_kind)])
        keep_ids = {id(b) for b in keep}
        removed = [b for b in builds if id(b) not in keep_ids]
        print('soft reset | builds:', len(builds), '->', len(keep),
              '(thin %d repeated)' % len(removed))
        if not a.yes:
            print('plan only. add --yes to do it.')
            return 0
        ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        archive = os.path.join(B, 'data', 'world', 'kit_life_%s' % ts)
        subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'braxis-world-life'], check=False)
        os.makedirs(archive, exist_ok=True)
        for name in FILES:
            srcp = os.path.join(B, 'data', 'world', name)
            if os.path.exists(srcp):
                shutil.copy2(srcp, os.path.join(archive, name))
        json.dump(keep, open(BUILDS, 'w', encoding='utf-8'), indent=1)
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {}
        st['blueprints'] = []
        st['custom_projects'] = []
        st['blank_slate'] = True
        st['project'] = None
        st['last_reflection'] = 0
        st['recent_project_kinds'] = []
        st['builds'] = len(keep)
        st['last_build'] = keep[-1] if keep else None
        st.setdefault('recent', []).insert(
            0, 'I thinned the town and I am starting with a blank slate; the choice is mine now.')
        st['recent'] = st['recent'][:6]
        st.setdefault('decisions', []).append({
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'kind': 'blank-slate',
            'text': 'I kept a few of my old things and will invent the next ones myself.'})
        json.dump(st, open(STATE, 'w', encoding='utf-8'), indent=1)
        subprocess.run(['sudo', '-n', 'systemctl', 'start', 'braxis-world-life'], check=False)
        print('soft reset done; %d builds remain; archive %s' % (len(keep), archive))
        return 0
    if a.remove_kind:
        kinds = {k.strip() for k in a.remove_kind.split(',') if k.strip()}
        try:
            builds = json.load(open(BUILDS, encoding='utf-8'))
        except Exception:
            builds = []
        keep = [b for b in builds if b.get('kind') not in kinds]
        removed = len(builds) - len(keep)
        print('remove kinds:', sorted(kinds), '| builds:', len(builds),
              '->', len(keep), '(remove %d)' % removed)
        if not a.yes:
            print('plan only. add --yes to do it.')
            return 0
        ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        archive = os.path.join(B, 'data', 'world', 'kit_life_%s' % ts)
        subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'braxis-world-life'], check=False)
        os.makedirs(archive, exist_ok=True)
        for name in FILES:
            srcp = os.path.join(B, 'data', 'world', name)
            if os.path.exists(srcp):
                shutil.copy2(srcp, os.path.join(archive, name))
        json.dump(keep, open(BUILDS, 'w', encoding='utf-8'), indent=1)
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {}
        st['blueprints'] = [b for b in (st.get('blueprints') or []) if b not in kinds]
        for k in list((st.get('skills') or {})):
            if k in kinds:
                st['skills'].pop(k, None)
        st['builds'] = len(keep)
        if (st.get('project') or {}).get('kind') in kinds:
            st['project'] = None
        st['custom_projects'] = [c for c in (st.get('custom_projects') or [])
                                 if c.get('kind') not in kinds]
        if (st.get('last_build') or {}).get('kind') in kinds:
            st['last_build'] = keep[-1] if keep else None
        st.setdefault('recent', []).insert(
            0, 'I cleared the %s; I was repeating myself.' % ', '.join(sorted(kinds)))
        st['recent'] = st['recent'][:6]
        st.setdefault('decisions', []).append({
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'kind': 'cleanup',
            'text': 'I removed %s from my town; I was repeating myself.' % ', '.join(sorted(kinds))})
        json.dump(st, open(STATE, 'w', encoding='utf-8'), indent=1)
        subprocess.run(['sudo', '-n', 'systemctl', 'start', 'braxis-world-life'], check=False)
        print('removed %d; %d builds remain; archive %s' % (removed, len(keep), archive))
        return 0
    old = {}
    try:
        old = json.load(open(STATE, encoding='utf-8'))
    except Exception:
        pass
    ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = os.path.join(B, 'data', 'world', 'kit_life_%s' % ts)
    print('archive ->', archive)
    print('mode:', 'BLANK SLATE' if a.blank else 'normal reset',
          '| keep identity:', a.keep_identity)
    if not a.yes:
        print('plan only. add --yes to do it.')
        return 0
    subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'braxis-world-life'], check=False)
    os.makedirs(archive, exist_ok=True)
    for name in FILES:
        src = os.path.join(B, 'data', 'world', name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(archive, name))
    from weapons.world import world_life as w
    fresh = w._default_state()
    if a.keep_identity:
        for k in ('name', 'pronouns', 'gender', 'world_name', 'tagline'):
            if old.get(k):
                fresh[k] = old[k]
        fresh['last_identity'] = old.get('last_identity') or 0
        fresh['last_rename'] = old.get('last_rename') or 0
    if a.blank:
        fresh['blueprints'] = []
        fresh['custom_projects'] = []
        fresh['blank_slate'] = True
        fresh['last_reflection'] = 0
        fresh['last_identity'] = 0
        fresh['last_rename'] = 0
    json.dump(fresh, open(STATE, 'w', encoding='utf-8'), indent=1)
    for name in ('world_builds.json', 'world_creations.json'):
        json.dump([], open(os.path.join(B, 'data', 'world', name), 'w', encoding='utf-8'))
    subprocess.run(['sudo', '-n', 'systemctl', 'start', 'braxis-world-life'], check=False)
    print('fresh life started. old life archived at', archive)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
