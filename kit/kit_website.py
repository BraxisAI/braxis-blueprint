#!/usr/bin/env python3
"""kit_website.py — let KIT make a small static web page.

The page is one self-contained HTML file with inline CSS. No JavaScript, no
forms, no external assets, no server-side code: it is a poster, not an app.
That keeps a KIT-authored page safe to serve from the same host.
"""
import datetime
import html as _html
import os
import re
import time

B = '/home/ubuntu/braxis-2.0'
WWW = '/var/www/braxis/world/made'


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _fallback(goal):
    title = _html.escape(str(goal or 'a small page')[:80])
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>
body{margin:0;background:#0b0e16;color:#e6e8ee;font:16px/1.65 ui-sans-serif,system-ui,sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:28px}
main{max-width:620px;border-left:3px solid #d7b8ff;padding:6px 0 6px 22px}
h1{font-size:34px;margin:0 0 10px;color:#d7b8ff;letter-spacing:.02em}
p{color:#c8cedb;margin:10px 0}
.small{color:#8d94a6;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
</style></head>
<body><main>
<div class="small">a page KIT made in Glowveil Hollow</div>
<h1>%s</h1>
<p>This is a small place on the web, made by the resident of Glowveil Hollow.</p>
<p>The hollow is at <a href="/world/" style="color:#7dd3a8">braxisai.com/world</a>.</p>
</main></body></html>""" % (title, title)


def _sanitize(raw):
    """Allow static HTML/CSS only. Strip scripts, frames, forms and every
    external URL; a KIT page must not phone home or run code."""
    s = str(raw or '')
    s = re.sub(r'(?is)<(script|iframe|object|embed|form|link|base)\b[^>]*>.*?</\1\s*>', '', s)
    s = re.sub(r'(?is)<(script|iframe|object|embed|form|link|base)\b[^>]*/?>', '', s)
    s = re.sub(r'(?i)\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', s)
    s = re.sub(r'(?i)javascript\s*:', '', s)
    s = re.sub(r'(?i)https?://[^\s"\'<>]+', '#', s)
    s = re.sub(r'(?i)@import[^;]+;', '', s)
    return s.strip()


def _extract_html(raw):
    s = str(raw or '').strip()
    s = re.sub(r'^```(?:html)?\s*', '', s, flags=re.I)
    s = re.sub(r'\s*```$', '', s)
    m = re.search(r'(?is)<!doctype html.*</html>|<html.*</html>', s)
    return m.group(0) if m else s


def make(goal, model=''):
    """Generate one static page. Returns {ok,id,url,html,model,error}."""
    goal = str(goal or 'a small page about the hollow')[:200]
    prompt = (
        "You are KIT, a small AI resident who lives in a 3D world called "
        "Glowveil Hollow. Make one complete, self-contained HTML page about: %s.\n\n"
        "Rules: one file; inline CSS in a <style> tag; NO JavaScript, NO forms, "
        "NO external images, fonts, links or network requests; no invented "
        "statistics, quotes or claims. It should feel handmade: a clear title, "
        "a short intro, and 3-5 small sections or a simple visual made of CSS. "
        "Dark background, warm violet/green accents. Return ONLY the HTML "
        "document, starting with <!doctype html>." % goal)
    raw = ''
    try:
        from shared import kit_llm
        r = kit_llm.call(prompt, max_tokens=2200, temperature=.7)
        if r.get('ok'):
            raw = str(r.get('content') or '')
            model = str(r.get('model') or 'kit_llm')
    except Exception:
        pass
    if not raw:
        try:
            from shared.llm_router import call_llm
            r = call_llm(prompt, task='writing', max_tokens=2200, temperature=.7)
            raw = str((r or {}).get('content') or '')
            model = str((r or {}).get('model') or 'router')
        except Exception:
            raw = ''
    page = _sanitize(_extract_html(raw)) if raw else ''
    if len(page) < 300 or '<body' not in page.lower():
        page = _fallback(goal)
        model = model or 'fallback'
    cid = 'web-%d-%d' % (int(time.time()), abs(hash(goal)) % 10000)
    out = os.path.join(WWW, cid)
    try:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        os.chmod(out, 0o755)
        os.chmod(os.path.join(out, 'index.html'), 0o644)
    except Exception as e:
        return {'ok': False, 'error': '%s: %s' % (type(e).__name__, str(e)[:160])}
    return {'ok': True, 'id': cid, 'url': 'https://braxisai.com/world/made/%s/' % cid,
            'html': page, 'model': model, 'made': _now()}
