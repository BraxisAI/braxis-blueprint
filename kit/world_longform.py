#!/usr/bin/env python3
"""world_longform.py — record a horizontal 3+ minute world tour for YouTube.

The Shorts lane is healthy; the Videos tab went dark because every producer
makes vertical clips. This records a 16:9 walk through Glowveil Hollow, runs
the visual critic, and uploads it as a regular video (no #Shorts tag).
"""
import datetime
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

B = "/home/ubuntu/braxis-2.0"
MEDIA = os.path.join(B, "data", "media", "world")
PUBLIC = "https://braxisai.com/media/world/"
WORLD = "https://braxisai.com/world/"
DB = os.path.join(B, "data", "dashboard.db")
SECONDS = 200


def capture():
    from playwright.sync_api import sync_playwright
    os.makedirs(MEDIA, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="worldlong-", dir=MEDIA)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True,
                              args=["--use-gl=swiftshader", "--enable-webgl",
                                    "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": 1920, "height": 1080},
                            record_video_dir=tmp,
                            record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        started = time.time()
        page.goto(WORLD + "?video=1", wait_until="domcontentloaded", timeout=90000)
        try:
            page.wait_for_function(
                "() => { const e=document.getElementById('load'); return !e || "
                "getComputedStyle(e).display === 'none'; }", timeout=120000)
        except Exception as e:
            print("load gate timeout:", str(e)[:120])
            ctx.close(); b.close(); shutil.rmtree(tmp, ignore_errors=True)
            return None
        loaded_at = time.time()
        page.wait_for_timeout(SECONDS * 1000)
        ctx.close(); b.close()
    src = sorted(glob.glob(os.path.join(tmp, "*.webm")))
    if not src:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(MEDIA, "long_%s.mp4" % ts)
    trim = max(0.0, loaded_at - started - 0.5)
    print("trim before world:", round(trim, 1), "s; recording", SECONDS, "s")
    cmd = ["ffmpeg", "-y"]
    if trim:
        cmd += ["-ss", "%.2f" % trim]
    cmd += ["-i", src[0]]
    audio = sorted(glob.glob(os.path.join(
        B, "data", "songs", "Braxis_Songs", "Kit", "*.mp3")), key=os.path.getmtime)
    if audio:
        cmd += ["-stream_loop", "-1", "-i", audio[-1]]
    cmd += ["-vf", "scale=1920:1080", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd += [out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=360)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("ffmpeg failed:", r.stderr[-300:])
        return None
    print("video", out, round(os.path.getsize(out) / 1e6, 1), "MB")
    return out


def main():
    mp4 = capture()
    if not mp4:
        return 1
    url = PUBLIC + os.path.basename(mp4)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            if r.status != 200:
                print("video not served:", r.status); return 1
    except Exception as e:
        print("video not served:", e); return 1
    try:
        from shared.visual_critic import critique_video
        vc = critique_video(mp4, context=(
            "A horizontal long-form walk through Glowveil Hollow, a stylized "
            "3D world with a white robot resident, KIT, and a green moss-cat, "
            "Juniper. The world, buildings and characters should be visible. "
            "Reject UI overlays, a loading screen, black bars, or a static clip."))
        print("critic", vc.get("score"), vc.get("ok"), vc.get("notes"))
        if not vc.get("ok"):
            print("rejected")
            return 1
    except Exception as e:
        print("critic unavailable; refusing:", str(e)[:160])
        return 1
    state = {}
    try:
        state = json.load(open(os.path.join(B, "data", "world", "world_life.json")))
    except Exception:
        pass
    world = state.get("world_name") or "Glowveil Hollow"
    title = "Glowveil Hollow — a living AI world at day %s" % (
        max(1, (datetime.datetime.now(datetime.timezone.utc) -
                datetime.datetime.fromisoformat(state.get("born"))).days + 1)
        if state.get("born") else 3)
    desc = ("A 3-minute walk through %s, the 3D world of KIT, an autonomous "
            "AI resident. KIT builds, paints, writes and keeps a journal; "
            "Juniper the moss-cat wanders nearby. World: %s  |  KIT's notebook: "
            "https://braxisai.com/builds/kit-notebook/  |  Dashboard: "
            "https://braxisai.com/kit/" % (world, WORLD))
    try:
        from weapons.youtube_upload import upload
        vid = upload(mp4, title[:100], desc, shorts=False)
    except Exception as e:
        print("upload failed:", str(e)[:300]); return 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        import sqlite3
        con = sqlite3.connect(DB, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(
            "INSERT INTO pending_content (client_uuid, weapon, platform, content_type, "
            "title, body, image_url, hashtags, scheduled_at, status, created_at, "
            "published_at, published_url, posted_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("long-" + str(int(time.time())), "kit_world", "youtube", "video",
             title[:110], desc[:900], url, "#AI #3D #autonomous", now,
             "published", now, now, vid, "world_longform"))
        con.commit(); con.close()
    except Exception as e:
        print("row write failed:", str(e)[:160])
    print("UPLOADED", vid, "https://youtu.be/" + vid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
