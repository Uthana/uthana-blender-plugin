"""UIList classes for asset browsing in Uthana plugin."""

import bpy


class UTHANA_UL_motions(bpy.types.UIList):
    """Motion list UI for browsing motions."""

    bl_idname = "UTHANA_UL_motions"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            # Show favorite icon if favorited
            if item.is_favorite:
                row.label(text="", icon="SOLO_ON")
            row.label(text=item.name, icon="ACTION")
            # Show created date in compact form
            if item.created:
                sub = row.row()
                sub.scale_x = 0.6
                sub.label(text=item.created[:10])
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.name, icon="ACTION")


class UTHANA_UL_characters(bpy.types.UIList):
    """Character list UI for browsing characters."""

    bl_idname = "UTHANA_UL_characters"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.label(text=item.name, icon="ARMATURE_DATA")
            # Show created date in compact form
            if item.created:
                row.label(text=item.created[:10])
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.name, icon="ARMATURE_DATA")


# Classes to register
classes = (
    UTHANA_UL_motions,
    UTHANA_UL_characters,
)
