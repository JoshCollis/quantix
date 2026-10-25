// Supported Plasma scripting APIs assign widget/screen IDs at runtime.
var state = new ConfigFile('quantix-desktoprc');
state.group = 'Migration';
if (Number(state.readEntry('PanelRevision', 0)) < profile.revision) {
    var existingPanels = panels();
    for (var i = 0; i < existingPanels.length; i++) {
        existingPanels[i].remove();
    }
    var panel = new Panel;
    panel.location = profile.panel.location;
    panel.height = profile.panel.height;
    panel.floating = profile.panel.floating;
    panel.lengthMode = 'fill';
    panel.hiding = 'none';
    for (var j = 0; j < profile.panel.widgets.length; j++) {
        var spec = profile.panel.widgets[j];
        var widget = panel.addWidget(spec.plugin);
        var config = spec.config || {};
        for (var group in config) {
            widget.currentConfigGroup = group.split('/');
            for (var key in config[group]) {
                var value = config[group][key];
                if (key === 'launchers') value = value.split(',');
                widget.writeConfig(key, value);
            }
        }
    }
    state.writeEntry('PanelRevision', profile.revision);
}
print('quantix-panel-ok');
