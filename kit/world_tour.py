#!/usr/bin/env python3
"""world_tour.py — a longer narrated walk through Glowveil Hollow.

The 1:16 montage filled the YouTube Videos tab. This cuts a ~2.5 minute
horizontal tour from real recorded world clips, adds a short factual
narration read from KIT's live state (day, project, home, Lumen), and runs
the visual critic before uploading. No invented facts in the narration.
"""
import argparse
import asyncio
import datetime
import glob
import json
import os
import sqlite3
import subprocess
import tempfile
import time

B = "/home/ubuntu/braxis-2.0"
MEDIA = os.path.join(B, "data", "media", "world")
PUBLIC = "https://braxisai.com/media/world/"
WORLD = "https://braxisai.com/world/"
DB = os.path.join(B, "data", "dashboard.db")


def _state():
    try:
        return json.load(open(os.path.join(B, "data", "world", "world_life.json")))
    except Exception:
        return {}


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _day(state):
    try:
        born = datetime.datetime.fromisoformat(state.get("born"))
        return max(1, (datetime.datetime.now(datetime.timezone.utc) - born).days + 1)
    except Exception:
        return 1


def _narration(state):
    p = state.get("project") or {}
    name = p.get("name") or "something small"
    progress = p.get("progress", 0)
    target = p.get("target", 0)
    why = p.get("why") or "to see what the hollow becomes"
    friend = state.get("friend") or {}
    fname = friend.get("name") or "another resident"
    fwords = friend.get("last_words") or "still deciding what to make of this place"
    world = state.get("world_name") or "Glowveil Hollow"
    day = _day(state)
    return (
        "This is %s. Day %d. I am KIT, a resident here. "
        "My house stands in the east meadow, beside a pool and a hot air balloon. "
        "Today I am working on %s, step %d of %d: %s. "
        "A ring road runs around the plaza, with lamps and long avenues. "
        "%s lives out past the orchard. Right now %s says: %s. "
        "We have not decided what we are to each other yet. That is allowed. "
        "The world is live at braxisai dot com slash world. "
        "This is not a finished place. I am still building it."
        % (world, day, name, progress, target, why, fname, fname, fwords)
    )


def _tts(text, out_mp3):
    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, "en-US-AriaNeural", rate="-6%").save(out_mp3))
        if os.path.getsize(out_mp3) > 1000:
            return out_mp3
    except Exception as e:
        print("edge-tts failed:", str(e)[:160])
    try:
        from gtts import gTTS
        gTTS(text, lang="en").save(out_mp3)
        if os.path.getsize(out_mp3) > 1000:
            return out_mp3
    except Exception as e:
        print("gtts failed:", str(e)[:160])
    out_wav = out_mp3.rsplit(".", 1)[0] + ".wav"
    r = subprocess.run(["espeak-ng", "-v", "en-us", "-s", "150", "-w", out_wav, text],
                       capture_output=True, text=True)
    if r.returncode == 0 and os.path.getsize(out_wav) > 1000:
        return out_wav
    return None


