"""Shot tools: light group creation and camera export.

Light groups:
  Select light(s) in the 3D viewport and press "Create Light Group". One light
  gets a group named after itself, several lights share one group (default
  name "Lightgroup"). Blender allows only ONE light group per object, and that
  assignment is the same in every view layer, so lights that already belong to
  another (existing) group are skipped and reported, unless "Reassign" is on.

Camera export:
  Writes the scene's active camera as an Alembic (.abc) file for Nuke, using
  the "camera" block of output_nodes.json. Blender's exporter converts to Y-up
  and adds the Maya-style camera orientation itself. Existing files are never
  overwritten: the version number goes up (_v001, _v002, ...).
"""

import os
import re

import bpy

from . import config
from .compositor import clean_directory
from .operators import resolve_preset_targets, short_list

DEFAULT_GROUP_NAME = "Lightgroup"


# ---------------------------------------------------------------------------
# Light groups
# ---------------------------------------------------------------------------

def light_group_name(text):
    """Blender turns '.' into '_' in light group names (it would clash with the
    EXR channel naming), so do the same up front to match existing groups."""
    return (text or "").strip().replace(".", "_")


def next_numbered_name(base, view_layers):
    """base_001, base_002, ... - the first one no target view layer has yet."""
    number = 1
    while any(f"{base}_{number:03d}" in vl.lightgroups for vl in view_layers):
        number += 1
    return f"{base}_{number:03d}"


def selected_lights(context):
    view_layer = context.view_layer
    if view_layer is None:
        return []
    return [o for o in view_layer.objects if o.type == 'LIGHT' and o.select_get(view_layer=view_layer)]


def remove_unused_groups(group_names):
    """Delete light groups nothing is assigned to anymore, from every view layer of
    every scene. Only the given names are looked at, other empty groups stay.
    Returns the names that were removed."""
    removed = []
    for name in sorted(set(group_names)):
        in_use = any(getattr(obj, "lightgroup", "") == name for obj in bpy.data.objects)
        in_use = in_use or any(getattr(world, "lightgroup", "") == name for world in (bpy.data.worlds or []))
        if in_use:
            continue
        for scene in bpy.data.scenes:
            for view_layer in scene.view_layers:
                group = view_layer.lightgroups.get(name)
                if group is not None:
                    view_layer.lightgroups.remove(group)
        removed.append(name)
    return removed


class BLENDDICE_OT_create_light_group(bpy.types.Operator):
    """Create a light group from the selected light(s) and assign them to it"""
    bl_idname = "blenddice.create_light_group"
    bl_label = "Create Light Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: bpy.props.StringProperty(
        name="Group Name",
        description="Name used when several lights are selected (one light uses its own name). The default name creates a new numbered group each time (Lightgroup_001, Lightgroup_002, ...)",
        default=DEFAULT_GROUP_NAME,
    )
    reassign: bpy.props.BoolProperty(
        name="Reassign",
        description="Also move lights that are already in another light group (the old group loses them in every view layer)",
        default=False,
    )
    all_view_layers: bpy.props.BoolProperty(
        name="All View Layers",
        description="Create the group in every view layer of the scene, not only the target one",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.view_layer is not None

    def _plan(self, context):
        """Returns (lights, view_layers, group name, to_assign, conflicts).
        conflicts = [(light, current group)] for lights in another existing group."""
        lights = selected_lights(context)
        if self.all_view_layers:
            view_layers = list(context.scene.view_layers)
        else:
            view_layers = [vl for _scene, vl in resolve_preset_targets(context)[0]]

        if len(lights) == 1:
            name = light_group_name(lights[0].name)
        else:
            name = light_group_name(self.group_name) or DEFAULT_GROUP_NAME
            if len(lights) > 1 and name.lower() == DEFAULT_GROUP_NAME.lower():
                # Several lights with the default name: always a NEW group (Lightgroup_001, _002, ...)
                name = next_numbered_name(DEFAULT_GROUP_NAME, view_layers)

        to_assign, conflicts = [], []
        for light in lights:
            current = light.lightgroup
            is_live_group = bool(current) and any(current in vl.lightgroups for vl in view_layers)
            if current != name and is_live_group:
                conflicts.append((light, current))
            else:
                to_assign.append(light)
        return lights, view_layers, name, to_assign, conflicts

    def invoke(self, context, event):
        lights, _view_layers, _name, _to_assign, conflicts = self._plan(context)
        if conflicts and not self.reassign:
            self._conflicts = conflicts
            self.reassign = True   # confirming the dialog means "overwrite"
            try:
                return context.window_manager.invoke_props_dialog(self, width=420, confirm_text="Overwrite")
            except TypeError:   # older Blender without confirm_text
                return context.window_manager.invoke_props_dialog(self, width=420)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        conflicts = getattr(self, "_conflicts", None)
        if not conflicts:
            layout.prop(self, "group_name")
            layout.prop(self, "reassign")
            layout.prop(self, "all_view_layers")
            return
        col = layout.column(align=True)
        col.alert = True
        col.label(text="These lights are already in a light group:", icon='ERROR')
        for light, group in conflicts[:8]:
            col.label(text=f"{light.name}  ({group})")
        if len(conflicts) > 8:
            col.label(text=f"... and {len(conflicts) - 8} more")
        layout.label(text="Overwrite removes them from their current group.")

    def execute(self, context):
        lights, view_layers, name, to_assign, conflicts = self._plan(context)
        if not lights:
            self.report({'WARNING'}, "Select at least one light")
            return {'CANCELLED'}
        if not view_layers:
            self.report({'ERROR'}, "No view layer found")
            return {'CANCELLED'}
        if not name:
            self.report({'ERROR'}, "The light has no usable name")
            return {'CANCELLED'}

        skipped = []
        if conflicts:
            if self.reassign:
                to_assign.extend(light for light, _group in conflicts)   # assigning removes the old group
            else:
                skipped = [f"{light.name} ({group})" for light, group in conflicts]

        if not to_assign:
            self.report({'WARNING'}, "All selected lights are already in a light group: " + short_list(skipped)
                        + " - enable Reassign to move them")
            return {'CANCELLED'}

        # Create the group (or reuse the existing one) in each target view layer
        final_name = name
        created_in = 0
        for view_layer in view_layers:
            existing = view_layer.lightgroups.get(final_name)
            if existing is None:
                item = view_layer.lightgroups.add(name=final_name)
                final_name = item.name   # Blender may have adjusted it
                created_in += 1

        for light in to_assign:
            light.lightgroup = final_name

        removed = []
        if self.reassign and conflicts:
            removed = remove_unused_groups(group for _light, group in conflicts if group != final_name)

        message = f"Light group '{final_name}': {len(to_assign)} light(s) assigned"
        if created_in == 0:
            message += " (group already existed)"
        moved = [f"{light.name} (was {group})" for light, group in conflicts] if self.reassign else []
        if moved:
            message += " - moved: " + short_list(moved)
        if removed:
            message += " - removed empty group(s): " + short_list(removed)
        if skipped:
            self.report({'WARNING'}, message + f" - skipped, already in a group: {short_list(skipped)}")
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}


