"""Config handling for Blenddice Render Manager.

Layout in the per-user extension folder (survives add-on updates):

    <user extension folder>/
        Presets_Config/        one .json per pass preset (file name = button name)
        basic_settings.json    the "Apply Basic Settings" config
        output_nodes.json      the "Build Output Node" config (packages, paths, denoise)

Bundled defaults (config_defaults/ inside the add-on) are copied there on first
run, but only for files that don't exist yet - existing files are never touched.
The production sync (sync.py) overwrites local files with the production ones.

Everything is cached: the UI only reads the cache, never the disk.
"""

import json
import os
import re
import shutil

import bpy

SCHEMA_VERSION = 1
PRESETS_DIR_NAME = "Presets_Config"
BASIC_SETTINGS_FILENAME = "basic_settings.json"
BASIC_SETTINGS_STEM = "basic_settings"   # never treated as a preset
OUTPUT_NODES_FILENAME = "output_nodes.json"
OUTPUT_NODES_STEM = "output_nodes"
RESERVED_STEMS = (BASIC_SETTINGS_STEM, OUTPUT_NODES_STEM)   # never treated as presets
DEFAULT_PRESET_NAME = "Default"

# Tokens usable in output_nodes.json path / file name templates
TOKENS = ("SCENE", "VIEW_LAYER", "PACKAGE")

# Pass preset key (used in the preset .json files) -> view layer attribute path.
PASS_ATTR_MAP = {
    "combined": "use_pass_combined",
    "depth": "use_pass_z",
    "mist": "use_pass_mist",
    "position": "use_pass_position",
    "normal": "use_pass_normal",
    "vector": "use_pass_vector",
    "uv": "use_pass_uv",
    "grease_pencil": "use_pass_grease_pencil",
    "denoising_data": "cycles.denoising_store_passes",
    "diffuse_direct": "use_pass_diffuse_direct",
    "diffuse_indirect": "use_pass_diffuse_indirect",
    "diffuse_color": "use_pass_diffuse_color",
    "glossy_direct": "use_pass_glossy_direct",
    "glossy_indirect": "use_pass_glossy_indirect",
    "glossy_color": "use_pass_glossy_color",
    "transmission_direct": "use_pass_transmission_direct",
    "transmission_indirect": "use_pass_transmission_indirect",
    "transmission_color": "use_pass_transmission_color",
    "volume_direct": "cycles.use_pass_volume_direct",
    "volume_indirect": "cycles.use_pass_volume_indirect",
    "emission": "use_pass_emit",
    "environment": "use_pass_environment",
    "ambient_occlusion": "use_pass_ambient_occlusion",
    "cryptomatte_object": "use_pass_cryptomatte_object",
    "cryptomatte_material": "use_pass_cryptomatte_material",
}

# basic_settings.json section -> attribute path on the scene. Keys inside a
# section are plain Blender property names on that object. Color management
# is deliberately not available: it is controlled by the studio's OCIO setup.
SECTION_TARGETS = {
    "scene": "",
    "render": "render",
    "image_settings": "render.image_settings",
    "cycles": "cycles",
    "eevee": "eevee",
}
SPECIAL_SECTIONS = ("world", "outliner")

_state = {
    "presets": {},
    "basic": None,
    "output": None,
    "errors": [],
    "warnings": [],
}


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def get_config_root():
    try:
        return bpy.utils.extension_path_user(__package__, path="", create=True)
    except Exception:
        return bpy.utils.user_resource('CONFIG', path="blenddice_render_manager", create=True)


def get_presets_dir():
    return os.path.join(get_config_root(), PRESETS_DIR_NAME)


def get_basic_settings_path():
    return os.path.join(get_config_root(), BASIC_SETTINGS_FILENAME)


def get_output_nodes_path():
    return os.path.join(get_config_root(), OUTPUT_NODES_FILENAME)


def get_bundled_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_defaults")


def get_prefs():
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return None


# ---------------------------------------------------------------------------
# First-run seeding (copy bundled defaults, never overwrite)
# ---------------------------------------------------------------------------

def seed_defaults():
    presets_dir = get_presets_dir()
    os.makedirs(presets_dir, exist_ok=True)

    bundled = get_bundled_dir()
    bundled_presets = os.path.join(bundled, PRESETS_DIR_NAME)
    if os.path.isdir(bundled_presets):
        for fn in os.listdir(bundled_presets):
            if fn.lower().endswith(".json"):
                dst = os.path.join(presets_dir, fn)
                if not os.path.exists(dst):
                    shutil.copyfile(os.path.join(bundled_presets, fn), dst)

    for filename, local in ((BASIC_SETTINGS_FILENAME, get_basic_settings_path()),
                            (OUTPUT_NODES_FILENAME, get_output_nodes_path())):
        bundled_file = os.path.join(bundled, filename)
        if os.path.isfile(bundled_file) and not os.path.exists(local):
            shutil.copyfile(bundled_file, local)


