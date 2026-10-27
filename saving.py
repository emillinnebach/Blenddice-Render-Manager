"""Turn the current scene back into config files.

  - Save Settings to Preset: writes the scene's current values into the local basic_settings.json
  - Save Passes to Preset:   writes the active view layer's passes as a new/updated Presets_Config/<Name>.json

Both ask for confirmation first, keep a .bak copy of anything they overwrite and write atomically.
Production sync overwrites local files on the next start - copy the saved file into the
production folder yourself to publish it.
"""

import copy
import json
import os
import re
import shutil

import bpy

from . import config
from .operators import resolve_attr_path

_MISSING = object()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def write_json_atomic(path, data, backup=True):
    """Write JSON next to its final place, then swap it in. Keeps a .bak of the old file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if backup and os.path.exists(path):
        shutil.copyfile(path, path + ".bak")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def production_path_set():
    prefs = config.get_prefs()
    return bool(prefs and (prefs.production_path or "").strip())


def to_json_value(value):
    """A Blender property value as something JSON can store, or _MISSING."""
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (set, frozenset, dict)):
        return _MISSING
    try:
        items = [to_json_value(v) for v in value]
    except TypeError:
        return _MISSING
    return _MISSING if any(i is _MISSING for i in items) else items


def color_to_hex(rgba):
    """Linear RGBA -> '#RRGGBBAA' (sRGB hex), the inverse of config.parse_color."""
    def to_srgb(c):
        c = max(0.0, min(1.0, c))
        return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055

    channels = [to_srgb(rgba[0]), to_srgb(rgba[1]), to_srgb(rgba[2]), max(0.0, min(1.0, rgba[3]))]
    return "#" + "".join(f"{round(c * 255):02X}" for c in channels)


def current_world_color(scene):
    world = scene.world
    tree = world.node_tree if world else None
    if tree is None:
        return None
    bg = tree.nodes.get("Background") or next(
        (n for n in tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
    if bg is None or "Color" not in bg.inputs:
        return None
    return color_to_hex(bg.inputs["Color"].default_value)


# ---------------------------------------------------------------------------
# Save settings to preset
# ---------------------------------------------------------------------------

def candidate_keys(existing, bundled, mode):
    """(section, key) pairs to capture. SET = only keys that already have a value in the
    file; ALL = every key the file or the shipped default lists."""
    pairs = []
    for section in config.SECTION_TARGETS:
        current = existing.get(section) if isinstance(existing.get(section), dict) else {}
        if mode == 'ALL':
            shipped = bundled.get(section) if isinstance(bundled.get(section), dict) else {}
            names = [k for k in current if not k.startswith("_")]
            names += [k for k in shipped if not k.startswith("_") and k not in current]
        else:
            names = [k for k, v in current.items() if not k.startswith("_") and v is not None]
        pairs.extend((section, name) for name in names)
    return pairs


def build_new_settings(scene, existing, bundled, mode):
    """Returns (new_data, written, skipped): the file content with the scene's current
    values filled in (order, dividers and untouched keys preserved)."""
    new_data = copy.deepcopy(existing)
    written, skipped = [], []

    for section, key in candidate_keys(existing, bundled, mode):
        base = resolve_attr_path(scene, config.SECTION_TARGETS[section])
        if base is None or not hasattr(base, key):
            skipped.append(f"{section}.{key}")
            continue
        value = to_json_value(getattr(base, key))
        if value is _MISSING:
            skipped.append(f"{section}.{key}")
            continue
        if section == "render" and key == "filepath" and isinstance(value, str):
            value = value.replace("\\", "/")
        new_data.setdefault(section, {})[key] = value
        written.append((section, key))

    world_cfg = existing.get("world") if isinstance(existing.get("world"), dict) else {}
    if mode == 'ALL' or world_cfg.get("surface_color") is not None:
        color = current_world_color(scene)
        if color is not None:
            new_data.setdefault("world", {})["surface_color"] = color
            written.append(("world", "surface_color"))
        else:
            skipped.append("world.surface_color")

    return new_data, written, skipped


def count_changes(existing, new_data, written):
    def lookup(data, section, key):
        sec = data.get(section)
        return sec.get(key) if isinstance(sec, dict) else None
    return sum(1 for section, key in written if lookup(existing, section, key) != lookup(new_data, section, key))


def load_settings_for_saving():
    """(existing_data, bundled_data, error)"""
    path = config.get_basic_settings_path()
    if os.path.isfile(path):
        existing, err = config._read_json(path)
        if err:
            return None, None, f"basic_settings.json is invalid ({err}) - fix it or delete it to restore the defaults"
        errors, _warnings = config.validate_basic_settings(existing)
        if errors:
            return None, None, "basic_settings.json has errors - fix it first: " + errors[0]
    else:
        existing = config.read_bundled_json(config.BASIC_SETTINGS_FILENAME) or {"schema_version": config.SCHEMA_VERSION}
    bundled = config.read_bundled_json(config.BASIC_SETTINGS_FILENAME) or {}
    return existing, bundled, None


def _confirm_dialog(context, operator, width, title, confirm_text):
    wm = context.window_manager
    try:
        return wm.invoke_props_dialog(operator, width=width, title=title, confirm_text=confirm_text)
    except TypeError:    # older Blender without title / confirm_text
        return wm.invoke_props_dialog(operator, width=width)


class BLENDDICE_OT_save_basic_settings(bpy.types.Operator):
    bl_idname = "blenddice.save_basic_settings"
    bl_label = "Save Settings to Preset"
    bl_description = "Write this scene's current settings into the local basic_settings.json (asks for confirmation)"
    bl_options = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        name="Capture",
        items=(
            ('SET', "Only settings already set in the file", "Update the values that already have a value in basic_settings.json"),
            ('ALL', "All supported settings", "Capture every supported option, also the ones that are currently null"),
        ),
        default='SET',
    )

    def invoke(self, context, event):
        return _confirm_dialog(context, self, 480, "Save Settings to Preset", "Overwrite basic_settings.json")

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.alert = True
        col.label(text="This overwrites your local basic_settings.json.", icon='ERROR')
        col.alert = False
        col.label(text="The previous file is kept as basic_settings.json.bak.")

        layout.separator()
        layout.prop(self, "mode", expand=True)

        existing, bundled, err = load_settings_for_saving()
        if err:
            box = layout.box()
            box.alert = True
            box.label(text=err, icon='ERROR')
            return
        _new, written, skipped = build_new_settings(context.scene, existing, bundled, self.mode)
        changed = count_changes(existing, _new, written)
        layout.label(text=f"Scene '{context.scene.name}': {len(written)} settings are written, {changed} change the file.")
        if skipped:
            layout.label(text=f"{len(skipped)} not available in this Blender / engine, left as they are.")
        if production_path_set():
            layout.label(text="A production path is set: the next startup replaces this file with the production one.", icon='INFO')

    def execute(self, context):
        existing, bundled, err = load_settings_for_saving()
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        new_data, written, skipped = build_new_settings(context.scene, existing, bundled, self.mode)
        try:
            write_json_atomic(config.get_basic_settings_path(), new_data)
        except OSError as e:
            self.report({'ERROR'}, f"Could not write basic_settings.json: {e}")
            return {'CANCELLED'}

        config.reload_configs()
        message = f"Saved {len(written)} settings to basic_settings.json (backup: basic_settings.json.bak)"
        if skipped:
            self.report({'WARNING'}, message + f" - {len(skipped)} not available and left unchanged")
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Save passes to preset
# ---------------------------------------------------------------------------

_INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_preset_name(name):
    return _INVALID_NAME_CHARS.sub("", name or "").strip().strip(".").strip()


def preset_path(name):
    return os.path.join(config.get_presets_dir(), name + ".json")


def capture_passes(view_layer):
    """(preset_dict, skipped_keys) from a view layer's current pass settings."""
    passes, skipped = {}, []
    for key, attr_path in config.PASS_ATTR_MAP.items():
        value = resolve_attr_path(view_layer, attr_path)
        if isinstance(value, bool):
            passes[key] = value
        else:
            skipped.append(key)
    preset = {"schema_version": config.SCHEMA_VERSION}
    if hasattr(view_layer, "samples"):
        preset["samples"] = int(view_layer.samples)
    preset["passes"] = passes
    return preset, skipped


