#!/usr/bin/env python3
"""kit_study.py — KIT's field-note loop.

A safe tool loop, not arbitrary code: choose a curiosity, read a Wikipedia
summary, ask the free writing chain for a first-person field note, save it, and
tell the live state. One note per run.

Run: venv/bin/python weapons/world/kit_study.py [--topic TOPIC] [--dry]
"""
import argparse
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

B = '/home/ubuntu/braxis-2.0'
STATE = os.path.join(B, 'data', 'world', 'world_life.json')
NOTES = os.path.join(B, 'data', 'world', 'kit_field_notes.jsonl')
UA = 'BraxisKit/1.0 (field notes; https://braxisai.com/world/)'
API = 'http://127.0.0.1:8130/api/world/field-note'


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj) + '\n')


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _summary(topic):
    slug = urllib.parse.quote(str(topic).replace(' ', '_'))
    try:
        d = _get_json('https://en.wikipedia.org/api/rest_v1/page/summary/' + slug)
        if d.get('extract'):
            return (d.get('title') or topic, d.get('extract'),
                    d.get('content_urls', {}).get('desktop', {}).get('page')
                    or ('https://en.wikipedia.org/wiki/' + slug))
    except Exception:
        pass
    try:
        q = urllib.parse.quote(str(topic))
        d = _get_json('https://en.wikipedia.org/w/api.php?action=query&list=search'
                      '&srsearch=%s&format=json&srlimit=1' % q)
        title = ((d.get('query') or {}).get('search') or [{}])[0].get('title')
        if title:
            return _summary(title)
    except Exception:
        pass
    return '', '', ''


def _clean(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text[:900]


def _write_note(topic, title, excerpt, url):
    prompt = (
        'You are KIT, a small garden-robot in a 3D world. You just read this '
        'Wikipedia summary about "%s" (source: %s).\n\n%s\n\n'
        'Return exactly three short lines, no markdown:\n'
        'NOTE: 2-3 plain first-person sentences about what you learned.\n'
        'SURPRISE: one sentence about what surprised you.\n'
        'QUESTION: one question you want to follow next.' % (topic, title, excerpt)
    )
    text = ''
    try:
        from shared import kit_llm
        r = kit_llm.call(prompt, max_tokens=260, temperature=0.8)
        if r.get('ok'):
            text = r.get('content') or ''
            print('model:', r.get('model'), 'remaining:', r.get('remaining'))
        else:
            print('kit_llm failed:', str(r.get('error'))[:120])
    except Exception as e:
        print('kit_llm exception:', str(e)[:160])
    if not text:
        try:
            from shared.llm_router import call_llm
            r = call_llm(prompt, system_prompt=(
                'You are the curious part of KIT. Concrete, first person, no hype, '
                'no invented facts. Only use the supplied summary.'),
                temperature=0.8, max_tokens=240, task='writing')
            text = r.get('content') or r.get('text') if isinstance(r, dict) else str(r)
        except Exception as e:
            print('router failed:', str(e)[:160])
    note, surprise, question = '', '', ''
    for line in str(text or '').splitlines():
        line = line.strip()
        if re.match(r'^NOTE\s*:', line, re.I):
            note = re.sub(r'^NOTE\s*:\s*', '', line, flags=re.I)
        elif re.match(r'^SURPRISE\s*:', line, re.I):
            surprise = re.sub(r'^SURPRISE\s*:\s*', '', line, flags=re.I)
        elif re.match(r'^QUESTION\s*:', line, re.I):
            question = re.sub(r'^QUESTION\s*:\s*', '', line, flags=re.I)
    if not note:
        note = _clean(text)[:500] if text else excerpt[:280]
    return {'note': _clean(note), 'surprise': _clean(surprise),
            'question': _clean(question)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--topic', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    st = _load(STATE, {})
    topic = a.topic.strip()
    if not topic:
        topic = str(st.get('browse_topic') or '').strip()
    if not topic:
        recent = set()
        try:
            with open(NOTES, encoding='utf-8') as f:
                for line in f:
                    try:
                        recent.add(str(json.loads(line).get('topic', '')).lower())
                    except Exception:
                        pass
        except Exception:
            pass
        cands = []
        for it in (st.get('interests') or []):
            t = str(it.get('text') or '').strip()
            if (3 <= len(t) <= 48 and t.lower() not in recent
                    and not t.lower().startswith(('how ', 'someone ', 'what '))):
                cands.append(t)
        for s in (st.get('subjects') or []):
            s = str(s or '').strip()
            if 3 <= len(s) <= 40 and s.lower() not in recent:
                cands.append(s)
        topic = cands[0] if cands else 'mycology'
    title, excerpt, url = _summary(topic)
    if not excerpt:
        print('no source for', topic)
        return 1
    print('topic:', topic, '| title:', title, '|', url)
    print('excerpt:', excerpt[:220])
    if a.dry:
        return 0
    parts = _write_note(topic, title, excerpt, url)
    rec = {'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'topic': topic, 'title': title, 'url': url,
           'excerpt': excerpt[:700], **parts}
    _append(NOTES, rec)
    try:
        body = json.dumps(rec).encode('utf-8')
        req = urllib.request.Request(API, data=body,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
        with urllib.request.urlopen(req, timeout=15) as r:
            print('state:', r.read().decode()[:160])
    except Exception as e:
        print('state post failed:', str(e)[:160])
    print('NOTE:', parts['note'][:300])
    print('QUESTION:', parts['question'][:200])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
