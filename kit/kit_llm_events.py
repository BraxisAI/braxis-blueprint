#!/usr/bin/env python3
"""kit_llm_events.py — turn high-value KIT events into short free-model notes.

The life loop only appends events. This script runs every five minutes, spends
up to three of KIT's shared daily free calls, and writes first-person summaries
that the next daily reflection reads.
"""
import datetime as dt
import json
import os

B = '/home/ubuntu/braxis-2.0'
QUEUE = os.path.join(B, 'data', 'world', 'kit_llm_events.jsonl')
CURSOR = os.path.join(B, 'data', 'world', 'kit_llm_events_cursor.json')
SUMMARIES = os.path.join(B, 'data', 'world', 'kit_event_summaries.jsonl')
STATE = os.path.join(B, 'data', 'world', 'world_life.json')


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
    from shared import kit_llm
    state = _load(STATE, {})
    try:
        lines = [l for l in open(QUEUE, encoding='utf-8').read().splitlines() if l.strip()]
    except Exception:
        lines = []
    cur = _load(CURSOR, {})
    offset = max(0, min(int(cur.get('offset') or 0), len(lines)))
    pending = lines[offset:]
    if not pending:
        print('no pending events')
        return 0
    done = 0
    for raw in pending[:3]:
        if kit_llm.remaining() <= 0:
            print('KIT daily LLM budget exhausted; events left queued')
            break
        try:
            ev = json.loads(raw)
        except Exception:
            offset += 1
            continue
        kind = str(ev.get('kind') or 'event')
        text = str(ev.get('text') or '')[:500]
        prompt = (
            'You are %s, the resident of %s. In one or two first-person sentences, '
            'say what this %s event means to you and what you want to do next. '
            'No markdown, no lists, no quotes around the whole answer.\n\nEvent: %s'
            % (state.get('name') or 'Kit', state.get('world_name') or 'the world',
               kind, text)
        )
        r = kit_llm.call(prompt, max_tokens=150, temperature=0.75)
        if not r.get('ok'):
            print('event call failed:', r.get('error'))
            break
        summary = str(r.get('content') or '').strip()[:500]
        with open(SUMMARIES, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'kind': kind, 'event': text, 'summary': summary,
                'model': r.get('model')}) + '\n')
        offset += 1
        done += 1
        print('event', kind, '->', summary[:120])
    _save(CURSOR, {'offset': offset, 'updated': dt.datetime.now(
        dt.timezone.utc).isoformat(timespec='seconds')})
    print('processed', done, 'offset', offset, 'budget left', kit_llm.remaining())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
