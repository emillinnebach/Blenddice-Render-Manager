import bpy

from . import config, sync

_STATUS_ICONS = {
    "ok": 'CHECKMARK',
    "running": 'TIME',
    "error": 'ERROR',
    "warning": 'ERROR',
    "skipped": 'INFO',
    "idle": 'INFO',
}

PRODUCTION_HINT = "If set, local presets are overwritten by the production presets on every startup."


class BLENDDICE_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    production_path: bpy.props.StringProperty(
        name="Production Presets",
        description=PRODUCTION_HINT,
        subtype='DIR_PATH',
        default="",
    )

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.prop(self, "production_path")
        col.label(text=PRODUCTION_HINT)

        row = layout.row(align=True)
        row.operator("blenddice.sync_presets", icon='FILE_REFRESH')
        row.operator("blenddice.reload_configs", icon='FILE_REFRESH')

        # One compact status line: time | sync result | preset count
        status = sync.status
        parts = [status["message"], f"{len(config.get_presets())} presets"]
        if status["time"]:
            parts.insert(0, status["time"])
        layout.label(text="  |  ".join(parts), icon=_STATUS_ICONS.get(status["level"], 'INFO'))

        # Problems (errors first, then notes) - only shown when there are any
        errors, warnings = config.get_errors(), config.get_warnings()
        if errors or warnings:
            box = layout.box()
            box.alert = bool(errors)
            problems = [(m, 'ERROR') for m in errors] + [(m, 'INFO') for m in warnings]
            for message, icon in problems[:6]:
                box.label(text=message, icon=icon)
            if len(problems) > 6:
                box.label(text=f"... and {len(problems) - 6} more")

        layout.operator("blenddice.open_config_folder", text="Settings: Open Config Folder", icon='FILE_FOLDER')


classes = (
    BLENDDICE_AP_preferences,
)
