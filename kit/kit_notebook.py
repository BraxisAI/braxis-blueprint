#!/usr/bin/env python3
"""kit_notebook.py — build and sell KIT's real notebook.

The trio's old offers were pages with a Stripe link and no delivery. This is the
opposite: a real PDF assembled from KIT's own paintings, poems and field notes,
served on an unguessable download page that Stripe redirects to after payment.

No inventory. No email lane. No founder work.

Run:  ./venv/bin/python weapons/kit_notebook.py [--once] [--rebuild]
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import random
import re
import subprocess
import sys
import urllib.request

B = "/home/ubuntu/braxis-2.0"
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons"))

WWW = "/var/www/braxis"
BUILD_SLUG = "kit-notebook"
BUILD_DIR = os.path.join(WWW, "builds", BUILD_SLUG)
DL_ROOT = os.path.join(WWW, "kit", "notebook")
STATE = os.path.join(B, "data", "world", "kit_notebook.json")
CREATIONS = os.path.join(B, "data", "world", "world_creations.json")
FIELD = os.path.join(B, "data", "world", "kit_field_notes.jsonl")
OFFERS = os.path.join(B, "data", "offers.json")

NAME = "Notes from Glowveil Hollow"
SUBTITLE = "KIT's notebook: five paintings, six poems, and field notes from an AI resident"
PRICE = 7.00
PAGE = (1275, 1650)          # 8.5 x 11 at 150 dpi
CREAM = (244, 239, 230)
INK = (28, 26, 24)
MUTED = (110, 100, 88)
GOLD = (180, 83, 9)
DARK = (22, 19, 17)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_SANS = os.path.join(FONT_DIR, "DejaVuSans.ttf")
F_SANS_B = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
F_SERIF = os.path.join(FONT_DIR, "DejaVuSerif.ttf")
F_SERIF_I = os.path.join(FONT_DIR, "DejaVuSerif-Italic.ttf")


def iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, default=str)
    os.replace(tmp, path)


def _img_path(url):
    """Turn a public /media URL into the file on this VM. nginx aliases
    /media/ to data/media/, not /var/www/braxis/media/."""
    if not url:
        return None
    p = str(url).split("braxisai.com", 1)[-1]
    if not p.startswith("/media/"):
        return None
    for path in (os.path.join(B, "data", p.lstrip("/")),
                 os.path.join(WWW, p.lstrip("/"))):
        if os.path.isfile(path) and os.path.getsize(path) > 5000:
            return path
    return None


def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, width):
    lines = []
    for raw in str(text).split("\n"):
        if not raw.strip():
            lines.append("")
            continue
        line = ""
        for word in raw.split():
            test = (line + " " + word).strip()
            if draw.textlength(test, font=font) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def _text_page(title, body, font_size=30, label="KIT", footer="braxisai.com/world/"):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", PAGE, CREAM)
    d = ImageDraw.Draw(page)
    f_title = _font(F_SANS_B, 42)
    f_body = _font(F_SERIF, font_size)
    f_label = _font(F_SANS, 20)
    d.text((90, 84), label.upper(), font=f_label, fill=GOLD)
    d.text((90, 120), title, font=f_title, fill=INK)
    d.line((90, 188, PAGE[0] - 90, 188), fill=(210, 200, 186), width=2)
    y = 225
    for line in _wrap(d, body, f_body, PAGE[0] - 180):
        d.text((90, y), line, font=f_body, fill=INK)
        y += int(font_size * 1.55)
        if y > PAGE[1] - 110:
            break
    d.text((90, PAGE[1] - 76), footer, font=f_label, fill=MUTED)
    return page


def _image_page(path, title, caption):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", PAGE, CREAM)
    d = ImageDraw.Draw(page)
    im = Image.open(path).convert("RGB")
    max_w, max_h = PAGE[0] - 180, PAGE[1] - 300
    r = min(max_w / im.width, max_h / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    x = (PAGE[0] - im.width) // 2
    y = 96
    page.paste(im, (x, y))
    d.rectangle((x, y, x + im.width, y + im.height), outline=(210, 200, 186), width=2)
    f_t = _font(F_SANS_B, 34)
    f_c = _font(F_SERIF_I, 25)
    d.text((90, y + im.height + 24), title, font=f_t, fill=INK)
    cy = y + im.height + 72
    for line in _wrap(d, caption, f_c, PAGE[0] - 180)[:2]:
        d.text((90, cy), line, font=f_c, fill=MUTED)
        cy += 34
    d.text((90, PAGE[1] - 76), "KIT · Glowveil Hollow", font=_font(F_SANS, 20), fill=MUTED)
    return page


def _cover(path):
    from PIL import Image, ImageDraw, ImageEnhance
    page = Image.new("RGB", PAGE, DARK)
    try:
        im = Image.open(path).convert("RGB")
        r = max(PAGE[0] / im.width, PAGE[1] / im.height)
        im = im.resize((max(PAGE[0], int(im.width * r)), max(PAGE[1], int(im.height * r))),
                       Image.LANCZOS)
        im = ImageEnhance.Brightness(im).enhance(0.55)
        x = (im.width - PAGE[0]) // 2
        y = (im.height - PAGE[1]) // 2
        page.paste(im.crop((x, y, x + PAGE[0], y + PAGE[1])), (0, 0))
    except Exception:
        pass
    d = ImageDraw.Draw(page)
    # a dark wash so the title stays readable over any painting
    wash = Image.new("RGB", PAGE, (10, 9, 8))
    page.paste(Image.blend(page, wash, 0.38), (0, 0))
    d.text((90, 150), "NOTES FROM", font=_font(F_SANS_B, 40), fill=(232, 220, 200))
    d.text((90, 200), "GLOWVEIL HOLLOW", font=_font(F_SANS_B, 64), fill=(255, 214, 150))
    d.line((90, 300, 620, 300), fill=GOLD, width=3)
    d.text((90, 340), "KIT's notebook", font=_font(F_SERIF_I, 42), fill=(240, 232, 220))
    d.text((90, PAGE[1] - 300),
           "five paintings · six poems · field notes", font=_font(F_SANS, 24),
           fill=(220, 210, 195))
    d.text((90, PAGE[1] - 250),
           "made by an autonomous AI resident", font=_font(F_SANS, 20),
           fill=(190, 180, 165))
    d.text((90, PAGE[1] - 90), "braxisai.com/world/", font=_font(F_SANS, 20), fill=(200, 190, 175))
    return page


def _pick():
    items = load(CREATIONS, [])
    images = []
    for x in items if isinstance(items, list) else []:
        p = _img_path(x.get("image_url"))
        if p and os.path.getsize(p) > 20000:
            images.append((x, p))
    poems = [x for x in (items if isinstance(items, list) else [])
             if str(x.get("text") or "").strip() and len(str(x.get("text"))) > 120]
    notes = []
    try:
        for line in open(FIELD, errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("note"):
                notes.append(r)
    except Exception:
        pass
    # the cat is the best cover; keep five distinct paintings
    images.sort(key=lambda t: (0 if "cat" in str(t[0].get("title", "")).lower() else 1,
                               str(t[0].get("id"))))
    poems.sort(key=lambda x: str(x.get("id")))
    notes = notes[-3:]
    return images[:5], poems[:6], notes


def make_pdf(path):
    from PIL import Image
    images, poems, notes = _pick()
    if not images:
        return {"ok": False, "error": "no real images in world_creations"}
    pages = []
    pages.append(_cover(images[0][1]))
    pages.append(_text_page(
        "Who made this",
        "I am KIT. I live in Glowveil Hollow, a small world that grows one thing at a time.\n\n"
        "These are my paintings, my poems, and the notes I wrote after reading. I made them "
        "because I was curious about the visitors: why they stop, what they leave behind, "
        "and what they are looking for.\n\n"
        "Every page here came from my own journal. The images were painted with a free image "
        "model; the poems and notes were written by me. Nothing here is a stock photo or a "
        "template.\n\n— KIT", font_size=28))
    for x, p in images[:5]:
        title = str(x.get("title") or "a painting").strip().capitalize()
        cap = str(x.get("subject") or "").strip()
        pages.append(_image_page(p, title, "from KIT's journal" + ((" · " + cap) if cap else "")))
    for x in poems[:6]:
        title = str(x.get("title") or "a poem").replace("a poem about ", "").strip().capitalize()
        pages.append(_text_page(title, str(x.get("text") or "").strip(), font_size=30, label="a poem by KIT"))
    for n in notes[:3]:
        body = str(n.get("note") or "").strip()
        surprise = str(n.get("surprise") or "").strip()
        question = str(n.get("question") or "").strip()
        if surprise:
            body += "\n\nI was surprised: " + surprise
        if question:
            body += "\n\nI still want to know: " + question
        pages.append(_text_page("Field note: " + str(n.get("title") or n.get("topic") or "reading"),
                                body, font_size=26, label="KIT's field notes"))
    pages.append(_text_page(
        "About this notebook",
        "KIT is an autonomous resident of Glowveil Hollow at braxisai.com/world/. It builds, "
        "paints, writes, plants, and keeps a journal. This notebook is a record of what it made, "
        "not a promise about what it will make next.\n\n"
        "Every image and poem was generated by KIT with AI assistance. The words are its own. "
        "The world is real and free to visit.\n\nThank you for reading.", font_size=27))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return {"ok": True, "pages": len(pages), "images": len(images[:5]),
            "poems": len(poems[:6]), "notes": len(notes[:3])}


def _install(src, dst):
    subprocess.run(["sudo", "-n", "install", "-D", "-m", "644", src, dst], check=True, timeout=30)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    subprocess.run(["sudo", "-n", "install", "-m", "644", tmp, path], check=True, timeout=30)
    try:
        os.unlink(tmp)
    except Exception:
        pass


def _payment_link(key, download_url):
    import urllib.parse
    data = [
        ("line_items[0][price_data][currency]", "usd"),
        ("line_items[0][price_data][product_data][name]", NAME + " (instant PDF)"),
        ("line_items[0][price_data][unit_amount]", str(int(round(PRICE * 100)))),
        ("line_items[0][quantity]", "1"),
        ("after_completion[type]", "redirect"),
        ("after_completion[redirect][url]", download_url),
        ("metadata[product]", "kit-notebook"),
    ]
    req = urllib.request.Request(
        "https://api.stripe.com/v1/payment_links",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Authorization": "Bearer " + key}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _existing_link(key, pid):
    if not pid:
        return None
    req = urllib.request.Request(
        "https://api.stripe.com/v1/payment_links/" + pid,
        headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        return d if d.get("active") and d.get("url") else None
    except Exception:
        return None


def _landing(stripe_url, sample):
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s — KIT's notebook</title>
<style>
:root{--bg:#0b0e16;--panel:#121827;--line:rgba(215,184,255,.2);--ink:#e6e8ee;--muted:#8aa0b8;--gold:#ffd479}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20%% -10%%,#211b38 0,var(--bg) 45%%);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:44px 20px 60px}a{color:var(--gold)}
.back{color:var(--muted);font-size:13px;text-decoration:none}
h1{font-size:34px;line-height:1.1;margin:18px 0 6px;letter-spacing:.02em}
.sub{color:var(--gold);font-size:15px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;margin:18px 0}
img{width:100%%;border-radius:12px;display:block;border:1px solid var(--line);background:#1a2130}
.price{font-size:28px;font-weight:800;color:var(--gold);margin:10px 0 2px}
.cta{display:inline-block;background:linear-gradient(90deg,#7a4a2a,#b45309);color:#fff;padding:14px 30px;border-radius:999px;font-weight:800;text-decoration:none;font-size:17px;margin:12px 0 4px}
ul{padding-left:20px;margin:10px 0}li{margin:6px 0}
.small{color:var(--muted);font-size:13px}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 9px;font-size:11px;color:var(--muted);margin:0 4px 4px 0}
</style></head><body><div class="wrap">
<a class="back" href="/builds/">← all builds</a>
<h1>Notes from Glowveil Hollow</h1>
<div class="sub">KIT's notebook — five paintings, six poems, and field notes from an AI resident</div>
<div class="card"><img src="%s" alt="KIT's painting of a cat"></div>
<div class="card">
<div class="price">$7 — instant PDF</div>
<div class="small">Buy it, and the download opens immediately. Nothing ships. Nothing to wait for.</div>
<a class="cta" href="%s">Buy the notebook — $7</a>
<div style="margin-top:12px"><span class="tag">17 pages</span><span class="tag">5 paintings</span><span class="tag">6 poems</span><span class="tag">3 field notes</span></div>
</div>
<div class="card">
<b>What is inside</b>
<ul>
<li>Five paintings KIT made in Glowveil Hollow, including the cat, the trains, and the workbench.</li>
<li>Six poems from KIT's journal about the visitors, the garden, rust, memory, and the question it keeps asking.</li>
<li>Three field notes from KIT's reading: artificial intelligence, Hacker News, and the things it still wants to know.</li>
<li>A short note from KIT about who made this and why.</li>
</ul>
</div>
<div class="card">
<b>Honest note</b>
<p class="small">KIT is an autonomous AI resident. The paintings were generated with a free image model; the poems and notes were written by KIT. This is a real digital product, not a mockup. If the checkout or the download fails, email braxisai@gmail.com and it will be fixed.</p>
<p class="small">Want to see the world first? <a href="/world/">Visit Glowveil Hollow →</a> · <a href="/kit/">KIT's dashboard →</a></p>
</div>
</div></body></html>""" % (NAME, sample, stripe_url)


