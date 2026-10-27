import bpy

from . import config, sync


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_attr_path(base, dotted_path):
    """Walk 'a.b.c' from base. '' returns base itself. None if anything is missing."""
    obj = base
    if not dotted_path:
        return obj
    for part in dotted_path.split("."):
        if not hasattr(obj, part):
            return None
        obj = getattr(obj, part)
    return obj


def set_nested_attr(base, dotted_path, value, failures):
    """Set base.a.b.c = value. Missing attributes are collected into
    `failures` instead of raising, so one unavailable setting never blocks
    the rest."""
    *parents, last = dotted_path.split(".")
    obj = resolve_attr_path(base, ".".join(parents))
    if obj is None or not hasattr(obj, last):
        failures.append(dotted_path)
        return False
    try:
        setattr(obj, last, value)
        return True
    except Exception:
        failures.append(dotted_path)
        return False


def short_list(items, limit=8):
    items = list(items)
    text = ", ".join(items[:limit])
    if len(items) > limit:
        text += f" (+{len(items) - limit} more)"
    return text


# ---------------------------------------------------------------------------
# Apply pass preset
# ---------------------------------------------------------------------------

def resolve_preset_targets(context):
    """Which view layers a preset button applies to.

    In the Compositor: the view layer of every selected Render Layers node.
    Otherwise (or if no Render Layers node is selected): the active view layer.
    Returns (list of (scene, view_layer), from_selected_nodes)."""
    space = context.space_data
    tree = getattr(space, "node_tree", None)
    if getattr(space, "tree_type", None) == 'CompositorNodeTree' and tree is not None:
        targets, seen = [], set()
        for node in tree.nodes:
            if node.select and node.bl_idname == 'CompositorNodeRLayers':
                scene = node.scene or context.scene
                view_layer = scene.view_layers.get(node.layer) if scene else None
                if view_layer is not None and (scene.name, view_layer.name) not in seen:
                    seen.add((scene.name, view_layer.name))
                    targets.append((scene, view_layer))
        if targets:
            return targets, True

    if context.view_layer is not None:
        return [(context.scene, context.view_layer)], False
    return [], False


def target_description(context):
    """Text lines for the 'Target:' note above the preset buttons."""
    targets, from_nodes = resolve_preset_targets(context)
    if not targets:
        return ["No view layer found"]
    names = ", ".join(vl.name for _scene, vl in targets)
    lines = [f"Target: {names}"]
    in_compositor = getattr(context.space_data, "tree_type", None) == 'CompositorNodeTree'
    if in_compositor and not from_nodes:
        lines.append("Select a Render Layers node to target its layer")
    return lines


class BLENDDICE_OT_apply_pass_preset(bpy.types.Operator):
    bl_idname = "blenddice.apply_pass_preset"
    bl_label = "Apply Pass Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_name: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        return (f"Apply the '{properties.preset_name}' pass preset to the target view layer "
                "(the layer of the selected Render Layers node in the Compositor, otherwise the active view layer)")

    def execute(self, context):
        targets, _from_nodes = resolve_preset_targets(context)
        if not targets:
            self.report({'ERROR'}, "No view layer found")
            return {'CANCELLED'}

        preset = config.get_presets().get(self.preset_name)
        if preset is None:
            self.report({'ERROR'}, f"Preset '{self.preset_name}' not found - see Add-on Preferences")
            return {'CANCELLED'}

        failures = []
        for _scene, view_layer in targets:
            if "samples" in preset:
                set_nested_attr(view_layer, "samples", int(preset["samples"]), failures)
            for key, value in preset.get("passes", {}).items():
                if key.startswith("_"):
                    continue
                attr_path = config.PASS_ATTR_MAP.get(key)
                if attr_path is None:
                    continue   # already flagged as a warning when the file was loaded
                set_nested_attr(view_layer, attr_path, bool(value), failures)

        names = ", ".join(vl.name for _scene, vl in targets)
        if failures:
            self.report(
                {'WARNING'},
                f"Applied '{self.preset_name}' to '{names}', but skipped unavailable "
                f"settings: {short_list(sorted(set(failures)))}",
            )
        else:
            self.report({'INFO'}, f"Applied '{self.preset_name}' passes to view layer '{names}'")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Apply basic settings
# ---------------------------------------------------------------------------

# Within image_settings these must be set first (later keys depend on them).
IMAGE_SETTINGS_FIRST = ("media_type", "file_format")


