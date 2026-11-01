#!/usr/bin/env python3
"""world_build_critic.py — score new builds before they become permanent.

A generated ring/arch can be a placeholder with no detail. Capture the build,
turn the still into a one-frame video, ask the visual critic whether it looks
deliberate, and hide the ones that fail. One new build per run keeps it cheap.
"""
import datetime
import json
import os
import subprocess
import sys

B = "/home/ubuntu/braxis-2.0"
BUILDS = os.path.join(B, "data", "world", "world_builds.json")
STATE = os.path.join(B, "data", "world", "build_critic_state.json")
sys.path.insert(0, B)
sys.path.insert(0, os.path.join(B, "weapons", "world"))


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def main():
    builds = load(BUILDS, [])
    st = load(STATE, {"checked": {}})
    checked = st.setdefault("checked", {})
    todo = [b for b in builds if b.get("id") and b.get("id") not in checked
            and not b.get("founder") and b.get("source") != "founder"]
    if not todo:
        print("build critic: nothing new")
        return 0
    b = todo[-1]
    import world_share
    png = world_share.capture(b)
    if not png or not os.path.exists(png):
        print("build critic: capture failed for", b.get("id"))
        checked[b["id"]] = {"score": None, "note": "capture failed"}
        save(STATE, st)
        return 0
    mp4 = png.rsplit(".", 1)[0] + ".mp4"
    r = subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", png, "-t", "1",
         "-vf", "scale=1080:1080", "-pix_fmt", "yuv420p", mp4],
        capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print("build critic: frame encode failed")
        checked[b["id"]] = {"score": None, "note": "encode failed"}
        save(STATE, st)
        return 0
    from shared.visual_critic import critique_video
    vc = critique_video(mp4, context=(
        "One still frame of a structure in Glowveil Hollow, a stylized 3D world. "
        "The structure is what KIT built: judge whether it looks deliberate and "
        "readable, not a placeholder. Characters are not required. Reject a "
        "blank frame, a single untextured cube, or an unreadable obstruction."))
    score = vc.get("score")
    ok = bool(vc.get("ok")) and score is not None and score >= 6
    b["quality"] = {"score": score, "ok": ok, "notes": vc.get("notes", ""),
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    if score is not None and score < 6:
        b["hidden"] = True
        b["quality"]["note"] = "hidden: visual critic below 6"
    elif score is not None:
        b["hidden"] = False
    save(BUILDS, builds)
    checked[b["id"]] = {"score": score, "ok": ok, "note": vc.get("notes", "")[:180]}
    save(STATE, st)
    print("build critic:", b.get("id"), score, ok, vc.get("notes"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