def read_bundled_json(filename):
    """The shipped default of a root-level config file, or None."""
    data, err = _read_json(os.path.join(get_bundled_dir(), filename))
    return None if err else data


# ---------------------------------------------------------------------------
# Reading + validation
# ---------------------------------------------------------------------------

def _read_json(path):
    try:
        # utf-8-sig tolerates the BOM that Windows Notepad likes to add
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}"
    except OSError as e:
        return None, f"cannot read file: {e}"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_schema(data, errors, warnings):
    version = data.get("schema_version")
    if version is None:
        warnings.append("no schema_version, assuming 1")
    elif not _is_int(version):
        errors.append("schema_version must be a whole number")
    elif version > SCHEMA_VERSION:
        errors.append(
            f"schema_version {version} needs a newer plugin version "
            f"(this one supports up to {SCHEMA_VERSION})"
        )


def validate_preset(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], warnings
    _check_schema(data, errors, warnings)

    if "samples" in data and (not _is_int(data["samples"]) or data["samples"] < 0):
        errors.append("'samples' must be a whole number >= 0")

    passes = data.get("passes")
    if not isinstance(passes, dict):
        errors.append("'passes' is missing or not an object")
    else:
        for key, value in passes.items():
            if key.startswith("_"):
                continue
            if not isinstance(value, bool):
                errors.append(f"pass '{key}' must be true or false")
            elif key not in PASS_ATTR_MAP:
                warnings.append(f"unknown pass '{key}' (will be ignored)")
    return errors, warnings


def parse_color(value):
    """Accept '#RRGGBB', '#RRGGBBAA' (sRGB hex, converted to linear) or a list
    of 3-4 linear floats. Returns an (r, g, b, a) tuple or None if invalid."""
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) not in (6, 8):
            return None
        try:
            channels = [int(text[i:i + 2], 16) / 255.0 for i in range(0, len(text), 2)]
        except ValueError:
            return None
        if len(channels) == 3:
            channels.append(1.0)

        def to_linear(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        return (to_linear(channels[0]), to_linear(channels[1]),
                to_linear(channels[2]), channels[3])

    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        if all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in value):
            rgba = [float(c) for c in value]
            if len(rgba) == 3:
                rgba.append(1.0)
            return tuple(rgba)
    return None


def validate_basic_settings(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], warnings
    _check_schema(data, errors, warnings)

    for key, value in data.items():
        if key.startswith("_") or key == "schema_version":
            continue
        if key in SECTION_TARGETS or key in SPECIAL_SECTIONS:
            if not isinstance(value, dict):
                errors.append(f"section '{key}' must be an object")
        else:
            warnings.append(f"unknown section '{key}' (will be ignored)")

    world = data.get("world")
    if isinstance(world, dict) and world.get("surface_color") is not None:
        if parse_color(world["surface_color"]) is None:
            errors.append("world.surface_color must be '#RRGGBB', '#RRGGBBAA' or a list of 3-4 numbers")
    return errors, warnings


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_TOKEN = re.compile(r"\{([A-Za-z_]+)\}")


