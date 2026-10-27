# Blenddice Render Manager
#
# Config-driven render setup for Blender:
#   - Pass presets (one .json per preset in Presets_Config/) applied to the active view layer
#   - "Apply Basic Settings" from basic_settings.json
#   - Compositor: File Output node builder (AOV / DATA / CRYPTO packages from output_nodes.json)
#   - Advanced: save the scene's settings / a view layer's passes back into config files
#   - Add-on preferences: production preset folder, background sync, config folder shortcut
#
# Extension metadata lives in blender_manifest.toml.

import bpy

from . import config, sync, operators, compositor, saving, prefs, ui

# prefs first: operators/panels read the preferences
_modules = (prefs, operators, compositor, saving, ui)


def register():
    config.reload_configs()
    for module in _modules:
        for cls in module.classes:
            bpy.utils.register_class(cls)
    sync.schedule_startup_sync()


def unregister():
    sync.unregister()
    for module in reversed(_modules):
        for cls in reversed(module.classes):
            bpy.utils.unregister_class(cls)
