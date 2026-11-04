import configparser
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path):
    return yaml.safe_load((ROOT / path).read_text())


class BuildTests(unittest.TestCase):
    def test_variant_recipes_and_matrices(self):
        build = load_yaml('.github/workflows/build.yml')['jobs']['build']
        cleanup = load_yaml('.github/workflows/cleanup-packages.yml')['jobs']['cleanup']
        recipes = build['strategy']['matrix']['recipe']
        self.assertEqual(recipes, ['recipe.yml', 'recipe-nvidia-open.yml'])
        names = []
        for filename, name, base in [
            ('recipe.yml', 'quantix', 'bazzite'),
            ('recipe-nvidia-open.yml', 'quantix-nvidia-open', 'bazzite-nvidia-open'),
        ]:
            recipe = load_yaml(f'recipes/{filename}')
            self.assertEqual(recipe['name'], name)
            self.assertEqual(recipe['base-image'], f'ghcr.io/ublue-os/{base}')
            self.assertEqual(recipe['image-version'], 'stable')
            self.assertEqual(recipe['modules'], [{'from-file': 'common.yml'}])
            names.append(name)
        self.assertEqual(cleanup['strategy']['matrix']['package'], names)

    def test_inherited_terra_repositories_are_not_added_again(self):
        # Bazzite 45.20261104 installs terra-release{,-extras,-mesa} in
        # the common build path, including NVIDIA Open. Model DNF5's repo-ID
        # collision rather than relying only on the local repo filenames.
        inherited = {'terra', 'terra-source', 'terra-mesa', 'terra-mesa-source',
                     'terra-extras', 'terra-extras-source'}
        for variant in ['recipe.yml', 'recipe-nvidia-open.yml']:
            with self.subTest(variant=variant):
                recipe = load_yaml(f'recipes/{variant}')
                modules = load_yaml('recipes/' + recipe['modules'][0]['from-file'])['modules']
                for module in modules:
                    for repo in module.get('repos', {}).get('files', []):
                        if '://' not in repo:
                            config = configparser.ConfigParser(interpolation=None)
                            self.assertTrue(config.read(ROOT / 'files/dnf' / repo))
                            self.assertFalse(inherited.intersection(config.sections()),
                                             f'Duplicate upstream repo IDs in {repo}')
                        self.assertNotIn('terra', repo.lower(), 'Use Bazzite-owned Terra repositories')
        for path in (ROOT / 'files').rglob('*.repo'):
            config = configparser.ConfigParser(interpolation=None)
            config.read(path)
            self.assertFalse(inherited.intersection(config.sections()), str(path))

    def test_no_custom_passthrough_or_kernel_tuning(self):
        modules = load_yaml('recipes/common.yml')['modules']
        self.assertFalse({'kargs', 'initramfs', 'akmods'}.intersection(
            module.get('type') for module in modules))
        self.assertFalse((ROOT / 'files/system/etc/dracut.conf.d/vfio.conf').exists())
        forbidden = re.compile(
            r'vfio|iommu|pci[-_]stub|pcie_acs_override|hugepages|'
            r'kvm\.(?:ignore_msrs|report_ignored_msrs)|preempt=|gpu_sched\.|'
            r'(?:rd\.)?driver\.blacklist|modprobe\.blacklist|nomodeset|'
            r'blacklist\s+(?:amdgpu|radeon|nouveau|nvidia|i915)|'
            r'(?:driver_override|new_id|/drivers/[^\s]+/bind)|'
            r'mokutil\s+--disable-validation', re.IGNORECASE)
        for directory in ['files', 'modules', 'recipes']:
            for path in (ROOT / directory).rglob('*'):
                if not path.is_file():
                    continue
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotRegex(str(path.relative_to(ROOT)),
                                        r'dracut\.conf\.d|modprobe\.d|kargs\.d|\.patch$')
                    try:
                        text = path.read_text()
                    except UnicodeDecodeError:
                        continue
                    self.assertNotRegex(text, forbidden)
        # These are application COPRs, not replacement kernels or akmods.
        dnf = next(module for module in modules if module.get('type') == 'dnf')
        self.assertEqual(dnf['repos']['copr'], ['lizardbyte/stable', 'codifryed/CoolerControl'])
        self.assertFalse(any(package.startswith(('kernel', 'akmod', 'kmod'))
                             for package in dnf['install']['packages']))

    def test_standard_virtualization_is_preserved(self):
        modules = load_yaml('recipes/common.yml')['modules']
        packages = next(module['install']['packages'] for module in modules if module.get('type') == 'dnf')
        for package in ['virt-manager', 'virt-viewer', 'libvirt', 'qemu',
                        'qemu-char-spice', 'qemu-device-display-virtio-gpu',
                        'qemu-device-display-virtio-vga', 'qemu-device-usb-redirect',
                        'qemu-img', 'qemu-system-x86-core', 'qemu-user-binfmt', 'qemu-user-static']:
            self.assertIn(package, packages)
        services = next(module['system']['enabled'] for module in modules if module.get('type') == 'systemd')
        self.assertIn('libvirtd', services)
        self.assertIn('swtpm-workaround', services)
        for path in ['usr/lib/systemd/system/swtpm-workaround.service',
                     'usr/lib/tmpfiles.d/swtpm-workaround.conf']:
            self.assertTrue((ROOT / 'files/system' / path).is_file())

    def test_signing_is_preserved(self):
        modules = load_yaml('recipes/common.yml')['modules']
        self.assertEqual(modules[-1], {'type': 'signing'})
        self.assertEqual(hashlib.sha256((ROOT / 'cosign.pub').read_bytes()).hexdigest(),
                         '640eb628a4a7518c423428b67addfee31e5555a50798e360abb3473d59cb58c6')
        build = load_yaml('.github/workflows/build.yml')['jobs']['build']
        action = next(step for step in build['steps'] if step['name'] == 'Build Custom Image')
        self.assertEqual(action['with']['cosign_private_key'], '${{ secrets.SIGNING_SECRET }}')
        self.assertEqual(action['with']['registry_token'], '${{ github.token }}')
        self.assertEqual(build['permissions']['id-token'], 'write')

    def test_cpe_matches_verified_fedora_base(self):
        modules = load_yaml('recipes/common.yml')['modules']
        metadata = next(module['properties'] for module in modules if module.get('type') == 'os-release')
        self.assertEqual(metadata['CPE_NAME'], 'cpe:/o:joshcollis:quantix:45')

    def test_file_overrides_win_over_upstream_theme(self):
        modules = load_yaml('recipes/common.yml')['modules']
        theme = next(i for i, module in enumerate(modules) if 'install-dracula.sh' in module.get('scripts', []))
        files = next(i for i, module in enumerate(modules) if module['type'] == 'files')
        metadata = next(i for i, module in enumerate(modules) if 'qtx-info.sh' in module.get('scripts', []))
        self.assertLess(theme, files)
        self.assertLess(files, metadata)

    def test_image_metadata(self):
        original = (ROOT / 'files/scripts/qtx-info.sh').read_text()
        for name, flavor in [('quantix', 'main'), ('quantix-nvidia-open', 'nvidia-open'), (None, 'main')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                splash = root / 'Splash.qml'
                splash.write_text('plasma.svgz')
                info = root / 'image-info.json'
                script = original.replace(
                    '/usr/share/plasma/look-and-feel/org.kde.breeze.desktop/contents/splash/Splash.qml',
                    str(splash),
                ).replace('/usr/share/quantix-os/image-info.json', str(info))
                env = dict(os.environ)
                env.pop('IMAGE_NAME', None)
                if name:
                    env['IMAGE_NAME'] = name
                subprocess.run(['bash', '-c', script], env=env, check=True, capture_output=True)
                metadata = json.loads(info.read_text())
                self.assertEqual(metadata['image-name'], name or 'quantix')
                self.assertEqual(metadata['image-flavor'], flavor)
                self.assertEqual(metadata['image-ref'], f'ostree-image-signed:docker://ghcr.io/joshcollis/{name or "quantix"}')
                self.assertEqual(splash.read_text(), 'quantix_logo.svgz')

    def test_buildkit_pull_retries(self):
        steps = load_yaml('.github/workflows/build.yml')['jobs']['build']['steps']
        cleanup = next(step for step in steps if step['name'] == 'Free space for chunk composition')
        self.assertNotIn('if', cleanup)
        self.assertNotIn('skip-if-available', cleanup.get('with', {}))
        build = next(step['with'] for step in steps if step['name'] == 'Build Custom Image')
        self.assertTrue(build['build_chunked_oci'])
        self.assertEqual(build['build_opts'], '--build-driver podman --run-driver podman')
        script = next(step['run'] for step in steps if step['name'] == 'Pre-pull BuildKit with retries')
        for failures, attempts, status, delays in [
            (0, 1, 0, []), (1, 2, 0, ['10']), (2, 3, 0, ['10', '20']), (3, 3, 1, ['10', '20']),
        ]:
            with self.subTest(failures=failures), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                docker = root / 'docker'
                docker.write_text('''#!/bin/bash
set -eu
[[ "$*" == "pull moby/buildkit:buildx-stable-1" ]]
n=$(cat "$STATE" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$STATE"
(( n > FAILURES ))
''')
                sleep = root / 'sleep'
                sleep.write_text('#!/bin/bash\necho "$1" >> "$DELAYS"\n')
                docker.chmod(0o755)
                sleep.chmod(0o755)
                state, delay_file = root / 'state', root / 'delays'
                env = dict(os.environ, PATH=f'{root}:' + os.environ['PATH'], STATE=str(state), DELAYS=str(delay_file), FAILURES=str(failures))
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, status)
                self.assertEqual(int(state.read_text()), attempts)
                self.assertEqual(delay_file.read_text().splitlines() if delay_file.exists() else [], delays)

    def test_cleanup_retention_and_dry_run(self):
        cleanup = load_yaml('.github/workflows/cleanup-packages.yml')['jobs']['cleanup']
        script = cleanup['steps'][0]['with']['script']
        harness = '''
const assert = require('node:assert/strict');
const script = JSON.parse(process.argv[1]);
const run = new (Object.getPrototypeOf(async function() {}).constructor)('github', 'context', 'core', script);
(async () => {
  for (const name of ['quantix', 'quantix-nvidia-open']) {
    for (const dryRun of [true, false]) {
      process.env.PACKAGE_NAME = name;
      process.env.RETENTION_DAYS = '21';
      process.env.DRY_RUN = String(dryRun);
      const old = new Date(Date.now() - 30 * 86400000).toISOString();
       const versions = ['latest', 'latest-cache', '43', '44', 'dated', null].map((tag, i) => ({
        id: i, updated_at: old, metadata: {container: {tags: tag ? [tag] : []}}
      }));
      versions.push({id: 6, updated_at: new Date().toISOString(), metadata: {container: {tags: []}}});
      versions.push({id: 7, updated_at: old});
      versions.push({id: 8, updated_at: old, metadata: {container: {tags: ['dated', 'latest']}}});
       versions.push({id: 9, updated_at: 'invalid', metadata: {container: {tags: []}}});
       versions.push({id: 10, updated_at: old, metadata: {container: {tags: ['sha256-abc.sig']}}});
      const deleted = [];
      const github = {
        paginate: async (route, params) => {assert.equal(params.package_name, name); return versions;},
        request: async (route, params) => {
          assert.match(route, /^DELETE /);
          assert.equal(params.package_name, name);
          deleted.push(params.package_version_id);
        }
      };
      const summary = {addHeading() {return this}, addRaw() {return this}, async write() {}};
      await run(github, {repo: {owner: 'JoshCollis'}}, {info() {}, summary});
       assert.deepEqual(deleted, dryRun ? [] : [4]);
    }
  }
})().catch(error => {console.error(error); process.exit(1)});
'''
        result = subprocess.run(['node', '-e', harness, json.dumps(script)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
