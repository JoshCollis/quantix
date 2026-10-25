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
client="$workdir/Discord"
if [[ -x "$client/updater_bootstrap" && ! -x "$client/Discord" ]]; then
  # Since 2026 the official tarball is a launcher. Resolve the complete stable
  # host at build time, without running Discord or using a real user's profile.
  install -d "$workdir/client" "$workdir/home"
  app_dir="$(HOME="$workdir/home" XDG_CONFIG_HOME="$workdir/home/.config" \
    timeout 600 "$client/updater_bootstrap" --no-zenity "$workdir/client" \
    stable https://updates.discord.com/)"
  client="$workdir/client/$app_dir"
fi
test -x "$client/Discord"
test -f "$client/resources/build_info.json"
test -f "$client/resources/app.asar"
install -d /usr/share/discord /usr/share/quantix-os
cp -a "$client/." /usr/share/discord/
chmod 4755 /usr/share/discord/chrome-sandbox
# The launcher can stay unchanged while the host updates. Identify the host.
(cd "$client" && sha256sum Discord resources/app.asar) | sha256sum | cut -d' ' -f1 \
  > /usr/share/quantix-os/discord-build-id
install -Dm0644 "$workdir/Discord/discord.png" /usr/share/pixmaps/discord.png
# Replace a possible RPM-provided symlink before installing our launcher.
if [[ -L /usr/bin/discord ]]; then rm /usr/bin/discord; fi