class BLENDDICE_OT_save_passes_preset(bpy.types.Operator):
    bl_idname = "blenddice.save_passes_preset"
    bl_label = "Save Passes to Preset"
    bl_description = "Save the pass settings of the active view layer as a preset file (asks for a name)"
    bl_options = {'REGISTER'}

    preset_name: bpy.props.StringProperty(name="Preset Name", default="")

    def invoke(self, context, event):
        self.preset_name = sanitize_preset_name(context.view_layer.name) if context.view_layer else ""
        return _confirm_dialog(context, self, 420, "Save Passes to Preset", "Save Preset")

    def draw(self, context):
        layout = self.layout
        if context.view_layer:
            layout.label(text=f"Passes of view layer '{context.view_layer.name}'", icon='RENDERLAYERS')
        layout.prop(self, "preset_name")

        name = sanitize_preset_name(self.preset_name)
        if not name:
            layout.alert = True
            layout.label(text="Enter a name.", icon='ERROR')
            return
        if name.lower() in config.RESERVED_STEMS:
            layout.alert = True
            layout.label(text=f"'{name}' is reserved for a config file.", icon='ERROR')
            return
        if os.path.exists(preset_path(name)):
            col = layout.column(align=True)
            col.alert = True
            col.label(text=f"{name}.json exists and will be overwritten (backup kept).", icon='ERROR')
        else:
            layout.label(text=f"New preset {name}.json - button: Apply {name} passes", icon='INFO')
        if production_path_set():
            layout.label(text="A production preset with this name replaces it on the next startup.", icon='INFO')

    def execute(self, context):
        view_layer = context.view_layer
        if view_layer is None:
            self.report({'ERROR'}, "No active view layer found")
            return {'CANCELLED'}

        name = sanitize_preset_name(self.preset_name)
        if not name:
            self.report({'ERROR'}, "Enter a preset name")
            return {'CANCELLED'}
        if name.lower() in config.RESERVED_STEMS:
            self.report({'ERROR'}, f"'{name}' is reserved for a config file")
            return {'CANCELLED'}

        preset, skipped = capture_passes(view_layer)
        if not preset["passes"]:
            self.report({'ERROR'}, "No pass settings could be read from this view layer")
            return {'CANCELLED'}

        try:
            write_json_atomic(preset_path(name), preset)
        except OSError as e:
            self.report({'ERROR'}, f"Could not write {name}.json: {e}")
            return {'CANCELLED'}

        config.reload_configs()
        message = f"Saved preset '{name}' ({len(preset['passes'])} passes) - button: Apply {name} passes"
        if skipped:
            self.report({'WARNING'}, message + f"; not available here: {', '.join(skipped)}")
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}


classes = (
    BLENDDICE_OT_save_basic_settings,
    BLENDDICE_OT_save_passes_preset,
)
