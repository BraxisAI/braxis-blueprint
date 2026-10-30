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
    ap.add_argument('--yes', action='store_true', help='actually do it')
    a = ap.parse_args()
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
