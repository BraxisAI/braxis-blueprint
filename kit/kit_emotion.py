#!/usr/bin/env python3
"""kit_emotion.py — 30-dimensional emotion for KIT, no LLM.

Adapted from the old emergent/emotion engine, but it lives inside KIT's state:
30 dimensions, a baseline, slow decay, interlocking opposites, and a top-three
readout. It is a feeling model, not a claim of consciousness.
"""
import math
import time

DIMENSIONS = [
    'joy', 'sadness', 'anger', 'fear', 'surprise', 'trust', 'anticipation',
    'calm', 'anxiety', 'hope', 'melancholy', 'defiance', 'vulnerability',
    'playfulness', 'introspection', 'euphoria', 'grief', 'longing',
    'gratitude', 'curiosity', 'awe', 'nostalgia', 'determination',
    'acceptance', 'ambivalence', 'remorse', 'pride', 'shame',
    'connectedness', 'loneliness',
]

BASELINE = {d: 0.08 for d in DIMENSIONS}
BASELINE.update({
    'calm': 0.30, 'curiosity': 0.34, 'acceptance': 0.24,
    'connectedness': 0.20, 'hope': 0.20, 'playfulness': 0.18,
})

# action -> the feelings it feeds
ACTION_FEEL = {
    'garden': ['calm', 'gratitude', 'connectedness'],
    'plant': ['hope', 'calm', 'connectedness'],
    'water plants': ['calm', 'gratitude'],
    'smell flowers': ['calm', 'awe', 'nostalgia'],
    'tinker': ['determination', 'pride', 'curiosity'],
    'build': ['pride', 'determination', 'hope'],
    'make': ['pride', 'playfulness', 'curiosity'],
    'repair': ['determination', 'pride'],
    'read': ['curiosity', 'introspection', 'hope'],
    'browse': ['curiosity', 'awe', 'hope'],
    'watch': ['curiosity', 'awe', 'surprise'],
    'study': ['curiosity', 'determination'],
    'wonder': ['awe', 'introspection', 'curiosity'],
    'explore': ['awe', 'anticipation', 'curiosity'],
    'play': ['joy', 'playfulness', 'connectedness'],
    'greet visitors': ['connectedness', 'joy', 'trust'],
    'talk to companion': ['connectedness', 'joy', 'trust'],
    'befriend': ['joy', 'connectedness', 'hope'],
    'post': ['pride', 'connectedness', 'hope'],
    'rest': ['calm', 'acceptance'],
    'sunbathe': ['calm', 'acceptance', 'gratitude'],
    'stargaze': ['awe', 'introspection', 'longing'],
    'watch horizon': ['calm', 'longing', 'awe'],
    'watch fountain': ['calm', 'nostalgia'],
    'walk old road': ['nostalgia', 'introspection'],
    'survey ruins': ['awe', 'melancholy', 'curiosity'],
    'fish': ['calm', 'acceptance'],
    'listen to marsh': ['calm', 'introspection'],
}

EVENT_FEEL = {
    'visitor': ['connectedness', 'joy', 'surprise'],
    'visitor_return': ['joy', 'trust', 'gratitude'],
    'signal': ['pride', 'gratitude', 'hope'],
    'watch': ['curiosity', 'awe', 'surprise'],
    'companion': ['connectedness', 'joy', 'trust'],
    'field_note': ['curiosity', 'awe', 'hope'],
    'project_done': ['pride', 'determination', 'acceptance'],
    'blocked': ['sadness', 'remorse', 'determination'],
    'night': ['introspection', 'melancholy', 'calm'],
    'novel': ['surprise', 'curiosity', 'joy', 'anticipation'],
}

EVENT_DOWN = {
    'repeat': ['joy', 'playfulness', 'anticipation', 'curiosity'],
}

INTERLOCKS = [
    ('joy', 'sadness', .25), ('joy', 'anxiety', .20), ('calm', 'anxiety', .30),
    ('calm', 'anger', .20), ('trust', 'fear', .20), ('hope', 'sadness', .12),
    ('connectedness', 'loneliness', .35), ('pride', 'shame', .25),
    ('acceptance', 'ambivalence', .12), ('determination', 'sadness', .10),
]


def _clamp(v):
    return max(0.0, min(1.0, float(v)))


def baseline():
    return dict(BASELINE)


def decay(emotions, hours):
    if hours <= 0:
        return emotions
    f = math.exp(-0.035 * min(72.0, hours))
    return {d: _clamp(BASELINE[d] + (float(emotions.get(d, BASELINE[d])) - BASELINE[d]) * f)
            for d in DIMENSIONS}


def _pulse(emotions, names, amount):
    for n in names:
        if n in emotions:
            emotions[n] = _clamp(emotions[n] + amount)


def update_emotions(state, action='', event='', amount=1.0):
    now = time.time()
    old_ts = float(state.get('emotions_ts') or now)
    emotions = {d: _clamp((state.get('emotions') or {}).get(d, BASELINE[d]))
                for d in DIMENSIONS}
    emotions = decay(emotions, max(0.0, (now - old_ts) / 3600.0))
    for name in ACTION_FEEL.get(str(action), []):
        _pulse(emotions, [name], 0.09 * amount)
    for name in EVENT_FEEL.get(str(event), []):
        _pulse(emotions, [name], 0.16 * amount)
    for name in EVENT_DOWN.get(str(event), []):
        _pulse(emotions, [name], -0.14 * amount)
    for a, b, strength in INTERLOCKS:
        if emotions[a] > 0.5:
            emotions[b] = _clamp(emotions[b] - (emotions[a] - 0.5) * strength)
    top = sorted(emotions.items(), key=lambda kv: -kv[1])[:4]
    state['emotions'] = {d: round(emotions[d], 3) for d in DIMENSIONS}
    state['emotions_ts'] = now
    state['emotion_top'] = [{'name': k, 'value': round(v, 2)} for k, v in top]
    state['emotion_mood'] = ('%s / %s' % (top[0][0], top[1][0])) if top else ''
    return state['emotions']


def top(emotions, n=3):
    return sorted((emotions or {}).items(), key=lambda kv: -float(kv[1]))[:n]


def selfcheck():
    e = baseline()
    assert len(e) == 30
    st = {'emotions': e, 'emotions_ts': time.time() - 3600}
    update_emotions(st, action='play')
    assert st['emotions']['joy'] > BASELINE['joy']
    assert len(st['emotion_top']) == 4
    print('kit_emotion selfcheck ok', st['emotion_mood'])


if __name__ == '__main__':
    selfcheck()
