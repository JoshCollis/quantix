import os
import json
from pathlib import Path
import runpy
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
seed = runpy.run_path(str(ROOT / 'files/system/usr/libexec/quantix-discord-seed'))['seed']


class DiscordTests(unittest.TestCase):
    def test_updater_seed_registers_bundled_modules_without_downgrading_personal_hosts(self):
        host_key = 'host/app/stable/linux/x64'
        latest_key = 'latest/' + host_key

        def host(version, **extra):
            return {'host_version': {'version': [1, 0, version]}, 'install_state': 'Installed', **extra}

        def metadata(path, version):
            with sqlite3.connect(path) as database:
                database.execute('CREATE TABLE key_values (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                database.executemany('INSERT INTO key_values VALUES (?, ?)', [
                    (host_key, json.dumps([host(version)])),
                    (latest_key, json.dumps({'full': {'host_version': [1, 0, version]}})),
                    ('install_id', json.dumps('build-identity-must-not-be-shared')),
                ])

        def get(path, key):
            with sqlite3.connect(path) as database:
                return json.loads(database.execute('SELECT value FROM key_values WHERE key = ?', (key,)).fetchone()[0])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay = root / 'overlay'
            overlay.mkdir()
            (overlay / 'Discord').write_text('executable')
            (overlay / 'resources').mkdir()
            (overlay / 'modules').mkdir()
            (overlay / 'modules/discord_desktop_core-1').mkdir()
            config = root / 'user/discord'
            first, second = root / 'seed-1.db', root / 'seed-2.db'
            metadata(first, 166)
            metadata(second, 167)
            seed(config, first, overlay, 'build-a')
            database = config / 'installer.db'
            identity = get(database, 'install_id')
            self.assertNotEqual(identity, 'build-identity-must-not-be-shared')
            self.assertEqual((config / 'app-1.0.166/Discord').read_text(), 'executable')
            self.assertEqual((config / 'app-1.0.166/resources').resolve(), overlay / 'resources')
            (config / 'settings.json').write_text('{"personal":true}')
            personal = config / 'app-1.0.168'
            personal.mkdir()
            with sqlite3.connect(database) as connection:
                connection.execute('UPDATE key_values SET value = ? WHERE key = ?',
                                   (json.dumps([host(166), host(168, moduleRevision=99)]), host_key))
                connection.execute('UPDATE key_values SET value = ? WHERE key = ?',
                                   (json.dumps({'full': {'host_version': [1, 0, 168]}}), latest_key))
            before = database.read_bytes()
            seed(config, first, overlay, 'build-a')
            self.assertEqual(database.read_bytes(), before)
            seed(config, second, overlay, 'build-b')
            self.assertFalse((config / 'app-1.0.166').is_symlink())
            self.assertTrue(personal.is_dir())
            self.assertEqual((config / 'app-1.0.167/resources').resolve(), overlay / 'resources')
            self.assertEqual(get(database, 'install_id'), identity)
            self.assertEqual(get(database, latest_key)['full']['host_version'], [1, 0, 168])
            self.assertEqual(get(database, host_key), [host(168, moduleRevision=99), host(167)])
            self.assertEqual((config / 'settings.json').read_text(), '{"personal":true}')

    def test_self_updated_host_is_only_used_when_not_older(self):
        original = (ROOT / 'files/system/usr/libexec/quantix-discord-user-host').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / 'base/resources'
            base.mkdir(parents=True)
            (base / 'build_info.json').write_text('{"version":"1.0.166"}')
            user = root / 'config/discord'
            for name, expected in [('1.0.165', False), ('1.0.166', True), ('1.0.167', True)]:
                host = user / f'app-{name}'
                (host / 'resources').mkdir(parents=True)
                (host / 'resources/build_info.json').write_text('{"version":"' + name + '"}')
                executable = host / 'Discord'
                executable.touch()
                executable.chmod(0o755)
                link = user / 'Discord'
                link.unlink(missing_ok=True)
                link.symlink_to(executable)
                script = original.replace('/usr/share/discord', str(root / 'base'))
                result = subprocess.run(['python3', '-c', script], capture_output=True, text=True,
                                        env=dict(os.environ, XDG_CONFIG_HOME=str(root / 'config')), check=True)
                self.assertEqual(result.stdout.strip(), str(executable) if expected else '')
            (host / '.quantix-managed-host').write_text('{}')
            result = subprocess.run(['python3', '-c', script], capture_output=True, text=True,
                                    env=dict(os.environ, XDG_CONFIG_HOME=str(root / 'config')), check=True)
            self.assertEqual(result.stdout, '')

    def test_overlay_keeps_same_build_patches_but_discards_stale_ones(self):
        original = (ROOT / 'files/system/usr/libexec/quantix-discord-overlay').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, base, target, bin_dir = [root / name for name in ['state', 'base', 'target', 'bin']]
            base.mkdir()
            bin_dir.mkdir()
            binary = base / 'Discord'
            binary.touch()
            binary.chmod(0o755)
            build_id = root / 'build-id'
            build_id.write_text('build-a\n')
            script = original.replace('state=/var/lib/overlays/discord', f'state={state}').replace(
                'base=/usr/share/discord', f'base={base}').replace('target=/opt/discord', f'target={target}').replace(
                '/run/lock/quantix-discord-overlay.lock', str(root / 'lock')).replace(
                '/usr/share/quantix-os/discord-build-id', str(build_id))
            for name, body in [('findmnt', 'exit 1'), ('mount', 'echo "$*" >> "$MOUNTS"')]:
                path = bin_dir / name
                path.write_text('#!/bin/bash\n' + body + '\n')
                path.chmod(0o755)
            env = dict(os.environ, PATH=f'{bin_dir}:' + os.environ['PATH'], MOUNTS=str(root / 'mounts'))

            def start():
                subprocess.run(['bash', '-c', script], env=env, check=True, capture_output=True)

            start()
            patch_file = state / 'upper/patched'
            patch_file.touch()
            start()
            self.assertTrue(patch_file.exists())
            build_id.write_text('build-b\n')
            start()
            self.assertFalse(patch_file.exists())
            self.assertEqual((state / 'build-id').read_text().strip(), 'build-b')
            self.assertEqual(len((root / 'mounts').read_text().splitlines()), 3)


if __name__ == '__main__':
    unittest.main()
