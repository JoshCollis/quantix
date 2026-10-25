#!/usr/bin/env bash

set -Eeuo pipefail

DRACULA_REPO="https://github.com/dracula/gtk.git"
DRACULA_REF="${DRACULA_REF:-master}"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

src="$workdir/gtk"

git clone --depth=1 "$DRACULA_REPO" "$src"

if [[ "$DRACULA_REF" != "master" ]]; then
  git -C "$src" fetch --depth=1 origin "$DRACULA_REF"
  git -C "$src" checkout --detach FETCH_HEAD
fi

install_tree() {
  local from="$1"
  local to="$2"

  if [[ ! -e "$from" ]]; then
    echo "Missing expected Dracula path: $from" >&2
    exit 1
  fi

  rm -rf "$to"
  install -d "$(dirname "$to")"
  cp -a "$from" "$to"
}

install_file() {
  local from="$1"
  local to="$2"

  if [[ ! -f "$from" ]]; then
    echo "Missing expected Dracula file: $from" >&2
    exit 1
  fi

  install -Dm0644 "$from" "$to"
}

# Plasma / KDE assets.
for theme in "$src"/kde/plasma/desktoptheme/*; do
  install_tree "$theme" "/usr/share/plasma/desktoptheme/$(basename "$theme")"
done

install_tree "$src/kde/plasma/look-and-feel/Plasma6/Dracula" \
  "/usr/share/plasma/look-and-feel/Dracula"

for theme in "$src"/kde/aurorae/*; do
  install_tree "$theme" "/usr/share/aurorae/themes/$(basename "$theme")"
done

for scheme in "$src"/kde/color-schemes/*.colors; do
  install_file "$scheme" "/usr/share/color-schemes/$(basename "$scheme")"
done

for theme in "$src"/kde/kvantum/*; do
  install_tree "$theme" "/usr/share/Kvantum/$(basename "$theme")"
done

install_tree "$src/kde/cursors/Dracula-cursors" \
  "/usr/share/icons/Dracula-cursors"

install_tree "$src/kde/sddm/Dracula" \
  "/usr/share/sddm/themes/Dracula"

# GTK / GNOME fallback theme.
install_tree "$src" "/usr/share/themes/Dracula"

# Remove source and desktop-environment bundles that are installed elsewhere.
rm -rf \
  /usr/share/themes/Dracula/.git \
  /usr/share/themes/Dracula/.github \
  /usr/share/themes/Dracula/kde \
  /usr/share/themes/Dracula/src \
  /usr/share/themes/Dracula/Art

# Preferences are compiled from recipes/desktop.yml, independently of the assets.
install_file "$src/gtk-4.0/gtk.css" "/usr/etc/xdg/gtk-4.0/gtk.css"
install_file "$src/gtk-4.0/gtk-dark.css" "/usr/etc/xdg/gtk-4.0/gtk-dark.css"
echo "Dracula theme assets installed."