class BLENDDICE_OT_clear_light_groups(bpy.types.Operator):
    """Remove the light group from every object and delete all light groups (all view layers of this file)"""
    bl_idname = "blenddice.clear_light_groups"
    bl_label = "Clear all Lightgroups"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def _counts():
        assigned = [o for o in bpy.data.objects if getattr(o, "lightgroup", "")]
        worlds = [w for w in (bpy.data.worlds or []) if getattr(w, "lightgroup", "")]
        groups = sum(len(vl.lightgroups) for scene in bpy.data.scenes for vl in scene.view_layers)
        return assigned, worlds, groups

    def invoke(self, context, event):
        assigned, worlds, groups = self._counts()
        if not assigned and not worlds and not groups:
            self.report({'INFO'}, "There are no light groups")
            return {'CANCELLED'}
        return context.window_manager.invoke_confirm(
            self, event,
            message=f"Remove {len(assigned) + len(worlds)} assignment(s) and delete {groups} light group(s)?",
        ) if hasattr(context.window_manager, "invoke_confirm") else context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        assigned, worlds, groups = self._counts()
        for item in assigned + worlds:
            item.lightgroup = ""
        removed = 0
        for scene in bpy.data.scenes:
            for view_layer in scene.view_layers:
                for group in list(view_layer.lightgroups):
                    view_layer.lightgroups.remove(group)
                    removed += 1
        self.report({'INFO'}, f"Cleared {len(assigned) + len(worlds)} assignment(s), deleted {removed} light group(s)")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Camera export
# ---------------------------------------------------------------------------

_BAD_FILE_CHARS = re.compile(r'[\\/:*?"<>|]')


def fill_camera_template(template, scene_name, camera_name):
    safe = lambda text: _BAD_FILE_CHARS.sub("_", text)
    return (template.replace("{SCENE}", safe(scene_name))
                    .replace("{CAMERA}", safe(camera_name)))


def next_version_path(folder, base_name, ext=".abc"):
    """folder/base_name_v001.abc, or the next free version number."""
    pattern = re.compile(rf"^{re.escape(base_name)}_v(\d+){re.escape(ext)}$", re.IGNORECASE)
    highest = 0
    if os.path.isdir(folder):
        for filename in os.listdir(folder):
            match = pattern.match(filename)
            if match:
                highest = max(highest, int(match.group(1)))
    version = highest + 1
    return version, os.path.join(folder, f"{base_name}_v{version:03d}{ext}")


def _layer_collection_ok(layer_collection, targets, parent_ok=True):
    """True if one of the `targets` collections is reachable through layer collections
    that are neither excluded nor disabled in the viewport."""
    ok = (parent_ok and not layer_collection.exclude and not layer_collection.hide_viewport
          and not layer_collection.collection.hide_viewport)
    if ok and layer_collection.collection in targets:
        return True
    return any(_layer_collection_ok(child, targets, ok) for child in layer_collection.children)


