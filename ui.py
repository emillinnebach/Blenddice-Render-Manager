import bpy

from . import config
from .operators import target_description
from .tools import selected_lights

CATEGORY = "Render Layer Manager"


def draw_config_warning(layout):
    errors = config.get_errors()
    if errors:
        box = layout.box()
        box.alert = True
        box.label(text=f"{len(errors)} config problem(s)", icon='ERROR')
        box.label(text="See Add-on Preferences")


def draw_presets_box(layout, context):
    """The 'Apply Presets:' box with the target note and one button per preset file."""
    box = layout.box()
    box.label(text="Apply Presets:")

    col = box.column(align=True)
    for line in target_description(context):
        col.label(text=line, icon='RENDERLAYERS' if line.startswith("Target") else 'INFO')

    names = config.get_preset_names()
    if not names:
        box.label(text="No presets found", icon='INFO')
        box.operator("blenddice.open_config_folder", icon='FILE_FOLDER')
        return

    col = box.column(align=True)
    col.scale_y = 1.3
    for name in names:
        op = col.operator("blenddice.apply_pass_preset", text=f"Apply {name} passes")
        op.preset_name = name


def draw_camera_box(layout, context):
    box = layout.box()
    camera = context.scene.camera if context.scene else None
    box.label(text=f"Camera: {camera.name}" if camera else "No active camera", icon='CAMERA_DATA')
    row = box.row()
    row.scale_y = 1.3
    row.operator("blenddice.export_camera", icon='EXPORT')


def draw_light_group_box(layout, context):
    box = layout.box()
    box.label(text="Light Groups:")
    count = len(selected_lights(context))
    box.label(text=f"{count} light(s) selected" if count else "Select light(s) first", icon='LIGHT')
    row = box.row()
    row.scale_y = 1.3
    row.operator("blenddice.create_light_group", icon='OUTLINER_OB_LIGHT')
    box.operator("blenddice.clear_light_groups", icon='TRASH')


# ---------------------------------------------------------------------------
# 3D Viewport sidebar
# ---------------------------------------------------------------------------

class VIEW3D_PT_blenddice_main(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_blenddice_main"
    bl_label = "Render Layer Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.4
        col.operator("blenddice.apply_basic_settings", icon='OUTPUT')

        draw_presets_box(layout, context)
        draw_light_group_box(layout, context)
        draw_camera_box(layout, context)
        draw_config_warning(layout)


class VIEW3D_PT_blenddice_advanced(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_blenddice_advanced"
    bl_label = "Advanced"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "VIEW3D_PT_blenddice_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Writes config files - asks first.", icon='INFO')
        col = layout.column(align=True)
        col.operator("blenddice.save_basic_settings", icon='EXPORT')
        col.operator("blenddice.save_passes_preset", icon='EXPORT')


# ---------------------------------------------------------------------------
# Compositor sidebar
# ---------------------------------------------------------------------------

class NODE_PT_blenddice_main(bpy.types.Panel):
    bl_idname = "NODE_PT_blenddice_main"
    bl_label = "Render Layer Manager"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = CATEGORY

    @classmethod
    def poll(cls, context):
        return getattr(context.space_data, "tree_type", None) == 'CompositorNodeTree'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.4
        col.operator("blenddice.build_output_node", icon='NODE_COMPOSITING')

        draw_presets_box(layout, context)
        draw_camera_box(layout, context)
        draw_config_warning(layout)


classes = (
    VIEW3D_PT_blenddice_main,
    VIEW3D_PT_blenddice_advanced,
    NODE_PT_blenddice_main,
)
