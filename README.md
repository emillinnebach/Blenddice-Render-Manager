# Blenddice Render Manager

Extension to apply render pass configs to view layers and auto output node generator. Enables you to share your ViewLayer presets across your production. Edit the config files to set up.
Created with heavy use of CLAUDE CODE!

## Features

- **Pass presets:** one `.json` file per preset. The file name becomes the button: `Environment.json` gives **Apply Environment passes**. Applies to the active view layer (or, in the Compositor, the layer of the selected Render Layers node).
- **Apply Basic Settings:** about 100 Output and Render tab options (resolution, file format, sampling, denoising, light paths, motion blur, ...) from `basic_settings.json`. Only the options you set are applied (`null` = untouched).
- **Build Output Node:** builds File Output nodes (AOV / DATA / CRYPTO) for a selected Render Layers node, with Denoise nodes, from `output_nodes.json`. Rebuilding replaces the earlier nodes.
- **Production sync:** point the add-on at a pipeline folder and the presets are copied to every artist's machine on startup, in the background.
- **Save back:** write the current scene settings or a view layer's passes into config files.

Sidebar tab: **Blenddice Render Setup** (3D Viewport and Compositor).

## Install

1. Download `Blenddice_Render_Manager_vX.Y.Z.zip` from the [Releases](../../releases) page.
2. Blender: **Edit > Preferences > Get Extensions**, open the drop-down at the top right, **Install from Disk**, pick the zip.
3. If the old *Breakdice Render Manager* is installed, remove it first.

Requires Blender 4.2 or newer. Developed and tested on Blender 5.0. One setting (`render.save_output`, the Output checkbox) needs Blender 5.2 and is skipped with a warning on older versions.

## Set up for your production

In **Preferences > Add-ons > Blenddice Render Manager**:

- **Production Presets:** path to the folder with your config files. If set, local presets are overwritten by the production presets on every startup. Leave empty to skip the sync.
- **Settings: Open Config Folder:** opens the local config folder.

Start from the files in [`config_defaults/`](config_defaults/), adjust them, and put them in your pipeline folder. Full reference: [docs/CONFIG_README.md](docs/CONFIG_README.md). All basic settings with their Blender UI names and valid values: [docs/BASIC_SETTINGS_REFERENCE.md](docs/BASIC_SETTINGS_REFERENCE.md).

## Repository layout

The add-on files sit at the repository root, as Blender's extension manifest expects them inside the install zip.

| Path | |
|---|---|
| `blender_manifest.toml` | extension metadata and version |
| `__init__.py`, `*.py` | the add-on |
| `config_defaults/` | bundled default configs (copied to the user folder on first run) |
| `docs/` | config reference |

## Building a release zip

1. Update the version in `blender_manifest.toml` and add an entry to [CHANGELOG.md](CHANGELOG.md).
2. Zip the **contents** of the repository, not the folder itself, so that `blender_manifest.toml` is at the top level of the zip. Leave out `.git`.
3. Name it `Blenddice_Render_Manager_vX.Y.Z.zip` and attach it to a GitHub Release.

## License

GPL-2.0-or-later, see [LICENSE](LICENSE).
