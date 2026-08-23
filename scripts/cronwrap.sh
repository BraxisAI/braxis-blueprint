#!/bin/bash
# cronwrap.sh (08-21, research sweep #3) — every cron job runs through:
#   flock -n : never stack a duplicate when the previous run is still alive
#              (kills the duplicate-sender cascade class)
#   timeout --kill-after=30 : SIGTERM at deadline, SIGKILL 30s later
#              (kills the hung-process SQLite-lock-hog class)
# Usage: cronwrap.sh <lock-name> <seconds> <command...>
LOCK="$1"; SECS="$2"; shift 2
LOCKFILE="/var/lock/braxis-$LOCK.lock"
exec flock -n "$LOCKFILE" timeout --kill-after=30 "$SECS" "$@"
