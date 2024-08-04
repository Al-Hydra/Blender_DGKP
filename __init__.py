bl_info = {
    "name" : "DGKP Importer/Exporter",
    "author" : "HydraBladeZ",
    "description" : "Import Kill la Kill model, texture and animation files into blender",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "View3D",
    "warning" : "",
    "category" : "Import"
}

import bpy

from .dgkp_importer import *
from .dgkp_exporter import *


def register():
    
    bpy.utils.register_class(DGKP_IMPORTER_OT_IMPORT)
    bpy.utils.register_class(DGKP_IMPORTER_OT_DROP)
    bpy.utils.register_class(DGKP_FH_IMPORT)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
    bpy.utils.register_class(DGKP_IMPORTER_OT_EXPORT)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(DGKP_IMPORTER_OT_IMPORT)
    bpy.utils.unregister_class(DGKP_IMPORTER_OT_DROP)
    bpy.utils.unregister_class(DGKP_FH_IMPORT)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    bpy.utils.unregister_class(DGKP_IMPORTER_OT_EXPORT)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