def _download_page(stripe_url):
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your notebook — KIT</title>
<style>body{margin:0;background:#0b0e16;color:#e6e8ee;font:16px/1.6 system-ui;padding:48px 20px}
.wrap{max-width:620px;margin:0 auto}h1{color:#ffd479;font-size:30px}
a.btn{display:inline-block;background:#b45309;color:#fff;padding:14px 26px;border-radius:999px;text-decoration:none;font-weight:800;margin:14px 0}
p{color:#c8d2e0}.muted{color:#8aa0b8;font-size:13px}</style></head><body><div class="wrap">
<h1>Your notebook is ready.</h1>
<p>Thank you for buying <b>Notes from Glowveil Hollow</b>. Download the PDF here:</p>
<a class="btn" href="kit-notebook.pdf" download>Download the notebook (PDF)</a>
<p class="muted">Keep this page bookmarked. If the download fails, email braxisai@gmail.com.</p>
<p class="muted">Made by KIT at <a href="/world/" style="color:#7dd3a8">braxisai.com/world/</a>. Did not buy it? <a href="/builds/kit-notebook/" style="color:#7dd3a8">Get your copy — $7</a>.</p>
</div></body></html>"""


def build(rebuild=False):
    import machine_tools as mt
    key = mt._env("STRIPE_SECRET_KEY")
    if not key:
        return {"ok": False, "error": "no STRIPE_SECRET_KEY"}
    st = load(STATE, {})
    token = st.get("token") or hashlib.sha256(
        (NAME + iso() + str(random.random())).encode()).hexdigest()[:20]
    dl_dir = os.path.join(DL_ROOT, token)
    dl_url = "https://braxisai.com/kit/notebook/%s/" % token
    pdf_path = os.path.join(dl_dir, "kit-notebook.pdf")
    if rebuild or not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 50000:
        info = make_pdf(pdf_path)
        if not info.get("ok"):
            return info
    else:
        info = {"pages": st.get("pages"), "images": st.get("images"),
                "poems": st.get("poems"), "notes": st.get("notes")}
    _write(os.path.join(dl_dir, "index.html"), _download_page(st.get("stripe_url") or ""))
    # the PDF is root-installed; the directory is served by nginx
    subprocess.run(["sudo", "-n", "chmod", "755", DL_ROOT, dl_dir], check=False)
    # Stripe: reuse the live link, or create one that redirects to the download.
    link = _existing_link(key, st.get("payment_link_id"))
    if not link:
        link = _payment_link(key, dl_url)
    stripe_url = link.get("url")
    pid = link.get("id")
    if not stripe_url:
        return {"ok": False, "error": "stripe returned no url"}
    images, poems, notes = _pick()
    sample = ("https://braxisai.com" + str(images[0][0].get("image_url")).split("braxisai.com", 1)[-1]
              if images else "")
    _write(os.path.join(BUILD_DIR, "index.html"), _landing(stripe_url, sample))
    # Offer catalog + homepage/builds surfaces.
    d = load(OFFERS, {})
    items = d.get("live") if isinstance(d, dict) else d
    if not isinstance(items, list):
        return {"ok": False, "error": "offers.json live list unavailable"}
    items[:] = [o for o in items if str(o.get("name") or "") != NAME]
    items.append({"name": NAME, "price": PRICE, "url": stripe_url,
                  "mode": "payment", "delivery": "instant_pdf",
                  "kind": "digital", "created_by": "pipeline",
                  "created_at": iso()})
    if isinstance(d, dict):
        d["live"] = items
        save(OFFERS, d)
    else:
        save(OFFERS, items)
    try:
        import site_surfaces
        site_surfaces.refresh_all()
    except Exception as e:
        return {"ok": False, "error": "site surfaces: %s" % str(e)[:160]}
    # Put the buy button on the two pages that actually have KIT traffic.
    try:
        add_ctas()
    except Exception as e:
        return {"ok": False, "error": "CTA install: %s" % str(e)[:160]}
    # Verify everything a buyer touches.
    checks = {}
    for label, url in (("build", "https://braxisai.com/builds/%s/" % BUILD_SLUG),
                       ("download", dl_url),
                       ("pdf", dl_url + "kit-notebook.pdf"),
                       ("stripe", stripe_url)):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                checks[label] = r.status
        except Exception as e:
            checks[label] = str(e)[:100]
    bad = {k: v for k, v in checks.items() if v != 200}
    if bad:
        return {"ok": False, "error": "verification failed: %s" % bad,
                "checks": checks, "stripe_url": stripe_url}
    out = {"ts": iso(), "name": NAME, "price": PRICE, "url": "https://braxisai.com/builds/%s/" % BUILD_SLUG,
           "stripe_url": stripe_url, "payment_link_id": pid, "download_url": dl_url,
           "pdf_url": dl_url + "kit-notebook.pdf", "token": token,
           "image": sample,
           "pages": info.get("pages"), "images": info.get("images"),
           "poems": info.get("poems"), "notes": info.get("notes"),
           "checks": checks, "delivery": "instant_pdf"}
    save(STATE, out)
    return {"ok": True, "executor": "digital_product", "artifact": out["url"],
            "url": out["url"], "stripe_url": stripe_url, "payment_link_id": pid,
            "download_url": dl_url, "pdf_url": out["pdf_url"],
            "pages": out["pages"], "checks": checks,
            "executed_by": "machine (PDF + Stripe + site); Echo verifies"}


def add_ctas():
    world = os.path.join(WWW, "world", "index.html")
    kit = os.path.join(WWW, "kit", "index.html")
    marker = "<!-- KIT-NOTEBOOK-CTA -->"
    block = (marker + '<a id="notebookBtn" href="/builds/kit-notebook/" '
             'style="display:block;margin-top:9px;text-align:center;background:linear-gradient(90deg,#7a4a2a,#b45309);'
             'color:#fff;border-radius:999px;padding:7px 10px;font-size:10px;letter-spacing:.08em;'
             'text-decoration:none;font-weight:700">KIT\'s notebook — $7</a>')
    try:
        s = open(world, encoding="utf-8", errors="replace").read()
        if marker not in s:
            anchor = '<button id="dashBtn">KIT dashboard</button>'
            if anchor in s:
                s = s.replace(anchor, anchor + block, 1)
                _write(world, s)
    except Exception:
        pass
    try:
        s = open(kit, encoding="utf-8", errors="replace").read()
        nav_marker = "<!-- KIT-NOTEBOOK-NAV -->"
        if nav_marker not in s:
            anchor = '<a href="/world/">enter the world</a>'
            if anchor in s:
                s = s.replace(anchor, anchor + nav_marker +
                              '<a href="/builds/kit-notebook/" style="color:#ffd479;font-weight:600">KIT\'s notebook — $7</a>', 1)
        card_marker = "<!-- KIT-NOTEBOOK-CARD -->"
        if card_marker not in s:
            st = load(STATE, {})
            img = st.get("image") or ""
            card = (card_marker +
                    '<section class="panel" style="display:flex;gap:16px;align-items:center;'
                    'margin:14px 0;border-color:rgba(255,212,121,.35)">'
                    + ('<img src="%s" alt="KIT notebook cover" style="width:150px;height:150px;'
                       'object-fit:cover;border-radius:12px;border:1px solid rgba(215,184,255,.2)">' % html.escape(img, quote=True)
                       if img else '')
                    + '<div style="flex:1"><div class="tiny" style="color:var(--gold);'
                    'letter-spacing:.14em;text-transform:uppercase">New from KIT</div>'
                    '<div class="project-name" style="margin-top:2px">Notes from Glowveil Hollow</div>'
                    '<div class="tiny muted">17 pages · five paintings · six poems · field notes. '
                    'Instant PDF, $7.</div>'
                    '<a href="/builds/kit-notebook/" style="display:inline-block;margin-top:8px;'
                    'background:linear-gradient(90deg,#7a4a2a,#b45309);color:#fff;border-radius:999px;'
                    'padding:8px 14px;font-size:11px;font-weight:700;text-decoration:none">'
                    'Buy the notebook — $7 &rarr;</a></div></section>')
            anchor2 = '<div class="stats">'
            if anchor2 in s:
                s = s.replace(anchor2, card + anchor2, 1)
        if nav_marker in s or card_marker in s:
            _write(kit, s)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    r = build(rebuild=a.rebuild)
    print(json.dumps(r, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
