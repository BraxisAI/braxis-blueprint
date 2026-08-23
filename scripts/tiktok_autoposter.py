#!/usr/bin/env python3
"""08-19: THE TIKTOK AUTO-POSTER (VM-native, 24/7) — drains the tiktok queue
through the uploader library (cookie session), marks published. Cron */15.
Safety: one video per pass, never re-tries published, fail-soft."""
import json, os, sys, datetime, shutil
sys.path.insert(0, '/home/ubuntu/braxis-2.0')
os.chdir('/home/ubuntu/braxis-2.0')

from tiktok_uploader.upload import TikTokUploader
from shared.db import open_dashboard_db

STATE = 'data/tiktok_posted.json'
DAILY_CAP = 6  # 08-20: safe ceiling — burst queues (batch nights) never flood
try:
    state = json.load(open(STATE))
except Exception:
    state = {'posted': []}

db = open_dashboard_db()
posted_today = db.execute("SELECT COUNT(*) FROM pending_content WHERE platform='tiktok' "
                          "AND status='published' AND published_at >= datetime('now','start of day')").fetchone()[0]
if posted_today >= DAILY_CAP:
    print(f'tiktok daily cap reached ({posted_today}/{DAILY_CAP})')
    import sys as _sys
    _sys.exit(0)
rows = db.execute(
    "SELECT id, body, image_url FROM pending_content WHERE platform='tiktok' "
    "AND status IN ('pending','approved') AND content_type IN ('video','clip') "
    "ORDER BY id LIMIT 1").fetchall()

posted = 0
for rid, body, image_url in rows:
    if str(rid) in state['posted']:
        continue
    video = f'data/tiktok_videos/{rid}.mp4'
    if not os.path.exists(video) and image_url:
        # 08-22: resolve the render path (om_daily clips etc.)
        _src = image_url.replace('/media/', 'data/../var/www/braxis/media/', 1)
        for _cand in (image_url.replace('/media/', '/var/www/braxis/media/', 1),
                      image_url.replace('/media/', 'data/media/', 1),
                      image_url.lstrip('/')):
            if os.path.exists(_cand):
                try:
                    shutil.copy(_cand, video)
                    print(f'resolved {rid}.mp4 from {_cand}', flush=True)
                    break
                except Exception:
                    pass
    if not os.path.exists(video):
        continue
    full = json.load(open('data/tiktok_cookies_pc.json'))
    cookies_list = [{'name': c['name'], 'value': c['value'],
                     'domain': c.get('domain', ''), 'path': c.get('path', '/'),
                     'expires': c.get('expires', 0)} for c in full]
    uploader = TikTokUploader(cookies_list=cookies_list, headless=True, browser='chromium')
    try:
        uploader.upload_video(video, description=(body or '')[:300])
        db.execute("UPDATE pending_content SET status='published', published_at=? WHERE id=?",
                   (datetime.datetime.now().isoformat(), rid))
        db.commit()
        state['posted'].append(str(rid))
        json.dump(state, open(STATE, 'w'), indent=1)
        posted += 1
        print(f'TIKTOK POSTED #{rid}: {(body or "")[:50]}...')
    except Exception as e:
        print(f'#{rid} fail: {str(e)[:150]}')
        # 08-19: flag the stale session for the PC refresher
        if 'login' in str(e).lower() or 'authentication' in str(e).lower():
            import time as _t
            json.dump({'ts': _t.time()}, open('data/tiktok_cookies_stale.json', 'w'))

print(f'tiktok autoposter: {posted} posted')
