import os
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
seed = runpy.run_path(str(ROOT / 'files/system/usr/libexec/quantix-discord-seed'))['seed']


class DiscordInstallTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.host = self.root / 'host'
        for name, content in {
            'Discord': '#!/bin/sh\nexit 99\n',  # Installing must never launch the GUI.
            'chrome-sandbox': 'sandbox',
            'resources/build_info.json': '{"version":"1.0.170"}',
            'resources/app.asar': 'complete host resources',
            'modules/discord_desktop_core-1/index.js': 'bundled native modules',
        }.items():
            path = self.host / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (self.host / 'Discord').chmod(0o755)
        self.metadata = self.root / 'installer.db'
        with sqlite3.connect(self.metadata) as database:
            database.execute('CREATE TABLE key_values (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            database.executemany('INSERT INTO key_values VALUES (?, ?)', [
                ('install_id', 'private-build-identity'), ('host/fixture', 'bundled host metadata'),
            ])
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        curl = self.bin / 'curl'
        curl.write_text('''#!/bin/bash
set -euo pipefail
if (( DOWNLOAD_STATUS != 0 )); then exit "$DOWNLOAD_STATUS"; fi
while [[ "$1" != --output ]]; do shift; done
cp "$ARCHIVE" "$2"
''')
        curl.chmod(0o755)
        self.usr = self.root / 'usr'
        (self.usr / 'bin').mkdir(parents=True)
        (self.usr / 'bin/discord').symlink_to('old-rpm-wrapper')

    def install(self, launcher=True, **environment):
        distribution = self.root / 'distribution/Discord'
        if launcher:
            distribution.mkdir(parents=True)
        else:
            shutil.copytree(self.host, distribution)
        (distribution / 'discord.png').write_text('official icon')
        bootstrap = distribution / 'updater_bootstrap'
        # Model the current official --help contract, not an invented CLI option.
        bootstrap.write_text('''#!/usr/bin/python3
import json
import os
from pathlib import Path
import shutil
import sys
if sys.argv[1] != '--no-gui':
    print(f"error: Found argument '{sys.argv[1]}' which wasn't expected, or isn't valid in this context", file=sys.stderr)
    sys.exit(1)
assert sys.argv[3:] == ['stable', 'https://updates.discord.com/']
root = Path(sys.argv[2])
assert os.environ['HOME'] == str(root.parent / 'home')
assert os.environ['XDG_CONFIG_HOME'] == str(root.parent / 'home/.config')
Path(os.environ['BOOTSTRAP_CALL']).write_text(json.dumps(sys.argv[1:]))
if int(os.environ['BOOTSTRAP_STATUS']):
    sys.exit(int(os.environ['BOOTSTRAP_STATUS']))
shutil.copytree(os.environ['HOST'], root / 'app-1.0.170')
shutil.copyfile(os.environ['METADATA'], root / 'installer.db')
print('app-1.0.170')
''')
        bootstrap.chmod(0o755)
        archive = self.root / 'discord.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(distribution, arcname='Discord')
        original = (ROOT / 'files/scripts/install-discord.sh').read_text()
        # Only redirect installation destinations; all actual file/SQLite/hash operations run.
        script = original.replace('/usr/share/', str(self.usr / 'share') + '/').replace(
            '/usr/bin/discord', str(self.usr / 'bin/discord'))
        env = dict(os.environ, PATH=f'{self.bin}:' + os.environ['PATH'],
                   HOME=str(self.root / 'unused-home'), XDG_CONFIG_HOME=str(self.root / 'unused-config'),
                   HOST=str(self.host), METADATA=str(self.metadata), ARCHIVE=str(archive),
                   BOOTSTRAP_CALL=str(self.root / 'bootstrap-call'), BOOTSTRAP_STATUS='0', DOWNLOAD_STATUS='0')
        env.update(environment)
        return subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True, timeout=10)

    def assert_installed(self):
        target = self.usr / 'share/discord'
        for path in self.host.rglob('*'):
            if path.is_file():
                self.assertEqual((target / path.relative_to(self.host)).read_bytes(), path.read_bytes())
        self.assertEqual((target / 'chrome-sandbox').stat().st_mode & 0o7777, 0o4755)
        self.assertTrue(os.access(target / 'Discord', os.X_OK))
        checksums = ''.join(hashlib.sha256((target / name).read_bytes()).hexdigest() + '  ' + name + '\n'
                            for name in ['Discord', 'resources/app.asar'])
        expected = hashlib.sha256(checksums.encode()).hexdigest() + '\n'
        self.assertEqual((self.usr / 'share/quantix-os/discord-build-id').read_text(), expected)
        self.assertEqual((self.usr / 'share/pixmaps/discord.png').read_text(), 'official icon')
        self.assertFalse((self.usr / 'bin/discord').is_symlink())

    def test_launcher_bootstrap_resolves_complete_host_headlessly(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()
        arguments = json.loads((self.root / 'bootstrap-call').read_text())
        self.assertEqual(arguments[0], '--no-gui')
        self.assertFalse(Path(arguments[1]).parent.exists(), 'Temporary build profile must be cleaned up')
        installed = self.usr / 'share/quantix-os/discord-installer.db'
        with sqlite3.connect(installed) as database:
            self.assertEqual(database.execute('SELECT * FROM key_values').fetchall(),
                             [('host/fixture', 'bundled host metadata')])
        self.assertNotIn(b'private-build-identity', installed.read_bytes())

    def test_legacy_complete_tarball_skips_bootstrap(self):
        result = self.install(launcher=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()
        self.assertFalse((self.root / 'bootstrap-call').exists())
        self.assertFalse((self.usr / 'share/quantix-os/discord-installer.db').exists())

    def test_download_error_fails_installation(self):
        result = self.install(DOWNLOAD_STATUS='22')
        self.assertEqual(result.returncode, 22, result.stderr)
        self.assertFalse((self.usr / 'share/discord').exists())

    def test_bootstrap_error_fails_installation(self):
        result = self.install(BOOTSTRAP_STATUS='23')
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertFalse((self.usr / 'share/discord').exists())

    def test_incomplete_resolved_host_fails_installation(self):
        (self.host / 'resources/app.asar').unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / 'bootstrap-call').exists())
        self.assertFalse((self.usr / 'share/discord').exists())


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
