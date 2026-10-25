#!/usr/bin/env bash
set -euo pipefail
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
# Fail the build on an unavailable/invalid release rather than silently shipping old Discord.
curl --fail --show-error --location --retry 5 --retry-all-errors \
  --connect-timeout 30 --max-time 600 \
  'https://discord.com/api/download?platform=linux&format=tar.gz' \
  --output "$workdir/discord.tar.gz"
tar -xzf "$workdir/discord.tar.gz" -C "$workdir" --no-same-owner
test -x "$workdir/Discord/Discord"
test -f "$workdir/Discord/resources/build_info.json"
test -f "$workdir/Discord/resources/app.asar"
install -d /usr/share/discord /usr/share/quantix-os
cp -a "$workdir/Discord/." /usr/share/discord/
chmod 4755 /usr/share/discord/chrome-sandbox
sha256sum "$workdir/discord.tar.gz" | cut -d' ' -f1 > /usr/share/quantix-os/discord-build-id
install -Dm0644 "$workdir/Discord/discord.png" /usr/share/pixmaps/discord.png
# Replace a possible RPM-provided symlink before installing our launcher.
if [[ -L /usr/bin/discord ]]; then rm /usr/bin/discord; fi
