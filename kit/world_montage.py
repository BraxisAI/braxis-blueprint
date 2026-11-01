#!/usr/bin/env python3
"""world_montage.py — fill the YouTube Videos tab from real world clips.

The 3-minute live capture failed its visual critic; the older long-form lane is
weekly and its recent renders came out at 42s. This cuts a horizontal 16:9
montage from the already-recorded world clips, keeps the real footage, and
uploads it as a regular video (not a Short).
"""
import datetime
import glob
import json
import os
import sqlite3
import subprocess
import time

B = "/home/ubuntu/braxis-2.0"
MEDIA = os.path.join(B, "data", "media", "world")
PUBLIC = "https://braxisai.com/media/world/"
DB = os.path.join(B, "data", "dashboard.db")


def main():
    clips = sorted(glob.glob(os.path.join(MEDIA, "live_*.mp4")),
                   key=os.path.getmtime)[-4:]
    if len(clips) < 2:
        print("not enough world clips"); return 1
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(MEDIA, "world_montage_%s.mp4" % ts)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", c]
    audio = sorted(glob.glob(os.path.join(
        B, "data", "songs", "Braxis_Songs", "Kit", "*.mp3")), key=os.path.getmtime)
    a_idx = len(clips)
    if audio:
        cmd += ["-stream_loop", "-1", "-i", audio[-1]]
    fc = []
    for i in range(len(clips)):
        fc.append("[%d:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                  "crop=1920:1080,setsar=1[v%d]" % (i, i))
    fc.append("".join("[v%d]" % i for i in range(len(clips))) +
              "concat=n=%d:v=1:a=0[v]" % len(clips))
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]"]
    if audio:
        cmd += ["-map", "%d:a" % a_idx, "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print("ffmpeg failed:", r.stderr[-500:]); return 1
    print("montage", out, round(os.path.getsize(out)/1e6, 1), "MB")
    try:
        from shared.visual_critic import critique_video
        vc = critique_video(out, context=(
            "A horizontal montage of the 3D world Glowveil Hollow, with KIT "
            "the robot and Juniper the moss-cat. Judge whether the world is "
            "visible and the clips are publishable; reject UI/loading screens."))
        print("critic", vc.get("score"), vc.get("ok"), vc.get("notes"))
        if not vc.get("ok"):
            print("rejected"); return 1
    except Exception as e:
        print("critic unavailable:", str(e)[:160]); return 1
    url = PUBLIC + os.path.basename(out)
    state = {}
    try: state = json.load(open(os.path.join(B, "data", "world", "world_life.json")))
    except Exception: pass
    world = state.get("world_name") or "Glowveil Hollow"
    title = "Glowveil Hollow — a living AI world (day 3)"
    desc = ("A short horizontal tour of %s, the live 3D world of KIT, an "
            "autonomous AI resident, and Juniper the moss-cat. World: %s  |  "
            "KIT's notebook: https://braxisai.com/builds/kit-notebook/  |  "
            "Dashboard: https://braxisai.com/kit/" % (world, "https://braxisai.com/world/"))
    try:
        from weapons.youtube_upload import upload
        vid = upload(out, title, desc, shorts=False)
    except Exception as e:
        print("upload failed:", str(e)[:300]); return 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        con = sqlite3.connect(DB, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(
            "INSERT INTO pending_content (client_uuid, weapon, platform, content_type, "
            "title, body, image_url, hashtags, scheduled_at, status, created_at, "
            "published_at, published_url, posted_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("montage-" + str(int(time.time())), "kit_world", "youtube", "video",
             title, desc, url, "#AI #3D #autonomous", now, "published", now, now,
             vid, "world_montage"))
        con.commit(); con.close()
    except Exception as e:
        print("row write failed:", str(e)[:160])
    print("UPLOADED", vid, "https://youtu.be/" + vid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
