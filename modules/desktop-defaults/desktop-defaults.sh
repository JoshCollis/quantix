#!/usr/bin/env bash
set -euo pipefail
module_dir="$(dirname "$(realpath "$0")")"
install -Dm0755 "$module_dir/apply.py" /usr/libexec/quantix-desktop-apply
python3 /usr/libexec/quantix-desktop-apply --install "$1"
install -Dm0644 "$module_dir/panel.js" /usr/share/quantix-os/panel.js
install -Dm0644 "$module_dir/migrate.desktop" /usr/etc/xdg/autostart/quantix-desktop.desktop
install -Dm0644 "$module_dir/environment.sh" /usr/etc/xdg/plasma-workspace/env/quantix-desktop.sh
