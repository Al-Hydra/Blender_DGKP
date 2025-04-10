import bpy, bmesh
import os, time
from time import perf_counter
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator, MeshLoopTriangle
from mathutils import Vector, Quaternion, Matrix, Euler
from bpy_extras.io_utils import ExportHelper
from math import radians, tan
from .lib.dgkp import *

class DGKP_IMPORTER_OT_EXPORT(Operator, ExportHelper):
    bl_idname = 'export_scene.dgkp'
    bl_label = 'Export DGKP'
    filename_ext = '.pac'

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    
    export_original_bone_data: bpy.props.BoolProperty(
        name="Use Original Bone Data",
        default=False,
        description="Export bone data using stored matrix/rotation/scale from custom bone properties")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_original_bone_data")
    
    def execute(self, context):
        start_time = time.time()

        dgkp = read_dgkp(self.filepath)
        blender_model = context.object

        dgkp_model = next((m for m in dgkp.models if m.name == blender_model.name), None)
        if not dgkp_model:
            self.report({'ERROR'}, "Matching DGKP model not found.")
            return {"CANCELLED"}

        # Coordinate system matrix
        up_matrix = Matrix.Rotation(radians(90), 4, 'X')
        up_inv = up_matrix.inverted()
        up_inv_3x3 = up_inv.to_3x3()

        # Bone processing
        blender_bones = sorted([b.name for b in blender_model.data.bones])
        bone_name_to_index = {name: i for i, name in enumerate(blender_bones)}
        dgkp_model.bones = []

        for bone_name in blender_bones:
            bone = blender_model.data.bones[bone_name]
            bone_matrix = up_inv @ bone.matrix_local
            loc, rot, scale = bone_matrix.decompose()
            if self.export_original_bone_data and "orig_matrix" in bone:
                loc, rot, scale = Matrix(bone["orig_matrix"]).decompose()
            else:
                bone_matrix = up_inv @ bone.matrix_local
                loc, rot, scale = bone_matrix.decompose()

            b = MDLD_Bone()
            b.name = bone.name
            b.position = list(loc)
            b.rotation = [rot.x, rot.y, rot.z, rot.w]
            b.scale = list(scale)
            b.parent = bone_name_to_index.get(bone.parent.name, -1) if bone.parent else -1
            dgkp_model.bones.append(b)

        # Mesh
        mesh_obj = blender_model.children[0]
        blender_mesh = mesh_obj.data
        blender_mesh.calc_loop_triangles()
        blender_mesh.calc_tangents()

        material_names = [slot.name for slot in mesh_obj.material_slots]

        if not blender_mesh.color_attributes:
            blender_mesh.vertex_colors.new(name='Color', type="BYTE_COLOR", domain="CORNER")
        color_layer = blender_mesh.color_attributes[0].data
        uv_layer = blender_mesh.uv_layers[0].data if blender_mesh.uv_layers else None
        vertex_groups = mesh_obj.vertex_groups

        mat_meshes = {mat: [] for mat in material_names}
        mdl_vertices = []
        unique_vertex_map = {}
        next_index = 0

        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bm.verts.ensure_lookup_table()

        def make_vertex_key(pos, norm, tang, uv, col, bone_ids, weights, loop_index):
            return (
                tuple(pos),
                tuple(norm),
                tuple(tang),
                tuple(uv) if uv else None,
                tuple(col) if col else None,
                tuple(bone_ids),
                tuple(weights),
                loop_index
            )

        for tri in blender_mesh.loop_triangles:
            triverts = []
            mat_name = material_names[tri.material_index]

            for loop_index in tri.loops:
                loop = blender_mesh.loops[loop_index]
                v_idx = loop.vertex_index
                v = blender_mesh.vertices[v_idx]
                bm_vert = bm.verts[v_idx]

                pos = up_inv @ v.co
                norm = (up_inv_3x3 @ loop.normal).normalized()
                tang = (up_inv_3x3 @ bm_vert.normal).normalized()
                uv = uv_layer[loop_index].uv 
                uv_final = [uv[0], 1 - uv[1]] 
                col = [int(c * 255) for c in color_layer[loop_index].color_srgb]

                groups = sorted(v.groups, key=lambda g: 1 - g.weight)
                b_weights = [(vertex_groups[g.group].name, g.weight)
                             for g in groups if vertex_groups[g.group].name in bone_name_to_index]
                b_weights = (b_weights + [(None, 0.0)] * 4)[:4]

                total = sum(w for _, w in b_weights)
                bone_ids = [bone_name_to_index.get(bw[0], 0) for bw in b_weights]
                weights = [(bw[1] / total if total > 0 else [0, 0, 0, 1][i]) for i, bw in enumerate(b_weights)]

                key = make_vertex_key(pos, norm, tang, uv_final, col, bone_ids, weights, loop_index)

                if key in unique_vertex_map:
                    index = unique_vertex_map[key]
                else:
                    index = next_index
                    unique_vertex_map[key] = index

                    mdl_v = MDLD_Vertex()
                    mdl_v.position = list(pos)
                    mdl_v.normal = list(norm)
                    mdl_v.tangent = list(tang)
                    mdl_v.uv = uv_final
                    mdl_v.color = col
                    mdl_v.boneIDs = bone_ids
                    mdl_v.weights = weights

                    mdl_vertices.append(mdl_v)
                    next_index += 1

                triverts.append(index)

            mat_meshes[mat_name].append(triverts)

        dgkp_model.vertices = mdl_vertices

        for mesh in dgkp_model.materialMeshes:
            mesh.triangles = mat_meshes.get(mesh.name, [])

        bm.free()

        write_dgkp(f"{self.filepath}", dgkp)

        elapsed = time.time() - start_time
        msg = f"Exported {len(mdl_vertices)} unique vertices in {elapsed:.2f}s"
        print(msg)
        self.report({'INFO'}, msg)

        return {'FINISHED'}
        


def menu_func_export(self, context):
    self.layout.operator(DGKP_IMPORTER_OT_EXPORT.bl_idname,
                        text='DGKP Archive Exporter')