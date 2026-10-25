#!/usr/bin/python3
"""Compile recipe preferences and migrate them once, without locking users in."""
import configparser
import json
import os
import pwd
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROFILE = Path('/usr/share/quantix-os/desktop-profile.json')


def text(value):
    return str(value).lower() if isinstance(value, bool) else str(value)


def apply_settings(directory, settings):
    for filename, groups in settings.items():
        path = directory / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        for group, entries in groups.items():
            for key, value in entries.items():
                command = ['kwriteconfig6', '--file', str(path)]
                for part in group.split('/'):
                    command += ['--group', part]
                subprocess.run(command + ['--key', key, text(value)], check=True)


def write_mime_defaults(directory, browser):
    associations = {'Default Applications': {
        mime: browser for mime in ['text/html', 'application/xhtml+xml',
                                   'x-scheme-handler/http', 'x-scheme-handler/https']
    }}
    apply_settings(directory, {name: associations for name in ['mimeapps.list', 'kde-mimeapps.list']})


def install(profile):
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(json.dumps(profile, indent=2) + '\n')
    # Author /etc in container images. OSTree creates /usr/etc at deployment.
    defaults = Path('/etc/xdg')
    apply_settings(defaults, profile['settings'])
    # ColorScheme alone is not a complete palette for the native login greeter.
    palette = configparser.ConfigParser(interpolation=None)
    palette.optionxform = str
    scheme = profile['settings']['kdeglobals']['General']['ColorScheme']
    with (Path('/usr/share/color-schemes') / f'{scheme}.colors').open() as stream:
        palette.read_file(stream)
    apply_settings(defaults, {'kdeglobals': {
        group: dict(palette[group]) for group in palette.sections()
        if group.startswith(('Colors:', 'ColorEffects:')) or group == 'WM'
    }})
    apply_settings(Path('/etc'), profile['system-settings'])
    environment = Path('/etc/environment.d/90-quantix-theme.conf')
    environment.parent.mkdir(parents=True, exist_ok=True)
    environment.write_text(''.join(f'{key}={text(value)}\n' for key, value in profile['environment'].items()))
    write_mime_defaults(defaults, profile['browser'])
    gtk2 = defaults / 'gtk-2.0/gtkrc'
    gtk2.parent.mkdir(parents=True, exist_ok=True)
    gtk2.write_text('gtk-theme-name="Dracula"\ngtk-icon-theme-name="Papirus"\n'
                    'gtk-cursor-theme-name="Dracula-cursors"\ngtk-cursor-theme-size=24\n')
    schema_dir = Path('/usr/share/glib-2.0/schemas')
    schema = schema_dir / 'zz1-quantix.gschema.override'
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_dict(profile['gsettings'])
    with schema.open('w') as stream:
        config.write(stream)
    subprocess.run(['glib-compile-schemas', '--strict', str(schema_dir)], check=True)


def migrate(profile, config_only=False):
    # Plasma Login also starts a small Plasma session; it is not a desktop user.
    if pwd.getpwuid(os.getuid()).pw_name in {'plasmalogin', 'sddm', 'gdm'}:
        return
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'quantix'
    state.mkdir(parents=True, exist_ok=True)
    revision = str(profile['revision'])
    marker = state / 'desktop-config-revision'
    if not marker.exists() or marker.read_text().strip() != revision:
        if 'KDE' in os.environ.get('XDG_CURRENT_DESKTOP', '').split(':'):
            # The environment hook runs before the Wayland compositor exists.
            subprocess.run(['plasma-apply-colorscheme', 'Dracula'], check=True,
                           env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
        apply_settings(config, profile['settings'])
        write_mime_defaults(config, profile['browser'])
        gtk4 = config / 'gtk-4.0'
        gtk4.mkdir(parents=True, exist_ok=True)
        (gtk4 / 'gtk.css').write_text('@import url("/usr/share/themes/Dracula/gtk-4.0/gtk.css");\n')
        # These old per-user copies conflict with the new portable defaults.
        for filename in ['xsettingsd/xsettingsd.conf', 'gtk-2.0/gtkrc']:
            path = config / filename
            if path.exists():
                path.unlink()
        # The former Flatpak RPC shim is incorrect for native Discord.
        rpc_rule = config / 'user-tmpfiles.d/discord-rpc.conf'
        if rpc_rule.exists() and rpc_rule.read_text().strip() == (
                'L %t/discord-ipc-0 - - - - app/com.discordapp.Discord/discord-ipc-0'):
            rpc_rule.unlink()
        runtime = os.environ.get('XDG_RUNTIME_DIR')
        if runtime:
            socket = Path(runtime) / 'discord-ipc-0'
            if socket.is_symlink() and os.readlink(socket) == 'app/com.discordapp.Discord/discord-ipc-0':
                socket.unlink()
        marker.write_text(revision + '\n')
    if config_only:
        return
    gsettings_marker = state / 'desktop-gsettings-revision'
    if not gsettings_marker.exists() or gsettings_marker.read_text().strip() != revision:
        for schema, entries in profile['gsettings'].items():
            for key, value in entries.items():
                subprocess.run(['gsettings', 'set', schema, key, value], check=True)
        gsettings_marker.write_text(revision + '\n')
    if 'KDE' not in os.environ.get('XDG_CURRENT_DESKTOP', '').split(':'):
        return
    panel_marker = state / 'desktop-panel-revision'
    if panel_marker.exists() and panel_marker.read_text().strip() == revision:
        return
    qdbus = shutil.which('qdbus6') or shutil.which('qdbus') or '/usr/lib64/qt6/bin/qdbus'
    script = 'var profile = ' + json.dumps(profile) + ';\n' + PROFILE.with_name('panel.js').read_text()
    for attempt in range(30):
        result = subprocess.run([qdbus, 'org.kde.plasmashell', '/PlasmaShell',
                                 'org.kde.PlasmaShell.evaluateScript', script],
                                capture_output=True, text=True)
        if result.returncode == 0 and 'quantix-panel-ok' in result.stdout:
            panel_marker.write_text(revision + '\n')
            return
        time.sleep(2)
    raise RuntimeError('Plasma panel migration failed; it will retry at next login')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        install(json.loads(sys.argv[2]))
    else:
        migrate(json.loads(PROFILE.read_text()), '--config-only' in sys.argv)