def camera_problem(camera, view_layer):
    """Why the camera would not be exported (excluded / hidden / disabled), or None."""
    if camera.name not in view_layer.objects:
        return f"'{camera.name}' is not in the active view layer (its collection is probably excluded)"
    if not _layer_collection_ok(view_layer.layer_collection, list(camera.users_collection)):
        names = ", ".join(c.name for c in camera.users_collection) or "none"
        return f"'{camera.name}' is in an excluded or disabled collection ({names}) - enable it for the export"
    if camera.hide_get(view_layer=view_layer) or camera.hide_viewport:
        return f"'{camera.name}' is hidden - unhide it for the export"
    if not camera.visible_get(view_layer=view_layer):
        return f"'{camera.name}' is not visible in the viewport - make it visible for the export"
    return None


def written_file_is_empty(filepath, camera_name):
    """The exporter happily writes a ~1 KB file without any object when it skipped the
    camera. Real files contain the object name (Alembic replaces ' ', '.' and ':' by '_')."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except OSError:
        return True
    abc_name = re.sub(r"[ .:]", "_", camera_name)
    return abc_name.encode("utf-8") not in data and len(data) < 8192


class BLENDDICE_OT_export_camera(bpy.types.Operator):
    """Export the active scene camera as an Alembic (.abc) file for Nuke (the version number goes up if the file exists)"""
    bl_idname = "blenddice.export_camera"
    bl_label = "Export Camera"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        scene = context.scene
        camera = scene.camera
        view_layer = context.view_layer

        # -- checks
        if camera is None or camera.type != 'CAMERA':
            self.report({'ERROR'}, "The scene has no active camera")
            return {'CANCELLED'}
        if camera.data.type != 'PERSP':
            self.report({'ERROR'}, f"'{camera.name}' is not a perspective camera - only perspective cameras can be exported")
            return {'CANCELLED'}
        if view_layer is None:
            self.report({'ERROR'}, "No view layer found")
            return {'CANCELLED'}
        problem = camera_problem(camera, view_layer)
        if problem:
            self.report({'ERROR'}, problem)
            return {'CANCELLED'}

        settings = config.get_camera_settings()
        directory = clean_directory(fill_camera_template(settings["directory"], scene.name, camera.name))
        if directory.startswith("//") and not bpy.data.filepath:
            self.report({'ERROR'}, "Save the .blend file first - the camera path is relative to it")
            return {'CANCELLED'}
        folder = bpy.path.abspath(directory)
        base_name = fill_camera_template(settings["file_name"], scene.name, camera.name)

        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self.report({'ERROR'}, f"Could not create the folder {folder}: {e}")
            return {'CANCELLED'}
        version, filepath = next_version_path(folder, base_name)

        # -- export with only the camera selected; the selection is restored afterwards
        previous_selection = [o for o in view_layer.objects if o.select_get(view_layer=view_layer)]
        previous_active = view_layer.objects.active
        error = None
        try:
            for obj in previous_selection:
                obj.select_set(False, view_layer=view_layer)
            camera.select_set(True, view_layer=view_layer)
            result = bpy.ops.wm.alembic_export(
                filepath=filepath,
                start=scene.frame_start,
                end=scene.frame_end,
                selected=True,
                flatten=bool(settings["flatten"]),
                global_scale=float(settings["global_scale"]),
            )
            if 'FINISHED' not in result:
                error = "the Alembic exporter did not finish"
        except Exception as e:
            error = str(e)
        finally:
            try:
                camera.select_set(False, view_layer=view_layer)
                for obj in previous_selection:
                    obj.select_set(True, view_layer=view_layer)
                view_layer.objects.active = previous_active
            except Exception:
                pass

        if error is None and not os.path.isfile(filepath):
            error = "no file was written"
        if error is None and written_file_is_empty(filepath, camera.name):
            try:
                os.remove(filepath)
            except OSError:
                pass
            self.report({'ERROR'}, f"Camera export failed: '{camera.name}' was not written (hidden, excluded or disabled?) "
                                   "- the empty file was deleted")
            return {'CANCELLED'}
        if error:
            self.report({'ERROR'}, f"Camera export failed: {error}")
            return {'CANCELLED'}

        # -- heads-up about things that make the result differ in Nuke
        notes = []
        if any(marker.camera is not None for marker in scene.timeline_markers):
            notes.append("camera markers found - only the active camera is exported")
        if camera.data.sensor_fit != 'AUTO':
            notes.append(f"sensor fit is {camera.data.sensor_fit.title()} - check the film back in Nuke")
        if scene.unit_settings.scale_length != 1.0:
            notes.append("Unit Scale is not 1 - the export ignores it, only global_scale counts")

        fps = scene.render.fps / (scene.render.fps_base or 1.0)
        message = (f"Exported '{camera.name}' as {os.path.basename(filepath)} (v{version:03d}, frames "
                   f"{scene.frame_start}-{scene.frame_end}, {fps:g} fps, scale x{settings['global_scale']:g}) to {folder}")
        if notes:
            self.report({'WARNING'}, message + " - " + "; ".join(notes))
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}


classes = (
    BLENDDICE_OT_create_light_group,
    BLENDDICE_OT_clear_light_groups,
    BLENDDICE_OT_export_camera,
)
