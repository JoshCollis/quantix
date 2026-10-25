# Apply once before KWin/kglobalaccel start, so shortcuts are loaded correctly.
XDG_CURRENT_DESKTOP=KDE /usr/libexec/quantix-desktop-apply --config-only >&2 || true
