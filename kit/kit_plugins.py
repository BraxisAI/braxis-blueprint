#!/usr/bin/env python3
"""kit_plugins.py — declarative actions and shapes KIT may add to its world.

A plugin is DATA, not host code: actions are name/place/effects; shapes are a
small list of primitives. The life loop and the renderer read them exactly like
built-ins. No eval, no imports, no host filesystem access, no network. That is
the boundary that makes "KIT invents a new thing" safe.
"""
import json
import os
import re

B = "/home/ubuntu/braxis-2.0"
PATH = os.path.join(B, "data", "world", "kit_plugins.json")
NAME_RX = re.compile(r"^[a-z][a-z0-9 ]{1,38}$")
SHAPE_RX = re.compile(r"^[a-z][a-z0-9 _-]{1,29}$")
PART_KINDS = {"box", "cyl", "sphere", "cone"}


def _doc():
    try:
        d = json.load(open(PATH, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(doc):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    os.replace(tmp, PATH)


def load():
    a = _doc().get("actions")
    return a if isinstance(a, dict) else {}


def load_shapes():
    s = _doc().get("shapes")
    return s if isinstance(s, dict) else {}


def save(actions):
    doc = _doc()
    doc["actions"] = actions
    _write(doc)


def save_shapes(shapes):
    doc = _doc()
    doc["shapes"] = shapes
    _write(doc)


def validate(spec, existing, places, drives):
    if not isinstance(spec, dict):
        return None, "not an object"
    name = str(spec.get("name") or "").strip().lower()
    if not NAME_RX.match(name):
        return None, "name must be 2-39 lowercase letters/spaces"
    if name in existing or name in (existing or {}):
        return None, "action already exists"
    place = str(spec.get("place") or "").strip()
    if place not in places:
        return None, "place %r is not in the world" % place
    eff = spec.get("effects")
    if not isinstance(eff, dict) or not eff:
        return None, "effects must be a non-empty object"
    clean = {}
    for k, v in eff.items():
        if k not in drives:
            return None, "unknown drive %r" % k
        try:
            v = round(float(v), 3)
        except Exception:
            return None, "effect %r is not a number" % k
        if v < -1.5 or v > 1.5:
            return None, "effect %r out of range" % k
        clean[k] = v
    try:
        intrinsic = round(float(spec.get("intrinsic", 0.6)), 3)
    except Exception:
        return None, "intrinsic is not a number"
    if not 0.0 <= intrinsic <= 1.0:
        return None, "intrinsic must be 0..1"
    try:
        cooldown = int(spec.get("cooldown") or 4 * 3600)
    except Exception:
        cooldown = 4 * 3600
    cooldown = max(0, min(86400, cooldown))
    thought = str(spec.get("thought") or "")[:140]
    return {
        "name": name,
        "place": place,
        "effects": clean,
        "intrinsic": intrinsic,
        "cooldown": cooldown,
        "thought": thought,
        "source": "kit",
    }, ""


def add(spec):
    """Validate and persist one action. Returns (spec, error)."""
    from world_life import ACTIONS, LOCS, DRIVES
    actions = load()
    clean, err = validate(spec, set(ACTIONS) | set(actions), set(LOCS), DRIVES)
    if err:
        return None, err
    actions[clean["name"]] = clean
    save(actions)
    return clean, ""


def _num(part, key, default, lo, hi):
    try:
        v = float(part.get(key, default))
    except Exception:
        return None
    if v < lo or v > hi:
        return None
    return round(v, 3)


def validate_shape(spec, existing):
    """A shape is a short list of primitives. Nothing executable."""
    if not isinstance(spec, dict):
        return None, "not an object"
    name = str(spec.get("name") or "").strip().lower()
    if not SHAPE_RX.match(name):
        return None, "name must be 2-30 lowercase letters/spaces/hyphens"
    if name in existing:
        return None, "shape already exists"
    parts = spec.get("parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 24:
        return None, "parts must be a list of 1-24 primitives"
    out = []
    for p in parts:
        if not isinstance(p, dict):
            return None, "each part must be an object"
        kind = str(p.get("kind") or "").lower()
        if kind not in PART_KINDS:
            return None, "part kind must be box/cyl/sphere/cone"
        q = {"kind": kind}
        for key, default, lo, hi in (
                ("x", 0, -25, 25), ("y", 0, -25, 25), ("z", 0, -25, 25),
                ("w", 1, .05, 20), ("h", 1, .05, 20), ("d", 1, .05, 20),
                ("r1", .5, .05, 20), ("r2", .5, .05, 20),
                ("rx", 0, -6.283, 6.283), ("ry", 0, -6.283, 6.283),
                ("rz", 0, -6.283, 6.283)):
            v = _num(p, key, default, lo, hi)
            if v is None:
                return None, "part %s out of range" % key
            q[key] = v
        try:
            color = int(p.get("color", 0x8a8f99))
        except Exception:
            return None, "part color must be an integer"
        if color < 0 or color > 0xffffff:
            return None, "part color out of range"
        q["color"] = color
        q["glow"] = bool(p.get("glow"))
        q["emissive"] = bool(p.get("emissive"))
        out.append(q)
    try:
        scale = round(float(spec.get("scale", 1.0)), 3)
    except Exception:
        return None, "scale is not a number"
    if not .5 <= scale <= 5:
        return None, "scale must be .5..5"
    return {"name": name, "scale": scale, "parts": out, "source": "kit"}, ""


def add_shape(spec):
    """Validate and persist one renderable shape. Returns (spec, error)."""
    shapes = load_shapes()
    clean, err = validate_shape(spec, set(shapes))
    if err:
        return None, err
    shapes[clean["name"]] = clean
    save_shapes(shapes)
    return clean, ""
