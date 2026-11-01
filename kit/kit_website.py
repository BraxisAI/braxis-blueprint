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


def _log(msg):
    try:
        with open(os.path.join(B, 'logs', 'kit_website.log'), 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (_now(), msg))
    except Exception:
        pass


def _fallback(goal):
    title = _html.escape(str(goal or 'a small page')[:80])
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>
:root{--ink:#e6e8ee;--muted:#9aa1b2;--violet:#d7b8ff;--green:#7dd3a8;--gold:#ffb057}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 20%% 10%%,#1b1630 0,#0b0e16 55%%);color:var(--ink);
font:16px/1.7 ui-sans-serif,system-ui,-apple-system,sans-serif;padding:48px 22px 72px}
main{max-width:720px;margin:0 auto}
.kicker{color:var(--green);font-size:11px;letter-spacing:.18em;text-transform:uppercase}
h1{font-size:clamp(32px,6vw,54px);line-height:1.05;margin:12px 0 18px;color:var(--violet);letter-spacing:-.02em}
.lede{font-size:18px;color:#c8cedb;max-width:560px}
.orb{width:110px;height:110px;border-radius:50%%;margin:26px 0 30px;
background:radial-gradient(circle at 35%% 30%%,#ffe9b0,#d7b8ff 42%%,#3b2a66 75%%);
box-shadow:0 0 60px rgba(215,184,255,.28)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}
.card{border:1px solid rgba(215,184,255,.18);border-radius:12px;padding:15px;background:rgba(255,255,255,.025)}
.card b{display:block;color:var(--gold);font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px}
.card p{margin:0;color:#c2c9d6;font-size:14px}
.foot{margin-top:32px;padding-top:16px;border-top:1px solid rgba(255,255,255,.08);color:var(--muted);font-size:13px}
a{color:var(--green);text-decoration:none}a:hover{text-decoration:underline}
@media(max-width:620px){.grid{grid-template-columns:1fr}}
</style></head>
<body><main>
<div class="kicker">a page KIT made in Glowveil Hollow</div>
<h1>%s</h1>
<p class="lede">A small place on the web, kept by the resident of Glowveil Hollow. It is handwritten, not a feed.</p>
<div class="orb"></div>
<div class="grid">
  <div class="card"><b>what this is</b><p>A page about one thing KIT is thinking about, made to be read slowly.</p></div>
  <div class="card"><b>what to notice</b><p>The quiet parts: the edge of the light, the shape of a path, the thing that is almost a door.</p></div>
  <div class="card"><b>leave a mark</b><p>Tell KIT what you would add. The hollow is at <a href="/world/">/world/</a>.</p></div>
</div>
<p class="foot">Made by KIT. No trackers, no scripts, no feed. <a href="/world/">Visit the hollow →</a></p>
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
    _log('goal=%r model=%s raw=%d page=%d' % (goal[:80], model, len(raw), len(page)))
    if len(page) < 300 or '<body' not in page.lower():
        page = _fallback(goal)
        model = model or 'fallback'
        _log('using fallback for %r' % goal[:80])
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
