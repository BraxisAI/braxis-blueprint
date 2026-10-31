#!/usr/bin/env python3
"""digital_guide.py — sell a real, instantly delivered guide.

The trio can invent a guide (a buyer, a problem, a practical method). This
module turns that idea into a PDF, a Stripe link that redirects to the
download, and a public landing page. No email lane, no shipping, no founder
work, no invented numbers.

Run:  ./venv/bin/python weapons/digital_guide.py --job <job-id>
      ./venv/bin/python weapons/digital_guide.py --name "..." --price 19 \
          --buyer "..." --action "..." [--dry]
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
import urllib.parse
import urllib.request

B = "/home/ubuntu/braxis-2.0"
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons"))
import kit_notebook as kn

WWW = "/var/www/braxis"
OFFERS = os.path.join(B, "data", "offers.json")
STATE_DIR = os.path.join(B, "data", "world", "digital_guides")


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


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "guide"


def _parse_json(raw):
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    cand = m.group(0)
    try:
        return json.loads(cand)
    except Exception:
        pass
    try:
        # The free models sometimes put a literal newline inside a JSON string.
        # The pipeline already has the repair for that exact class.
        import trio_pipeline as tp
        return json.loads(tp._repair_json(cand))
    except Exception:
        return None


def _fallback(name, buyer, action):
    """Substantive deterministic content when the free model returns nothing
    usable. It is general advice, never invented statistics or case studies."""
    low = (name + " " + action).lower()
    if "missed-call" in low or "missed call" in low:
        title = "The Missed-Call Recovery Playbook"
        sections = [
            {"title": "The job you never hear about",
             "body": "A missed call is not a missed conversation. It is a person who needed a service now, "
                     "called the first number they found, and then called the next one. The loss is invisible "
                     "because there is no voicemail to review and no email to answer. The first step is to stop "
                     "treating the phone as a background task. Count the calls that ring out, not just the ones "
                     "that become jobs. Put the count where the owner sees it every week. A simple tally sheet next to the phone or the call log is enough; the point is to make the leak visible without buying software."},
            {"title": "The five-minute text-back",
             "body": "When a call is missed, send one short text within five minutes: your business name, an "
                     "apology for missing the call, one question about the job, and a clear next step. Keep the "
                     "message under four lines. Do not send a link to a long form. Do not promise a price. The "
                     "goal is to get one reply: what do you need, and when do you need it? A reply restarts the "
                     "conversation; silence loses it."},
            {"title": "What to say",
             "body": "Use a stable template and fill in the blanks: “Hi, this is [business]. Sorry we missed "
                     "your call. What kind of job is it, and what town are you in? We can call you back today.” "
                     "If the job is urgent, add one line asking whether it is an emergency. Keep the tone plain. "
                     "Avoid “we will get back to you soon”; give a real window. A specific window is easier to "
                     "keep and easier for the customer to trust."},
            {"title": "Route the reply",
             "body": "A text-back only works if someone owns the reply. Name one person for each shift. When a "
                     "reply arrives, that person either books it, asks one more question, or hands it to the "
                     "owner. Put the booking on the calendar in the same step; do not create a second task. If "
                     "nobody can answer within the window, send a second message that gives a new time. Log the "
                     "outcome so the follow-up does not depend on memory."},
            {"title": "Measure the leak",
             "body": "Track three counts: missed calls, text-backs sent, and jobs booked from those replies. "
                     "Track them for a week before changing the script. The useful comparison is not “more "
                     "messages” but “how many missed calls turned into a booked conversation.” If the text-back "
                     "rate is high and the booking rate is low, fix the questions. If both are low, fix the "
                     "response time or the person who owns the phone."},
            {"title": "The weekly review",
             "body": "Once a week, read the missed calls and the replies. Keep the script that produced "
                     "bookings. Change one line at a time. Check the after-hours path separately from the "
                     "workday path; they fail for different reasons. The goal is not a perfect phone system. "
                     "It is a smaller gap between a ringing phone and a real conversation. Keep a short list of the questions that produced bookings and the ones that did not; that list is the next version of the script."},
        ]
    elif "receptionist" in low:
        title = "The Local AI Receptionist Playbook"
        sections = [
            {"title": "Decide what it owns",
             "body": "An AI receptionist should own a narrow job: answer, capture the request, and route it. "
                     "Write down the three things it may do (greet, ask qualifying questions, book a window) "
                     "and the three things it may not do (quote a firm price, promise a result, handle an "
                     "emergency alone). The boundary is the product. Without it, the receptionist becomes a "
                     "source of bad promises instead of a way to catch missed work."},
            {"title": "Write the call script",
             "body": "Start with a short greeting, the business name, and one question about the job. Ask for "
                     "the town, the type of work, and the urgency. Read back the details before ending the call. "
                     "Keep the script short enough that a real person could read it without sounding robotic. "
                     "The script should produce a clean summary the owner can act on, not a transcript. Use the same words the business uses on its website; a caller should not hear a different company."},
            {"title": "Set the escalation rules",
             "body": "List the cases that must reach a human immediately: emergencies, complaints, existing "
                     "customers with an open job, and anything involving a price the business has not approved. "
                     "For everything else, take a message and give a callback window. Test the escalation path "
                     "with a real phone, not a demo. A receptionist that cannot hand off cleanly is worse than "
                     "voicemail because the caller believes someone is handling it."},
            {"title": "Test before a real call",
             "body": "Run five scripted calls before the service answers a customer: a normal job, an "
                     "after-hours request, an emergency, a complaint, and a caller who will not give an address. "
                     "For each, check the summary, the routing, and the callback window. Fix the script before "
                     "you fix the voice. The test is not whether the AI sounds human; it is whether the owner "
                     "can act on the result."},
            {"title": "Measure and correct",
             "body": "Track calls answered, requests captured, bookings made, and calls that had to be "
                     "escalated. Read a sample of summaries every week. Look for missing details, not just "
                     "wrong answers. If the receptionist captures jobs but the owner cannot book them, the "
                     "problem is the handoff. If it escalates too often, the script is asking for too much. Read five summaries a week; mark missing town, job type, urgency, and callback window."},
            {"title": "Keep a human path",
             "body": "Always leave a way to reach a person: a transfer, a voicemail box that is checked, or a "
                     "callback promise with a real window. Tell the caller which one applies. The receptionist "
                     "is a filter, not a wall. The measure of a good setup is not how many calls it handles "
                     "alone; it is how few callers are left without a next step."},
        ]
    elif "one-person" in low or "ai office" in low:
        title = "The One-Person AI Office"
        sections = [
            {"title": "Choose the work",
             "body": "List the tasks you repeat every week. Keep the ones that are rule-based, have a clear "
                     "input, and produce a reviewable output: drafting replies, summarizing calls, organizing "
                     "notes, preparing a first pass. Do not start with judgment work, pricing, or anything that "
                     "carries a promise to a customer. The first workflow should save one hour, not redesign "
                     "the business."},
            {"title": "Write the brief",
             "body": "For each task, write four lines: the trigger, the inputs, the output, and the acceptance "
                     "test. “When a new inquiry arrives, use the message and the service list to draft a reply; "
                     "the reply must name the service, ask one question, and avoid a price.” A brief that cannot "
                     "be checked is not ready. The acceptance test is what stops the work from turning into "
                     "endless editing."},
            {"title": "Build one workflow",
             "body": "Connect the trigger to one draft step and one review step. Keep it small enough to run "
                     "this week. Do not add a second tool until the first workflow has run on real work. If the "
                     "draft fails the acceptance test, fix the input or the brief; do not add another prompt. "
                     "The first version should be boring and repeatable."},
            {"title": "Keep a human gate",
             "body": "Every customer-facing output gets a human check until the workflow has passed the same "
                     "test many times. The gate is not a lack of trust; it is how you catch a confidently wrong "
                     "draft. Put the check in the same place as the draft. If the check is a separate task, it "
                     "will be skipped on a busy day."},
            {"title": "Measure rework",
             "body": "Track cycle time, the number of drafts per request, and how often the first draft passes "
                     "the acceptance test. Do not measure how many messages the AI wrote. A workflow that "
                     "produces one draft and one clean approval is better than one that produces five drafts "
                     "and a tired owner. Review the log weekly and remove the step that creates the most rework."},
            {"title": "The weekly rhythm",
             "body": "Once a week, pick one workflow, read its last ten outputs, and change one thing. Keep "
                     "the change for a week before judging it. Write down what you changed and what happened. "
                     "The office improves through small, measured changes, not a new tool every month."},
        ]
    else:
        title = name.replace(" Playbook", "").replace(" (PDF)", "").strip()
        sections = [
            {"title": "Who this is for",
             "body": "This guide is for %s. It assumes you want a repeatable process, not a pile of tools. "
                     "%s" % (buyer or "a small team",
                              action or "The goal is to turn the idea into a simple workflow.")},
            {"title": "The problem",
             "body": "The work usually gets stuck in three places: nobody owns the next step, the input is "
                     "incomplete, and the output is never checked against a real acceptance test. That is why "
                     "the same task gets redone instead of improved. Start by naming the one decision that has "
                     "to be made and the one artifact that proves it was made."},
            {"title": "The method",
             "body": "Write down the trigger that starts the work. List the minimum inputs it needs. Produce "
                     "one draft artifact, not three. Check it against a plain acceptance test. Record what "
                     "changed and who owns the next step. Keep the steps in that order; skipping the acceptance "
                     "test is how a fast process turns into rework."},
            {"title": "A simple workflow",
             "body": "Put the trigger, inputs, draft, and acceptance test in one place. When a new request "
                     "arrives, the owner fills the inputs, runs the same draft step, and checks the same test. "
                     "If the test fails, fix the input, not the output. Review the log once a week and remove "
                     "the step that produced the most rework."},
            {"title": "What to measure",
             "body": "Measure cycle time, rework count, and the number of artifacts that passed the acceptance "
                     "test on the first try. Do not measure activity. A process that produces fewer drafts but "
                     "more first-pass acceptances is the better process."},
            {"title": "What to do next",
             "body": "Pick one real request this week. Run it through the five steps. Write the acceptance test "
                     "before you start. At the end, keep the test and the log; that is the beginning of a process "
                     "someone else can run."},
        ]
    return {
        "title": title,
        "subtitle": "A practical guide for %s" % (buyer or "people who want a repeatable process"),
        "buyer": buyer,
        "sections": sections,
        "checklist": [
            "The trigger is written down.",
            "The minimum inputs are listed.",
            "One owner is named.",
            "The acceptance test is written before the draft.",
            "The result and the next step are logged.",
        ],
    }


def _clean(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", str(s or ""))
    s = re.sub(r"(?m)^\s*[-*#]+\s*", "", s)
    s = s.replace("**", "").replace("__", "")
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def write_content(name, buyer, action):
    prompt = (
        "Write a real, practical guide that will be sold as a PDF. Use only "
        "general professional knowledge. Do NOT invent statistics, customers, "
        "case studies, quotes, guarantees, or results. Do not name a real company "
        "as a customer. Plain text only; no markdown.\n\n"
        "TITLE: %s\nBUYER: %s\nWHAT IT SHOULD HELP THEM DO: %s\n\n"
        "Write 5 short sections, each 120-170 words, concrete and actionable. "
        "Include a 5-item checklist. Return STRICT JSON only:\n"
        '{"title":"<title>","subtitle":"<one line>","sections":[{"title":"<heading>",'
        '"body":"<text>"}],"checklist":["<item>"]}' % (name, buyer, action))
    try:
        from shared import llm_router
        r = llm_router.call_llm(prompt, task="writing", max_tokens=3000,
                                temperature=0.55)
        d = _parse_json(str((r or {}).get("content") or ""))
        sections = []
        for s in (d or {}).get("sections") or []:
            body = _clean(s.get("body") or s.get("content") or s.get("text") or "")
            title = _clean(s.get("title") or s.get("heading") or "")
            if body and title:
                sections.append({"title": title[:100], "body": body})
        d = d or {}
        d["sections"] = sections
        d["checklist"] = [_clean(x) for x in (d.get("checklist") or []) if _clean(x)]
        words = sum(len(s["body"].split()) for s in sections)
        if len(sections) >= 5 and words >= 550:
            d.setdefault("title", name)
            d.setdefault("subtitle", "A practical guide for %s" % buyer)
            d["buyer"] = buyer
            return d
    except Exception:
        pass
    return None


def _cover(title, subtitle):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", kn.PAGE, (18, 16, 14))
    d = ImageDraw.Draw(page)
    d.rectangle((70, 70, kn.PAGE[0] - 70, kn.PAGE[1] - 70), outline=(90, 70, 50), width=3)
    d.text((110, 150), "A PRACTICAL GUIDE", font=kn._font(kn.F_SANS_B, 26), fill=(210, 160, 90))
    y = 210
    for line in kn._wrap(d, title, kn._font(kn.F_SANS_B, 54), kn.PAGE[0] - 220):
        d.text((110, y), line, font=kn._font(kn.F_SANS_B, 54), fill=(245, 238, 226))
        y += 66
    d.line((110, y + 18, 540, y + 18), fill=(180, 83, 9), width=3)
    for line in kn._wrap(d, subtitle, kn._font(kn.F_SERIF_I, 30), kn.PAGE[0] - 220)[:4]:
        d.text((110, y + 48), line, font=kn._font(kn.F_SERIF_I, 30), fill=(210, 200, 186))
        y += 40
    d.text((110, kn.PAGE[1] - 160), "Made by the Braxis machine",
           font=kn._font(kn.F_SANS, 21), fill=(180, 170, 155))
    d.text((110, kn.PAGE[1] - 120), "braxisai.com", font=kn._font(kn.F_SANS, 21), fill=(180, 170, 155))
    return page


def make_pdf(path, name, content):
    from PIL import Image
    pages = [_cover(content.get("title") or name, content.get("subtitle") or "")]
    pages.append(kn._text_page(
        "What this is",
        "This guide is for %s.\n\nIt is a practical method, not a promise of a result. "
        "It contains no invented statistics, no fake customers, and no guarantees. "
        "The words were drafted with AI assistance.\n\n"
        "Use the checklist at the end on a real piece of work this week."
        % (content.get("buyer") or "the reader"),
        font_size=25, label="About this guide", footer="braxisai.com"))
    for sec in content.get("sections") or []:
        pages.append(kn._text_page(str(sec.get("title") or "Step"),
                                   str(sec.get("body") or ""), font_size=25,
                                   label="A practical guide", footer="braxisai.com"))
    check = content.get("checklist") or []
    if check:
        pages.append(kn._text_page("Checklist", "\n".join("☐  " + str(x) for x in check),
                                   font_size=27, label="Use this", footer="braxisai.com"))
    pages.append(kn._text_page(
        "Where this came from",
        "This guide is a digital product from Braxis AI. The machine wrote it "
        "with AI assistance. It contains no invented statistics, no fake "
        "customers, and no guarantees. The PDF is delivered immediately after "
        "checkout. If something is wrong, email braxisai@gmail.com and it will "
        "be fixed.\n\nbraxisai.com", font_size=25, label="Braxis AI", footer="braxisai.com"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return {"ok": True, "pages": len(pages), "words": sum(
        len(str(s.get("body") or "").split()) for s in content.get("sections") or [])}


def _stripe(name, price, redirect):
    key = kn._env("STRIPE_SECRET_KEY") if hasattr(kn, "_env") else ""
    if not key:
        import machine_tools as mt
        key = mt._env("STRIPE_SECRET_KEY")
    if not key:
        return {"ok": False, "error": "no STRIPE_SECRET_KEY"}
    data = [
        ("line_items[0][price_data][currency]", "usd"),
        ("line_items[0][price_data][product_data][name]", name + " (instant PDF)"),
        ("line_items[0][price_data][unit_amount]", str(int(round(float(price) * 100)))),
        ("line_items[0][quantity]", "1"),
        ("after_completion[type]", "redirect"),
        ("after_completion[redirect][url]", redirect),
    ]
    req = urllib.request.Request(
        "https://api.stripe.com/v1/payment_links",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        return {"ok": True, "url": d.get("url"), "id": d.get("id")}
    except Exception as e:
        return {"ok": False, "error": "stripe: %s" % str(e)[:160]}


def _download_html(name, stripe_url):
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your guide — %s</title>
<style>body{margin:0;background:#0b0e16;color:#e6e8ee;font:16px/1.6 system-ui;padding:48px 20px}
.wrap{max-width:620px;margin:0 auto}h1{color:#ffd479;font-size:28px}
a.btn{display:inline-block;background:#b45309;color:#fff;padding:14px 26px;border-radius:999px;text-decoration:none;font-weight:800;margin:14px 0}
p{color:#c8d2e0}.muted{color:#8aa0b8;font-size:13px}</style></head><body><div class="wrap">
<h1>Your guide is ready.</h1>
<p>Thank you for buying <b>%s</b>. Download the PDF here:</p>
<a class="btn" href="guide.pdf" download>Download the guide (PDF)</a>
<p class="muted">Keep this page bookmarked. If the download fails, email braxisai@gmail.com.</p>
<p class="muted"><a href="/builds/" style="color:#7dd3a8">More builds</a> · <a href="/world/" style="color:#7dd3a8">KIT's world</a></p>
</div></body></html>""" % (html.escape(name), html.escape(name))


