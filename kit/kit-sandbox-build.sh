#!/bin/bash
# Rebuild KIT's package sandbox image. Packages are baked at build time; the
# runtime container has no network and no way to install anything.
set -e
B=/home/ubuntu/braxis-2.0
D=$(mktemp -d /tmp/kitsbx.XXXXXX)
cp "$B/weapons/kit-sandbox.Dockerfile" "$D/Dockerfile"
docker build --network host -t braxis-kit-sandbox:1 "$D"
rm -rf "$D"
echo "built braxis-kit-sandbox:1"
