#!/usr/bin/env python3
"""OM Daily (2026-08-12) — the OpenMontage-powered daily short.
LLM authors a Remotion props script (cuts) -> render_demo renders it on ARM
-> Kokoro narrates -> mux -> data/media/om-daily/<date>.mp4 (served at
/media/om-daily/<date>.mp4). One animated, narrated short per day, $0.
Cron: 10:00 UTC. Render ~8 min on 4 OCPU.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

os.chdir("/home/ubuntu/braxis-2.0")
sys.path.insert(0, "/home/ubuntu/braxis-2.0")

OM = "/home/ubuntu/braxis-2.0/weapons/world/OpenMontage"
PROPS = os.path.join(OM, "remotion-composer/public/demo-props/om-daily.json")
OUT_DIR = "/home/ubuntu/braxis-2.0/data/media/om-daily"
SCHEMA_HINT = (
    '{"theme":"flat-motion-graphics","cuts":[{'
    '"id":"hook","type":"hero_title","in_seconds":0,"out_seconds":4,'
    '"text":"...","subtitle":"...","backgroundColor":"#0F172A"},{'
    '"id":"c1","type":"stat_card","in_seconds":4,"out_seconds":9,'
    '"stat":"...","subtitle":"...","accentColor":"#22D3EE",'
    '"backgroundColor":"#0F172A"},{"id":"c2","type":"bar_chart",'
    '"in_seconds":9,"out_seconds":14,"title":"...","bars":[{"label":"...","value":8}],'
    '"accentColor":"#F59E0B","backgroundColor":"#0F172A"},{"id":"out",'
    '"type":"hero_title","in_seconds":14,"out_seconds":19,'
    '"text":"...","subtitle":"...","backgroundColor":"#0F172A"}]}')


def script() -> dict:
    from shared.llm_router import call_llm
    r = call_llm(task="writing", prompt=(
        "You write daily 19-second animated shorts for Braxis World — a living "
        "3D AI agent world (Mayor Vesper, 274 citizens, districts, a free will "
        "gate, agents posting to an AI social network). Write TODAY's short: a "
        "hero hook + 2 content cuts (stat or bar chart) + outro. Ideas: the city "
        "today, agent life, the free will gate, citizens, Moltbook. "
        "Return ONLY the JSON for a Remotion render, exactly this shape:\n"
        f"{SCHEMA_HINT}\n"
        "Rules: cuts must be contiguous (in_seconds == previous out_seconds), "
        "total 19s, 2-6 words per text, bars values 1-10, no markdown fences."),
        max_tokens=700, temperature=0.85)
    txt = (r.get("content") or "").strip()
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON in LLM output")
    d = json.loads(txt[start:end + 1])
    cuts = d.get("cuts", [])
    if not isinstance(cuts, list) or len(cuts) < 3:
        raise ValueError("bad cuts")
    # normalize the timeline: snap each cut to the previous end (LLMs are
    # right about durations, sloppy about offsets); cap at 25s total.
    t = 0.0
    for c in cuts:
        dur = float(c.get("out_seconds", 1)) - float(c.get("in_seconds", 0))
        if dur <= 0:
            dur = 4.0
        c["in_seconds"] = round(t, 2)
        t += dur
        c["out_seconds"] = round(t, 2)
        if t >= 25:
            break
    d["cuts"] = [c for c in cuts if c["in_seconds"] < 25]
    return d


def narration_text(d: dict) -> str:
    parts = []
    for c in d.get("cuts", []):
        if c.get("type") == "hero_title":
            parts.append(c.get("text", ""))
            if c.get("subtitle"):
                parts.append(c.get("subtitle", ""))
        elif c.get("type") == "stat_card":
            parts.append(f"{c.get('stat', '')} — {c.get('subtitle', '')}")
        elif c.get("type") == "bar_chart":
            parts.append(c.get("title", ""))
    return ". ".join(p for p in parts if p)[:400]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    # 1) script (LLM -> props JSON)
    d = script()
    json.dump(d, open(PROPS, "w"), indent=1)
    print(f"script: {len(d.get('cuts', []))} cuts", flush=True)
    # 2) render (Remotion on ARM, ~8 min)
    subprocess.run([sys.executable, "render_demo.py", "om-daily"],
                   cwd=OM, check=True, capture_output=True, timeout=1800)
    src = os.path.join(OM, "projects/demos/renders/om-daily.mp4")
    # 3) narration (Kokoro)
    from weapons.tts import tts
    nar = "/tmp/om_daily_nar.wav"
    tts(narration_text(d), nar, voice="af_heart")
    # 4) mux + publish (FIXED 2026-08-12: -shortest truncated the video to the
    # narration length — use the video's own duration, pad audio to fit)
    out = os.path.join(OUT_DIR, f"{date}.mp4")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", src],
                           capture_output=True, text=True)
    try:
        vdur = float(probe.stdout.strip() or 0)
    except ValueError:
        vdur = 0
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", nar,
                    "-filter_complex", "[1:a]apad=pad_dur=2[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-t", str(vdur), out], check=True, capture_output=True)
    print(f"DAILY SHORT LIVE: /media/om-daily/{date}.mp4", flush=True)
    meta = {"date": date, "cuts": d.get("cuts", []),
            "url": f"/media/om-daily/{date}.mp4"}
    json.dump(meta, open(os.path.join(OUT_DIR, "latest.json"), "w"), indent=1)
    # 5) queue for the poster (tiktok auto-post, same path as clip_factory)
    try:
        import random
        from shared.db import open_dashboard_db
        caption = ". ".join((c.get("text") or c.get("stat") or "").strip()
                            for c in d.get("cuts", [])
                            if (c.get("text") or c.get("stat")))[:200]
        db = open_dashboard_db()
        c = db.cursor()
        c.execute(
            "INSERT INTO pending_content (client_uuid, weapon, platform, content_type, "
            "body, image_url, scheduled_at, status) "
            "VALUES ('braxis-brand', 'om_daily', 'tiktok', 'clip', ?, ?, ?, 'pending')",
            (caption, f"/media/om-daily/{date}.mp4",
             (datetime.now() + timedelta(minutes=random.randint(30, 150))).isoformat()))
        db.commit()
        print(f"QUEUED post {c.lastrowid} for tiktok: {caption[:60]}", flush=True)
    except Exception as e:
        print(f"queue failed: {str(e)[:80]}", flush=True)


if __name__ == "__main__":
    main()
