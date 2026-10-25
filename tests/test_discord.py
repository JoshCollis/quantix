import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DiscordTests(unittest.TestCase):
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
