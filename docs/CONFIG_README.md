# Blenddice Render Manager

Extension to apply render pass configs to view layers and auto output node generator. Enables you to share your ViewLayer presets across your production. Edit the config files to set up.

Sidebar tab: **Blenddice Render Setup** (3D Viewport and Compositor).

# Config Reference

## Where the files live

Open the folder from **Preferences > Add-ons > Blenddice Render Manager > Settings: Open Config Folder**.

```
<per-user extension folder>/
    Presets_Config/        one .json per pass preset
    basic_settings.json    used by "Apply Basic Settings"
    output_nodes.json      used by "Build Output Node"
```

On first run the bundled defaults are copied there (existing files are never overwritten).

## Production sync

Set **Production Presets** in the add-on preferences to your pipeline folder. On every Blender start (and on
**Sync Now**) the .json files are copied into the local folder, in the background. The production folder always
wins: local files with the same name are overwritten, nothing is deleted. Empty path = no sync.

Both layouts work:

```
<production folder>/Presets_Config/*.json   (+ basic_settings.json, output_nodes.json in <production folder>)
<production folder>/*.json                  (+ basic_settings.json, output_nodes.json in the same folder)
```

## Pass presets (`Presets_Config/<Name>.json`)

The file name is the button name: `Environment.json` gives **Apply Environment passes**.
`Default.json` is always listed first. `basic_settings.json` and `output_nodes.json` are reserved and never become buttons.

```json
{
    "schema_version": 1,
    "samples": 0,
    "passes": { "combined": true, "depth": true, "mist": false }
}
```

Known pass keys: combined, depth, mist, position, normal, vector, uv, grease_pencil, denoising_data,
diffuse_direct/indirect/color, glossy_direct/indirect/color, transmission_direct/indirect/color,
volume_direct, volume_indirect, emission, environment, ambient_occlusion, cryptomatte_object,
cryptomatte_material. Keys starting with `_` are ignored (use them for comments).

## Basic settings (`basic_settings.json`)

Keys are plain Blender property names, grouped by the object they belong to. The shipped file lists every
supported option (about 100, covering the Output and Render tabs). **`null` means "not applied"** - set a value to
apply it, or set `null` / delete the line to leave that setting alone. Nothing outside the file is ever applied.

The full list with Blender UI names and valid values is in **BASIC_SETTINGS_REFERENCE.md**.

| Section | Target |
|---|---|
| `render` | `scene.render` (resolution, output path, stereoscopy, motion blur, persistent data, compositing, save_output, ...) |
| `image_settings` | `scene.render.image_settings` (media type, file format, color, depth, compression, EXR codec, ...) |
| `cycles` | `scene.cycles` (sampling, denoising, light paths, film, ...) |
| `eevee`, `scene` | free-form: any property name works, but there is no pre-listed menu |
| `world` | `surface_color`: `"#RRGGBB"`, `"#RRGGBBAA"` (sRGB hex) or a list of 3-4 linear floats |
| `outliner` | Outliner filter options: `show_restrict_column_holdout`, `show_restrict_column_indirect_only` |

Not covered on purpose: frame range, color management (use your OCIO setup), viewport-only settings.

Notes:

- `render.filepath` is always converted to forward slashes.
- `render.save_output: false` needs Blender 5.2+ (older versions skip it with a warning).
- With `save_output` off, keep `use_compositing` on - otherwise nothing is written at all.
- Settings that don't exist on your Blender version or render engine are skipped and listed in the warning.
- Keys starting with `_` are ignored, so the section dividers in the shipped file are harmless.

## Output nodes (`output_nodes.json`)

Drives **Build Output Node** in the Compositor tab. Select a Render Layers node and press the button.
Building again **replaces** the nodes generated earlier for that Render Layers node.

```json
{
    "schema_version": 1,
    "directory": "//../render/{VIEW_LAYER}/{PACKAGE}",
    "file_name": "{SCENE}_{VIEW_LAYER}_{PACKAGE}-",
    "node_width": 400,
    "rename_sockets": { "Image": "rgb" },
    "denoise": { "enabled": true, "passes": { "Diffuse Direct": "Diffuse Color", "Volume Direct": null } },
    "packages": [
        { "name": "AOV", "color": "#67AC0A", "match": ["*"],
          "save_as_render": true,
          "format": { "file_format": "OPEN_EXR_MULTILAYER", "color_depth": "32", "exr_codec": "DWAA", "quality": 65 } }
    ]
}
```

- **Tokens** in `directory` / `file_name`: `{SCENE}`, `{VIEW_LAYER}`, `{PACKAGE}` (the package name, e.g. AOV).
  Forward slashes only, no trailing slash on `directory`.
- **Packages** (default: AOV, DATA, CRYPTO): one File Output node each, placed top to bottom in list order.
  A pass goes to the first package whose `match` patterns fit (`*` = any characters, case-insensitive);
  specific patterns win over a catch-all `*`. Passes that match no package are not written.
  `format` keys are Blender properties of the node's image format; `file_format` is applied first.
- **Denoise:** each listed pass gets a collapsed Denoise node in front of its socket. With an albedo entry
  (`"Diffuse Direct": "Diffuse Color"`) the pass is only denoised if that Color pass and Normal are enabled,
  otherwise it passes through. With `null` (Volume Direct / Indirect) it is denoised from the image,
  plus Normal if that pass is enabled.
- **`rename_sockets`:** renames sockets in the File Output nodes, e.g. Image becomes `rgb`.
- Layout: nodes are placed right of the Render Layers node, from its top edge downward.

## Saving configs from the scene (Advanced)

The collapsed **Advanced** panel in the Layout tab has two buttons. Both ask for confirmation, keep a `.bak` copy
of what they overwrite, and only write to the *local* config folder. Copy the file into your production folder
to share it - the production sync overwrites local files on the next start.

- **Save Settings to Preset:** writes the scene's current values into `basic_settings.json`.
  Capture either only the settings that already have a value in the file, or all supported settings.
  Order, section dividers and untouched keys stay as they are.
- **Save Passes to Preset:** asks for a name (default: the active view layer's name) and writes the active
  view layer's passes to `Presets_Config/<Name>.json`, which then shows up as **Apply <Name> passes**.

## Validation

Files are validated on load. A broken file is skipped and its problem is listed in the add-on preferences
(and flagged in the sidebar). `schema_version` is currently `1`.
