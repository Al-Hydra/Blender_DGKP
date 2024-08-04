import bpy, bmesh
import os
from time import perf_counter
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator, MeshLoopTriangle
from mathutils import Vector, Quaternion, Matrix, Euler
from bpy_extras.io_utils import ExportHelper
from math import radians, tan
from .lib.dgkp import *


def calculate_tangent(p0, p1, p2, uv0, uv1, uv2):
    delta_pos1 = p1 - p0
    delta_pos2 = p2 - p0
    
    delta_uv1 = uv1 - uv0
    delta_uv2 = uv2 - uv0
    
    f = 1.0 / (delta_uv1.x * delta_uv2.y - delta_uv2.x * delta_uv1.y)
    
    tangent = f * (delta_uv2.y * delta_pos1 - delta_uv1.y * delta_pos2)
    return tangent


class DGKP_IMPORTER_OT_EXPORT(Operator, ExportHelper):
    bl_idname = 'export_scene.dgkp'
    bl_label = 'Export DGKP'
    filename_ext = '.pac'

    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    def execute(self, context):


        dgkp = read_dgkp(self.filepath)

        #find the model chunk
        blender_model = context.object

        dgkp_model: MDLD = None

        for model in dgkp.models:
            if blender_model.name == model.name:
                dgkp_model = model
                break
        
        if not dgkp_model:
             return {"CANCELLED"}
        
        blender_bones: list = sorted([b.name for b in blender_model.data.bones])
        dgkp_bones = []
        
        for bone_name in blender_bones:
            bone = blender_model.data.bones[bone_name]
            
            bone_matrix = bone.matrix_local

            loc, rot, scale = bone_matrix.decompose()


            mdld_bone = MDLD_Bone()

            mdld_bone.name = bone.name
            mdld_bone.position = list(loc)
            mdld_bone.rotation = [rot.x, rot.y, rot.z, rot.w]
            mdld_bone.scale = list(scale)
            mdld_bone.parent = blender_bones.index(bone.parent.name) if bone.parent else -1

            dgkp_bones.append(mdld_bone)
        dgkp_model.bones = dgkp_bones

        mesh_obj = blender_model.children[0]
        blender_mesh = mesh_obj.data
        #triangulate the mesh
        blender_mesh.calc_loop_triangles()

        #calculate tangents
        blender_mesh.calc_tangents()

        mesh_vertices = blender_mesh.vertices
        mesh_loops = blender_mesh.loops
        
        vertex_groups = mesh_obj.vertex_groups

        if len(blender_mesh.color_attributes) > 0:
            color_layer = blender_mesh.color_attributes[0].data
        else:
            color_layer = blender_mesh.vertex_colors.new(name='Color', type = "BYTE_COLOR", domain = "CORNER")
            color_layer = blender_mesh.color_attributes[0].data

        uv_layer = blender_mesh.uv_layers[0].data

        mat_meshes = {mat.name: [] for mat in mesh_obj.material_slots}
        mdl_vertices = []

        mdl_vertex_index = 0

        #bmesh will be used to get the real normals instead of the custom normals which are needed for some kill la kill shaders
        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bm.verts.ensure_lookup_table()


        for triangle in blender_mesh.loop_triangles:
            triangle: MeshLoopTriangle
            
            triangle_material = mesh_obj.material_slots[triangle.material_index]

            triverts = []

            for loop_index in triangle.loops:
                loop = mesh_loops[loop_index]
                blender_vertex = mesh_vertices[loop.vertex_index]
                bm_vertex = bm.verts[loop.vertex_index]
                triverts.append(mdl_vertex_index)
                mdl_vertex_index += 1

                mdl_vertex = MDLD_Vertex()

                
                mdl_vertex.position = list(blender_vertex.co)
                mdl_vertex.normal = list(loop.normal)
                tangent = (Vector(loop.tangent))
                mdl_vertex.tangent = list(bm_vertex.normal)

                # Color
                if color_layer:
                    mdl_vertex.color = [int(c*255) for c in color_layer[loop_index].color_srgb]
                
                if uv_layer:
                    mdl_vertex.uv = [uv_layer[loop_index].uv[0], 1 - uv_layer[loop_index].uv[1]]
                
                # Bone indices and weights
                # Direct copy of TheTurboTurnip's weight sorting method
                # https://github.com/theturboturnip/yk_gmd_io/blob/master/yk_gmd_blender/blender/export/legacy/exporter.py#L302-L316

                # Get a list of (vertex group ID, weight) items sorted in descending order of weight
                # Take the top 4 elements, for the top 4 most deforming bones
                # Normalize the weights so they sum to 1
                b_weights = [(vertex_groups[g.group].name, g.weight) for g in sorted(
                    blender_vertex.groups, key=lambda g: 1 - g.weight) if vertex_groups[g.group].name in blender_bones]
                if len(b_weights) > 4:
                    b_weights = b_weights[:4]
                elif len(b_weights) < 4:
                    # Add zeroed elements to b_weights so it's 4 elements long
                    b_weights += [(0, 0.0)] * (4 - len(b_weights))

                weight_sum = sum(weight for (_, weight) in b_weights)
                if weight_sum > 0.0:
                    for i, bw in enumerate(b_weights):
                        if bw[0] in blender_bones:
                            mdl_vertex.boneIDs[i] = blender_bones.index(bw[0])
                        else:
                            mdl_vertex.boneIDs[i] = 0
                        
                        mdl_vertex.weights[i] = bw[1] / weight_sum

                else:
                    mdl_vertex.boneIDs = [0] * 4
                    mdl_vertex.weights = [0] * 3 + [1]
                
                mdl_vertices.append(mdl_vertex)

            mat_meshes[triangle_material.name].append(triverts)

        dgkp_model.vertices = mdl_vertices

        for mesh in dgkp_model.materialMeshes:
            mesh: MDLD_MaterialMesh
            mesh.triangles = mat_meshes.get(mesh.name, [])
            
        bm.free()

        write_dgkp(f"{self.filepath}", dgkp)

        
        return {'FINISHED'}
        


def menu_func_export(self, context):
    self.layout.operator(DGKP_IMPORTER_OT_EXPORT.bl_idname,
                        text='DGKP Archive Exporter')