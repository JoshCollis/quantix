import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('desktop', ROOT / 'modules/desktop-defaults/apply.py')
desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.profile = yaml.safe_load((ROOT / 'recipes/desktop.yml').read_text())['modules'][0]

    def test_settings_apply_once_and_keep_subsequent_user_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {'XDG_CONFIG_HOME': directory + '/config', 'XDG_STATE_HOME': directory + '/state'}
            with patch.dict(os.environ, env), patch.object(desktop.subprocess, 'run') as run:
                desktop.migrate(self.profile, config_only=True)
                first = run.call_count
                self.assertGreater(first, 30)
                desktop.migrate(self.profile, config_only=True)
                self.assertEqual(run.call_count, first)
                self.profile['revision'] += 1
                desktop.migrate(self.profile, config_only=True)
                self.assertGreater(run.call_count, first)

    def test_portable_panel_and_one_time_migration(self):
        script = (ROOT / 'modules/desktop-defaults/panel.js').read_text()
        harness = '''
const assert = require('node:assert/strict');
var profile = JSON.parse(process.argv[1]);
var revision = 0, created = [], removed = 0;
global.ConfigFile = function() {this.readEntry = () => revision;
  this.writeEntry = (key, value) => {revision = value};};
global.panels = () => [{remove() {removed++}}];
global.Panel = function() {created.push(this); this.widgets = [];
  this.addWidget = (plugin) => {const widget = {plugin, writeConfig() {}};
    this.widgets.push(widget); return widget;};};
global.print = () => {};
const run = () => {eval(process.argv[2])};
run(); run();
assert.equal(created.length, 1);
assert.equal(removed, 1);
assert.equal(created[0].height, 44);
assert.equal(created[0].location, 'bottom');
assert.equal(created[0].floating, false);
assert.equal(created[0].widgets.length, 7);
'''
        subprocess.run(['node', '-e', harness, json.dumps(self.profile), script], check=True)

    def test_brave_replaces_zen_and_discord_is_fresh(self):
        modules = yaml.safe_load((ROOT / 'recipes/common.yml').read_text())['modules']
        dnf = next(module for module in modules if module.get('type') == 'dnf')
        self.assertIn('brave-browser', dnf['install']['packages'])
        self.assertNotIn('discord', dnf['install']['packages'])
        self.assertTrue(any('install-discord.sh' in module.get('scripts', []) for module in modules))
        flatpaks = next(module for module in modules if module.get('type') == 'default-flatpaks')
        config = flatpaks['configurations'][0]
        self.assertNotIn('app.zen_browser.zen', config['install'])
        self.assertIn('app.zen_browser.zen', config['remove'])
        self.assertEqual(self.profile['settings']['kwinrc']['org.kde.kdecoration2']['ButtonsOnLeft'], 'XIA')
        self.assertEqual(self.profile['settings']['Kvantum/kvantum.kvconfig']['General']['theme'], 'Dracula')


if __name__ == '__main__':
    unittest.main()
