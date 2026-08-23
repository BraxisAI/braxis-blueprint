#!/bin/bash
# BRAXIS V2 — daily backup of the whole empire (code + tours + data + postiz).
# Local rotation 14 days + off-VM copy to Oracle Object Storage (braxis-backup,
# versioned bucket, least-privilege API key). 3am cron.
# NOTE: data/songs excluded — the PC archives are canonical (7.3GB); the VM
# copy is the working set only.
cd /home/ubuntu
TS=$(date +%Y%m%d_%H%M)
mkdir -p backups

# crontab snapshot — the automation schedule goes IN the tar (and thus to OCI)
mkdir -p backups/cron-snapshot
crontab -l > backups/cron-snapshot/ubuntu-crontab.txt 2>/dev/null || true
sudo cp /etc/cron.d/braxis-virtual-tours backups/cron-snapshot/ 2>/dev/null || true
sudo chown -R ubuntu:ubuntu backups/cron-snapshot

# postiz docker volumes (connected accounts, schedules, DB) — separate dump
sudo docker run --rm -v postiz_postgres-volume:/data -v /home/ubuntu/backups:/backup \
    alpine tar czf "/backup/postiz-volumes-$TS.tar.gz" -C /data . 2>/dev/null \
    && sudo chown ubuntu:ubuntu "/home/ubuntu/backups/postiz-volumes-$TS.tar.gz" \
    && ls -t /home/ubuntu/backups/postiz-volumes-*.tar.gz | tail -n +8 | xargs -r rm

# full empire: braxis-2.0 (minus venv/logs/songs) + tours + stalwart + www + postiz config
tar -czf "backups/braxis2-$TS.tar.gz" \
    --exclude=*/venv --exclude=*/logs --exclude=*/__pycache__ --exclude=*/src/vendor \
    --exclude=*/data/songs --exclude=*/data/tiktok_videos --exclude=*/data/media/video_clips \
    -C /home/ubuntu braxis-2.0 backups/cron-snapshot \
    -C /opt/braxis virtual-tours/tours virtual-tours/photos virtual-tours/data \
    -C /var/www braxis /opt/stalwart-mail/config \
    -C /home/ubuntu postiz 2>/dev/null
ls -t backups/braxis2-*.tar.gz | tail -n +8 | xargs -r rm
SIZE=$(du -h "backups/braxis2-$TS.tar.gz" | cut -f1)
echo "Backup: backups/braxis2-$TS.tar.gz ($SIZE)"

# off-VM copy to Oracle Object Storage (the disaster-proof layer)
cd /home/ubuntu/braxis-2.0
./venv/bin/python backup_upload.py "/home/ubuntu/backups/braxis2-$TS.tar.gz" >> logs/backup.log 2>&1 \
    || echo "off-VM upload failed — check logs/backup.log"

# stable 'latest' copy in the bucket — restores and the D: sync always grab this name
cp "/home/ubuntu/backups/braxis2-$TS.tar.gz" /home/ubuntu/backups/braxis2-latest.tar.gz
./venv/bin/python backup_upload.py "/home/ubuntu/backups/braxis2-latest.tar.gz" >> logs/backup.log 2>&1 \
    || echo "latest upload failed — check logs/backup.log"

# log rotation — gzip anything older than 7 days, keep 14
find /home/ubuntu/braxis-2.0/logs -name '*.log' -mtime +7 -exec gzip -f {} \; 2>/dev/null