def validate_output_nodes(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], warnings
    _check_schema(data, errors, warnings)

    for key in ("directory", "file_name"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"'{key}' must be a non-empty text")
            continue
        for token in _TOKEN.findall(value):
            if token not in TOKENS:
                warnings.append(f"'{key}': unknown token {{{token}}} (known: {', '.join(TOKENS)})")

    width = data.get("node_width")
    if width is not None and (isinstance(width, bool) or not isinstance(width, (int, float)) or width <= 0):
        errors.append("'node_width' must be a positive number")

    rename = data.get("rename_sockets")
    if rename is not None:
        if not isinstance(rename, dict) or not all(isinstance(v, str) for v in rename.values()):
            errors.append("'rename_sockets' must be an object of text values")

    denoise = data.get("denoise")
    if denoise is not None:
        if not isinstance(denoise, dict):
            errors.append("'denoise' must be an object")
        else:
            if "enabled" in denoise and not isinstance(denoise["enabled"], bool):
                errors.append("'denoise.enabled' must be true or false")
            passes = denoise.get("passes", {})
            if not isinstance(passes, dict) or not all(
                    v is None or isinstance(v, str) for k, v in passes.items() if not k.startswith("_")):
                errors.append("'denoise.passes' must map pass names to an albedo pass name or null")

    packages = data.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("'packages' must be a non-empty list")
    else:
        seen = set()
        has_catch_all = False
        for i, pkg in enumerate(packages, 1):
            label = f"package {i}"
            if not isinstance(pkg, dict):
                errors.append(f"{label} must be an object")
                continue
            name = pkg.get("name")
            if not isinstance(name, str) or not name.strip() or any(c in name for c in '/\\:*?"<>|'):
                errors.append(f"{label}: 'name' must be a text without special characters")
            elif name.lower() in seen:
                errors.append(f"{label}: duplicate package name '{name}'")
            else:
                seen.add(name.lower())
                label = f"package '{name}'"
            match = pkg.get("match")
            if not isinstance(match, list) or not match or not all(isinstance(m, str) for m in match):
                errors.append(f"{label}: 'match' must be a non-empty list of pass name patterns")
            elif "*" in match:
                has_catch_all = True
            color = pkg.get("color")
            if color is not None and not (isinstance(color, str) and _HEX_COLOR.match(color)):
                errors.append(f"{label}: 'color' must look like '#RRGGBB'")
            if "format" in pkg and not isinstance(pkg["format"], dict):
                errors.append(f"{label}: 'format' must be an object")
        if not has_catch_all and not errors:
            warnings.append("no package matches '*': passes matched by no package are not written")
    return errors, warnings


# ---------------------------------------------------------------------------
# Loading + cache
# ---------------------------------------------------------------------------

def reload_configs():
    """Re-read everything from disk into the cache. Never raises."""
    presets, basic, output = {}, None, None
    errors, warnings = [], []

    try:
        seed_defaults()

        presets_dir = get_presets_dir()
        for fn in sorted(os.listdir(presets_dir), key=str.lower):
            stem, ext = os.path.splitext(fn)
            if ext.lower() != ".json" or stem.lower() in RESERVED_STEMS:
                continue
            data, err = _read_json(os.path.join(presets_dir, fn))
            if err:
                errors.append(f"{fn}: {err}")
                continue
            file_errors, file_warnings = validate_preset(data)
            warnings.extend(f"{fn}: {m}" for m in file_warnings)
            if file_errors:
                errors.extend(f"{fn}: {m}" for m in file_errors)
                continue
            presets[stem] = data

        basic_path = get_basic_settings_path()
        if os.path.isfile(basic_path):
            data, err = _read_json(basic_path)
            if err:
                errors.append(f"{BASIC_SETTINGS_FILENAME}: {err}")
            else:
                file_errors, file_warnings = validate_basic_settings(data)
                warnings.extend(f"{BASIC_SETTINGS_FILENAME}: {m}" for m in file_warnings)
                if file_errors:
                    errors.extend(f"{BASIC_SETTINGS_FILENAME}: {m}" for m in file_errors)
                else:
                    basic = data
        else:
            errors.append(f"{BASIC_SETTINGS_FILENAME}: file not found")

        output_path = get_output_nodes_path()
        if os.path.isfile(output_path):
            data, err = _read_json(output_path)
            if err:
                errors.append(f"{OUTPUT_NODES_FILENAME}: {err}")
            else:
                file_errors, file_warnings = validate_output_nodes(data)
                warnings.extend(f"{OUTPUT_NODES_FILENAME}: {m}" for m in file_warnings)
                if file_errors:
                    errors.extend(f"{OUTPUT_NODES_FILENAME}: {m}" for m in file_errors)
                else:
                    output = data
        else:
            errors.append(f"{OUTPUT_NODES_FILENAME}: file not found")
    except Exception as e:  # a broken config must never break the UI
        errors.append(f"config could not be loaded: {e}")

    _state["presets"] = presets
    _state["basic"] = basic
    _state["output"] = output
    _state["errors"] = errors
    _state["warnings"] = warnings


def get_presets():
    return _state["presets"]


def get_preset_names():
    """Preset names for the UI: 'Default' first, the rest alphabetical."""
    names = sorted(_state["presets"], key=str.lower)
    for name in names:
        if name.lower() == DEFAULT_PRESET_NAME.lower():
            names.remove(name)
            names.insert(0, name)
            break
    return names


def get_basic_settings():
    return _state["basic"]


def get_output_nodes():
    return _state["output"]


def get_errors():
    return _state["errors"]


def get_warnings():
    return _state["warnings"]