class BLENDDICE_OT_apply_basic_settings(bpy.types.Operator):
    bl_idname = "blenddice.apply_basic_settings"
    bl_label = "Apply Basic Settings"
    bl_description = "Apply the settings from basic_settings.json to this scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        data = config.get_basic_settings()
        if data is None:
            self.report({'ERROR'}, "basic_settings.json is missing or invalid - see Add-on Preferences")
            return {'CANCELLED'}

        scene = context.scene
        applied = 0
        failures = []

        for section, base_path in config.SECTION_TARGETS.items():
            values = data.get(section)
            if not isinstance(values, dict):
                continue

            base = resolve_attr_path(scene, base_path)
            if base is None:
                failures.append(f"{section} (not available)")
                continue

            # null = listed in the config but not applied
            keys = [k for k in values if not k.startswith("_") and values[k] is not None]
            if section == "image_settings":
                keys.sort(key=lambda k: IMAGE_SETTINGS_FIRST.index(k) if k in IMAGE_SETTINGS_FIRST else 99)

            for key in keys:
                value = values[key]
                # The render farm can't handle backslashes - forward slashes only
                if section == "render" and key == "filepath" and isinstance(value, str):
                    value = value.replace("\\", "/")
                if set_nested_attr(base, key, value, []):
                    applied += 1
                else:
                    failures.append(f"{section}.{key}")

        world_cfg = data.get("world")
        if isinstance(world_cfg, dict) and world_cfg.get("surface_color") is not None:
            if self._apply_world_color(scene, config.parse_color(world_cfg["surface_color"])):
                applied += 1
            else:
                failures.append("world.surface_color (no Background node)")

        notes = []
        outliner_cfg = data.get("outliner")
        if isinstance(outliner_cfg, dict):
            count = self._apply_outliner(outliner_cfg)
            if count:
                applied += 1
            else:
                notes.append("no Outliner found to update")

        message = f"Applied {applied} basic settings"
        if notes:
            message += " (" + "; ".join(notes) + ")"
        if failures:
            self.report({'WARNING'}, message + f" - skipped: {short_list(failures)}")
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}

    @staticmethod
    def _apply_world_color(scene, color):
        if color is None:
            return False
        world = scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            scene.world = world
        if hasattr(world, "use_nodes") and not world.use_nodes:
            try:
                world.use_nodes = True
            except Exception:
                pass

        tree = world.node_tree
        if tree is None:
            return False
        bg = tree.nodes.get("Background") or next(
            (n for n in tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None
        )
        if bg is None or "Color" not in bg.inputs:
            return False
        bg.inputs["Color"].default_value = color
        return True

    @staticmethod
    def _apply_outliner(outliner_cfg):
        """Set outliner filter options (e.g. the Holdout / Indirect Only
        columns) on every Outliner in every workspace. Returns how many
        Outliners were updated."""
        count = 0
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type != 'OUTLINER':
                    continue
                for space in area.spaces:
                    if space.type != 'OUTLINER':
                        continue
                    for key, value in outliner_cfg.items():
                        if key.startswith("_") or value is None or not hasattr(space, key):
                            continue
                        try:
                            setattr(space, key, value)
                        except Exception:
                            pass
                    count += 1
                area.tag_redraw()
        return count


# ---------------------------------------------------------------------------
# Config utilities (used from the add-on preferences)
# ---------------------------------------------------------------------------

class BLENDDICE_OT_sync_presets(bpy.types.Operator):
    bl_idname = "blenddice.sync_presets"
    bl_label = "Sync Now"
    bl_description = "Copy the latest preset configs from the production folder (runs in the background)"

    def execute(self, context):
        prefs = config.get_prefs()
        path = prefs.production_path if prefs else ""
        if sync.start(path):
            self.report({'INFO'}, "Sync started")
        elif sync.is_running():
            self.report({'INFO'}, "A sync is already running")
        else:
            self.report({'WARNING'}, sync.status["message"])
        return {'FINISHED'}


class BLENDDICE_OT_reload_configs(bpy.types.Operator):
    bl_idname = "blenddice.reload_configs"
    bl_label = "Reload Configs"
    bl_description = "Re-read the local preset and basic settings files from disk"

    def execute(self, context):
        config.reload_configs()
        errors = config.get_errors()
        if errors:
            self.report({'WARNING'}, f"{len(config.get_presets())} presets loaded, {len(errors)} problem(s)")
        else:
            self.report({'INFO'}, f"{len(config.get_presets())} presets loaded")
        return {'FINISHED'}


class BLENDDICE_OT_open_config_folder(bpy.types.Operator):
    bl_idname = "blenddice.open_config_folder"
    bl_label = "Open Config Folder"
    bl_description = "Open the folder containing the preset and basic settings config files"

    def execute(self, context):
        try:
            config.seed_defaults()
            bpy.ops.wm.path_open(filepath=config.get_config_root())
        except Exception as e:
            self.report({'ERROR'}, f"Could not open the config folder: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (
    BLENDDICE_OT_apply_pass_preset,
    BLENDDICE_OT_apply_basic_settings,
    BLENDDICE_OT_sync_presets,
    BLENDDICE_OT_reload_configs,
    BLENDDICE_OT_open_config_folder,
)
