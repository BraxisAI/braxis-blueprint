#!/usr/bin/env python3
"""BRAXIS off-VM backup uploader — push the nightly tar to OCI Object Storage
(bucket: braxis-backup, versioned, group-scoped least-privilege key).
Usage: backup_upload.py <tarfile> [keep_days]
Keeps the newest `keep_days` days of full backups, prunes the rest."""
import os
import sys
from datetime import datetime, timedelta

import oci

BUCKET = 'braxis-backup'
KEEP_DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 7

config = oci.config.from_file(os.path.expanduser('~/.oci/config'))
os_client = oci.object_storage.ObjectStorageClient(config)
ns = os_client.get_namespace().data

tar_path = sys.argv[1]
obj_name = os.path.basename(tar_path)


def upload():
    with open(tar_path, 'rb') as f:
        resp = os_client.put_object(ns, BUCKET, obj_name, f)
    if resp.status == 200:
        print('UPLOADED', obj_name, '->', BUCKET, '(%d bytes)' % os.path.getsize(tar_path))
        return True
    print('UPLOAD FAILED:', resp.status)
    return False


def prune():
    """Delete objects older than KEEP_DAYS (versioning keeps recoverable copies)."""
    cutoff = (datetime.utcnow() - timedelta(days=KEEP_DAYS)).strftime('%Y%m%d')
    try:
        objects = os_client.list_objects(ns, BUCKET, fields='name,timeCreated').data.objects or []
        removed = 0
        for o in objects:
            if o.name == obj_name:
                continue
            ts = o.time_created
            if ts and ts.strftime('%Y%m%d') < cutoff:
                os_client.delete_object(ns, BUCKET, o.name)
                removed += 1
                print('pruned', o.name)
        print('prune done:', removed, 'old object(s) removed')
    except Exception as e:
        print('prune skipped:', str(e)[:120])


def verify():
    try:
        objects = os_client.list_objects(ns, BUCKET).data.objects or []
        print('OBJECTS IN BUCKET (%d):' % len(objects))
        for o in objects:
            size_mb = (o.size or 0) / 1024 / 1024
            print('  -', o.name, '(%.1f MB)' % size_mb)
        return True
    except Exception as e:
        print('verify failed:', str(e)[:120])
        return False


if __name__ == '__main__':
    ok = upload()
    if ok:
        prune()
        verify()