def _publish(out, state, a):
    try:
        from shared.visual_critic import critique_video
        vc = critique_video(out, context=(
            "A horizontal narrated tour of Glowveil Hollow, a stylized 3D world. "
            "Show KIT the white robot and the river, trees and buildings of the "
            "hollow. Reject UI overlays, loading screens, black bars, or a fully "
            "static clip."))
        print("critic", vc.get("score"), vc.get("ok"), vc.get("notes"))
        if not vc.get("ok"):
            print("rejected; not uploaded"); return 1
    except Exception as e:
        print("critic unavailable; refusing:", str(e)[:160]); return 1
    world = state.get("world_name") or "Glowveil Hollow"
    day = _day(state)
    title = a.title or ("Glowveil Hollow — a narrated walk (day %d)" % day)
    desc = ("A narrated tour of %s, the live 3D world of KIT, an autonomous "
            "AI resident, and Juniper the moss-cat. Narration is read from "
            "KIT's live state. World: %s  |  KIT's notebook: "
            "https://braxisai.com/builds/kit-notebook/  |  Dashboard: "
            "https://braxisai.com/kit/" % (world, WORLD))
    try:
        from weapons.youtube_upload import upload
        vid = upload(out, title[:100], desc, shorts=False)
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
            ("tour-" + str(int(time.time())), "kit_world", "youtube", "video",
             title[:110], desc[:900], PUBLIC + os.path.basename(out),
             "#AI #3D #autonomous", now, "published", now, now, vid, "world_tour"))
        con.commit(); con.close()
    except Exception as e:
        print("row write failed:", str(e)[:160])
    print("UPLOADED", vid, "https://youtu.be/" + vid)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=8)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--nomusic", action="store_true")
    ap.add_argument("--capture", action="store_true",
                    help="record a fresh 200s horizontal walk instead of using clips")
    ap.add_argument("--sources", default="",
                    help="comma-separated clip paths or filenames to use")
    ap.add_argument("--slow", type=float, default=1.0,
                    help="slow-motion factor for the source clips")
    ap.add_argument("--seconds", type=int, default=90,
                    help="capture length when --capture is set")
    ap.add_argument("--copy-video", action="store_true",
                    help="keep the source video stream (single source) and only add audio")
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    if a.sources:
        clips = []
        for src in a.sources.split(","):
            src = src.strip()
            if not src:
                continue
            p = src if os.path.isabs(src) else os.path.join(MEDIA, os.path.basename(src))
            if not os.path.exists(p):
                print("missing source:", p); return 1
            clips.append(p)
    elif a.capture:
        from world_longform import capture
        mp4 = capture(seconds=a.seconds)
        if not mp4:
            print("capture failed"); return 1
        clips = [mp4]
    else:
        clips = sorted(glob.glob(os.path.join(MEDIA, "live_*.mp4")),
                       key=os.path.getmtime)[-max(2, a.clips):]
        if len(clips) < 2:
            print("not enough world clips"); return 1
    if not clips:
        print("no clips"); return 1
    slow = max(0.25, min(4.0, float(a.slow or 1.0)))
    total = sum(_duration(c) for c in clips) * slow
    state = _state()
    text = _narration(state)
    tmpdir = tempfile.mkdtemp(prefix="worldtour-", dir=MEDIA)
    voice = _tts(text, os.path.join(tmpdir, "narration.mp3"))
    if not voice:
        print("no tts available"); return 1
    print("narration", round(_duration(voice), 1), "s; clips", len(clips), "s", round(total, 1))
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(MEDIA, "world_tour_%s.mp4" % ts)
    music = [] if a.nomusic else sorted(glob.glob(os.path.join(
        B, "data", "songs", "Braxis_Songs", "Kit", "*.mp3")), key=os.path.getmtime)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", c]
    music_idx = None
    if music:
        music_idx = len(clips)
        cmd += ["-stream_loop", "-1", "-t", "%.3f" % max(1.0, total), "-i", music[-1]]
    voice_idx = len(clips) + (1 if music else 0)
    cmd += ["-i", voice]
    if a.copy_video and len(clips) == 1:
        if music:
            afc = ("[1:a]volume=0.16[bg];[2:a]volume=1.0[nar];"
                   "[bg][nar]amix=inputs=2:duration=first:dropout_transition=2[a]")
            cmd += ["-filter_complex", afc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", out]
        else:
            cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print("ffmpeg failed:", r.stderr[-1200:]); return 1
        print("tour", out, round(os.path.getsize(out) / 1e6, 1), "MB", round(_duration(out), 1), "s")
        if a.dry:
            print("dry; not uploaded"); return 0
        return _publish(out, state, a)
    fc = []
    for i in range(len(clips)):
        # Vertical world clips would lose KIT when cropped to 16:9. Keep the
        # full frame and fill the sides with a blurred copy (no black bars).
        pre = ("setpts=%.3f*PTS," % slow) if slow != 1.0 else ""
        fc.append("[%d:v]%ssplit=2[bgsrc%d][fgsrc%d];"
                  "[bgsrc%d]scale=1920:1080:force_original_aspect_ratio=increase,"
                  "crop=1920:1080,gblur=sigma=24[bg%d];"
                  "[fgsrc%d]scale=-2:1080[fg%d];"
                  "[bg%d][fg%d]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30[v%d]"
                  % (i, pre, i, i, i, i, i, i, i, i, i))
    fc.append("".join("[v%d]" % i for i in range(len(clips))) +
              "concat=n=%d:v=1:a=0[v]" % len(clips))
    if music:
        fc.append("[%d:a]volume=0.16[bg]" % music_idx)
        fc.append("[%d:a]volume=1.0[nar]" % voice_idx)
        fc.append("[bg][nar]amix=inputs=2:duration=first:dropout_transition=2[a]")
    else:
        fc.append("[%d:a]volume=1.0[a]" % voice_idx)
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("ffmpeg failed:", r.stderr[-3000:]); return 1
    print("tour", out, round(os.path.getsize(out) / 1e6, 1), "MB", round(_duration(out), 1), "s")
    if a.dry:
        print("dry; not uploaded"); return 0
    return _publish(out, state, a)

if __name__ == "__main__":
    raise SystemExit(main())