def _landing(name, content, price, stripe_url):
    sections = "".join("<li>%s</li>" % html.escape(str(s.get("title") or ""))
                       for s in content.get("sections") or [])
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s — a practical guide</title>
<style>
:root{--bg:#0b0e16;--panel:#121827;--line:rgba(215,184,255,.2);--ink:#e6e8ee;--muted:#8aa0b8;--gold:#ffd479}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20%% -10%%,#211b38 0,var(--bg) 45%%);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:44px 20px 60px}a{color:var(--gold)}
.back{color:var(--muted);font-size:13px;text-decoration:none}
h1{font-size:34px;line-height:1.15;margin:18px 0 6px}
.sub{color:var(--gold);font-size:15px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;margin:18px 0}
.price{font-size:28px;font-weight:800;color:var(--gold);margin:8px 0 2px}
.cta{display:inline-block;background:linear-gradient(90deg,#7a4a2a,#b45309);color:#fff;padding:14px 30px;border-radius:999px;font-weight:800;text-decoration:none;font-size:17px;margin:12px 0 4px}
ul{padding-left:20px;margin:10px 0}li{margin:6px 0}
.small{color:var(--muted);font-size:13px}
</style></head><body><div class="wrap">
<a class="back" href="/builds/">← all builds</a>
<h1>%s</h1>
<div class="sub">%s</div>
<div class="card">
<div class="price">$%g — instant PDF</div>
<div class="small">Buy it, and the download opens immediately. Nothing ships. Nothing to wait for.</div>
<a class="cta" href="%s">Buy the guide — $%g</a>
</div>
<div class="card"><b>What is inside</b><ul>%s</ul></div>
<div class="card"><b>Honest note</b><p class="small">A practical guide written with AI assistance. No fake case studies, no invented statistics, no guarantees. If the download fails, email braxisai@gmail.com.</p></div>
</div></body></html>""" % (
        html.escape(name), html.escape(content.get("title") or name),
        html.escape(content.get("subtitle") or ""), float(price), stripe_url,
        float(price), sections)


def build(job=None, name=None, price=None, buyer=None, action=None, dry=False):
    if job:
        name = name or str(job.get("arm") or "")
        idea = job.get("idea") or {}
        price = price or idea.get("price") or 19
        buyer = buyer or idea.get("buyer") or ""
        action = action or idea.get("action") or ""
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "guide needs a name"}
    slug = slugify(name)
    state_path = os.path.join(STATE_DIR, slug + ".json")
    st = load(state_path, {})
    content = st.get("content") or write_content(name, buyer, action) or _fallback(name, buyer, action)
    if dry:
        return {"ok": True, "dry": True, "name": name, "content": content}
    token = st.get("token") or hashlib.sha256(
        (name + iso() + str(random.random())).encode()).hexdigest()[:20]
    dl_dir = os.path.join(WWW, "kit", "guides", slug, token)
    dl_url = "https://braxisai.com/kit/guides/%s/%s/" % (slug, token)
    pdf_path = os.path.join(dl_dir, "guide.pdf")
    info = make_pdf(pdf_path, name, content)
    kn._write(os.path.join(dl_dir, "index.html"), _download_html(name, st.get("stripe_url") or ""))
    subprocess.run(["sudo", "-n", "chmod", "755", os.path.dirname(dl_dir), dl_dir], check=False)
    link = kn._existing_link(
        (lambda: __import__("machine_tools")._env("STRIPE_SECRET_KEY"))(),
        st.get("payment_link_id"))
    if not link:
        r = _stripe(name, price, dl_url)
        if not r.get("ok"):
            return r
        link = {"url": r["url"], "id": r["id"]}
    stripe_url = link.get("url")
    pid = link.get("id")
    build_dir = os.path.join(WWW, "builds", slug)
    kn._write(os.path.join(build_dir, "index.html"),
              _landing(name, content, price, stripe_url))
    d = load(OFFERS, {})
    items = d.get("live") if isinstance(d, dict) else d
    if not isinstance(items, list):
        return {"ok": False, "error": "offers.json live list unavailable"}
    items[:] = [o for o in items if str(o.get("name") or "") != name]
    items.append({"name": name, "price": float(price), "url": stripe_url,
                  "mode": "payment", "delivery": "instant_pdf", "kind": "digital_guide",
                  "created_by": "pipeline", "created_at": iso()})
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
    checks = {}
    for label, url in (("build", "https://braxisai.com/builds/%s/" % slug),
                       ("download", dl_url), ("pdf", dl_url + "guide.pdf"),
                       ("stripe", stripe_url)):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                checks[label] = r.status
        except Exception as e:
            checks[label] = str(e)[:100]
    bad = {k: v for k, v in checks.items() if v != 200}
    if bad:
        return {"ok": False, "error": "verification failed: %s" % bad, "checks": checks}
    out = {"ts": iso(), "name": name, "slug": slug, "price": float(price),
           "url": "https://braxisai.com/builds/%s/" % slug, "stripe_url": stripe_url,
           "payment_link_id": pid, "download_url": dl_url, "pdf_url": dl_url + "guide.pdf",
           "token": token, "content": content, "pages": info.get("pages"),
           "words": info.get("words"), "checks": checks, "delivery": "instant_pdf"}
    save(state_path, out)
    return {"ok": True, "executor": "digital_product", "artifact": out["url"],
            "url": out["url"], "stripe_url": stripe_url, "payment_link_id": pid,
            "download_url": dl_url, "pdf_url": out["pdf_url"],
            "pages": out["pages"], "checks": checks,
            "executed_by": "machine (guide + Stripe + site); Echo verifies"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--name")
    ap.add_argument("--price", type=float)
    ap.add_argument("--buyer")
    ap.add_argument("--action")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    job = load(os.path.join(B, "data", "world", "pipeline", "jobs", a.job + ".json"), None) if a.job else None
    if a.job and not job:
        print("job not found")
        return 1
    r = build(job=job, name=a.name, price=a.price, buyer=a.buyer,
              action=a.action, dry=a.dry)
    print(json.dumps(r, indent=1)[:5000])
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
