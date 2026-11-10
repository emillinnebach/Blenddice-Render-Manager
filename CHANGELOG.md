# Changelog

Versioning: `2.0.x` small fixes, `2.x.0` new features, `X.0.0` big versions.

## 2.3.4

- **Clear all Lightgroups:** new small button in the Light Groups box. After a confirmation it clears the light group of every object and deletes all light groups in all view layers.

## 2.3.3

- **Create Light Group:** several selected lights now always get a new numbered group (`Lightgroup_001`, `Lightgroup_002`, ...) instead of being added to an existing `Lightgroup`. A custom name typed in the redo panel still reuses a group of that name.

## 2.3.2

- **Create Light Group:** when Overwrite moves lights out of a group and nothing is assigned to that group anymore, the empty group is deleted (from all view layers). Other empty groups are left alone.

## 2.3.1

- **Create Light Group:** lights that are already in another light group now open a confirmation window (**Overwrite** / **Cancel**). Overwrite removes them from their old group; Cancel changes nothing.
- **Export Camera:** a camera in an excluded, disabled or hidden collection now gives an error and no file is written. If the exporter still produces an empty file, it is deleted and reported.

## 2.3.0

- **Light groups:** new **Create Light Group** button (Layout tab). One selected light creates a group named after it, several lights share one group. Lights already in another group are skipped and reported (redo panel: **Reassign**, **All View Layers**).
- **Denoise:** `denoise.passes` supports wildcards (`Combined_*`) and an object form `{ "normal": bool, "albedo": name }`. Light group passes are denoised. Volume Direct / Indirect no longer get a Normal input.
- **Export Camera:** exports the active camera as Alembic (.abc) for Nuke (Layout and Compositor tabs). Settings in the new `camera` block of `output_nodes.json`; files are versioned (`Camera_{SCENE}_v001.abc`, never overwritten).
- Sidebar tab and panels renamed to **Render Layer Manager**.
- Bundled `output_nodes.json`: DATA and CRYPTO default to 32-bit ZIP (lossless).
- Only `output_nodes.json` changes; presets and `basic_settings.json` stay as they are. Older `output_nodes.json` files keep working (missing `camera` block uses the defaults), but they need the new `denoise` entries to denoise light groups.

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
