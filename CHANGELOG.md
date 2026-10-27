# Changelog

Versioning: `2.0.x` small fixes, `2.x.0` new features, `X.0.0` big versions.

## 2.2.0

- **Compositor:** Build Output Node is now driven by `output_nodes.json`.
  - Three packages: **AOV**, **DATA** and **CRYPTO**. Which pass goes where, node colors and EXR formats are configurable.
  - Path and file name templates with the tokens `{SCENE}`, `{VIEW_LAYER}` and `{PACKAGE}`.
  - Building again replaces the nodes generated earlier instead of duplicating them.
  - Denoise nodes are collapsed and compact, and now include Volume Direct / Indirect.
  - Nodes are placed to the right of the Render Layers node, from its top edge downward. File Output nodes are wider so the path stays readable.
- **Apply Presets** is now also available in the Compositor tab. It targets the layer of the selected Render Layers node, otherwise the active view layer.
- **Layout tab:** "Apply Presets" is a box instead of a dropdown. New collapsed **Advanced** panel:
  - **Save Settings to Preset** writes the scene's current values into the local `basic_settings.json`.
  - **Save Passes to Preset** writes the active view layer's passes into a new preset file.
  - Both ask for confirmation, keep a `.bak` copy and write atomically.
- `output_nodes.json` is also synced from the production folder.

## 2.1.0

- `basic_settings.json` now lists about 100 options covering the Output and Render tabs. `null` means "not applied", so nothing is applied that is not in the file.
- Color management is intentionally not touched (handled by the studio's OCIO setup).
- Compact add-on preferences. Sidebar tab renamed to **Blenddice Render Setup**.

## 2.0.0

- Renamed to **Blenddice Render Manager** (new extension ID, the old Breakdice add-on has to be removed).
- Pass presets and basic settings moved into config files (`Presets_Config/*.json`, `basic_settings.json`) in the per-user extension folder. The file name of a preset becomes its button name.
- Production sync: copies the preset configs from a pipeline folder on startup, in the background. The production folder always wins, nothing is deleted.
- Add-on preferences: production path, Sync Now, Reload Configs, config folder shortcut.
- Config files are validated; problems are shown in the preferences.
- Basic Settings can show the Holdout and Indirect Only columns in the Outliner, switch off the default render output (Blender 5.2+) and enable Persistent Data.
- Removed Fix Output Path and Create Folders.
