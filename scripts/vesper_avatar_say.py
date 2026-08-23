#!/usr/bin/env python3
"""08-22: VESPER AVATAR SAY — edge-tts line → mp3 + word-timing JSON for the
TalkingHead avatar page (/avatar/). Word timings drive the lip-sync with zero
API keys. Run: python vesper_avatar_say.py "line text" [slug]
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

OUT = Path("/var/www/braxis/avatar/audio")
VOICE = "en-US-ChristopherNeural"


async def gen(text: str, slug: str, voice: str = VOICE, rate: str = "+8%"):
    words = []
    mp3 = OUT / f"{slug}.mp3"
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "word": chunk["text"],
                    "start": round(chunk["offset"] / 1e7, 3),
                    "end": round((chunk["offset"] + chunk["duration"]) / 1e7, 3),
                })
    (OUT / f"{slug}.json").write_text(json.dumps({
        "text": text, "voice": voice, "words": words,
    }, indent=1))
    print(f"{slug}: {len(words)} words, mp3 {mp3.stat().st_size // 1024}KB")


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "Welcome to Sanctuary. I am Vesper, Mayor of this world."
    slug = sys.argv[2] if len(sys.argv) > 2 else "welcome"
    asyncio.run(gen(text, slug))


if __name__ == "__main__":
    main()
