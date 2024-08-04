import bpy, bmesh
import os
from time import time, perf_counter
from bpy.props import CollectionProperty, StringProperty
from mathutils import Vector, Quaternion, Matrix, Euler
from bpy_extras.io_utils import ImportHelper
from math import radians, tan
from .lib.dgkp import *


class DGKP_IMPORTER_OT_IMPORT(bpy.types.Operator, ImportHelper):
    bl_label = "Import DGKP"
    bl_idname = "import_scene.dgkp"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore
    materialspath: StringProperty(name= "Materials Path",subtype='FILE_PATH') # type: ignore


    def execute(self, context):

        start_time = perf_counter()

        for file in self.files:
            
            self.filepath = os.path.join(self.directory, file.name)
            import_dgkp(self.filepath, self.materialspath)
        
        elapsed_s = "{:.2f}s".format(perf_counter() - start_time)
        self.report({'INFO'}, "DGKP archives imported in " + elapsed_s)

        return {'FINISHED'}
    

class DGKP_IMPORTER_OT_DROP(bpy.types.Operator):
    bl_label = "Import DGKP"
    bl_idname = "import_scene.drop_dgkp"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore
    materialspath: StringProperty(subtype='FILE_PATH') # type: ignore


    def execute(self, context):

        start_time = perf_counter()

        for file in self.files:
            
            self.filepath = os.path.join(self.directory, file.name)
            import_dgkp(self.filepath, self.materialspath)
        
        elapsed_s = "{:.2f}s".format(perf_counter() - start_time)
        self.report({'INFO'}, "DGKP archives imported in " + elapsed_s)

        return {'FINISHED'}


class DGKP_FH_IMPORT(bpy.types.FileHandler):
    bl_idname = "DGKP_FH_import"
    bl_label = "File handler for DGKP archives"
    bl_import_operator = "import_scene.drop_dgkp"
    bl_file_extensions = ".pac"

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass

def import_dgkp(filePath, materialspath):
        
    dgkp:DGKP = read_dgkp(filePath)
    materialsDGKP: DGKP = read_dgkp(materialspath)


    def add_material(mat):

        # Create a new material
        material = bpy.data.materials.get(mat.name)
        if not material:
            material = bpy.data.materials.new(mat.name)
            material.use_nodes = True
            nodes = material.node_tree.nodes
            nodes.clear()

            # Create Image Texture Node
            image_texture_node = nodes.new(type='ShaderNodeTexImage')
            image_texture_node.image = bpy.data.images.get(mat.textures[0])
            image_texture_node.location = (-400, 0)

            # Create Color Mix Node (set to Multiply)
            color_mix_node = nodes.new(type='ShaderNodeMixRGB')
            color_mix_node.blend_type = 'MULTIPLY'
            color_mix_node.inputs['Fac'].default_value = 1.0
            color_mix_node.location = (-200, 0)

            # Create Material Output Node
            output_node = nodes.new(type='ShaderNodeOutputMaterial')
            output_node.location = (200, 0)

            # Connect Image Texture Node output to Color Mix Node inputs
            material.node_tree.links.new(image_texture_node.outputs['Color'], color_mix_node.inputs['Color1'])
            material.node_tree.links.new(image_texture_node.outputs['Alpha'], color_mix_node.inputs['Color2'])

            # Connect Color Mix Node output to Material Output Node
            material.node_tree.links.new(color_mix_node.outputs['Color'], output_node.inputs['Surface'])
        
        return material
        


    def add_bones(bone, armature):
        bbone = armature.edit_bones.new(bone.name)
        bbone.use_deform = True
        bbone.tail = Vector((0, 0.1, 0))
        
        rotation = Quaternion((bone.rotation[3], bone.rotation[0], bone.rotation[1], bone.rotation[2]))
        matrix = Matrix.LocRotScale(bone.position, rotation, bone.scale)
        
        bbone["loc"] = bone.position
        bbone["rotation"] = rotation
        bbone["scale"] = bone.scale
        bbone["matrix"] = matrix
        
        
        
        bbone.matrix = matrix
        
        return bbone


    if dgkp.textures:
        for texture in dgkp.textures:
            texture: TEXD
            
            if not bpy.data.images.get(texture.name):
                img = bpy.data.images.new(texture.name, texture.width, texture.height, alpha=True)
                img.pack(data=bytes(texture.textureData), data_len=len(texture.textureData))
                img.source = 'FILE'


    if dgkp.models:
        
        for mdl in dgkp.models:

            armature = bpy.data.armatures.new(mdl.name)
            armature.display_type = 'STICK'
            armature_obj = bpy.data.objects.new(mdl.name, armature)
            armature_obj.show_in_front = True

            bpy.context.collection.objects.link(armature_obj)

            bpy.context.view_layer.objects.active = armature_obj
            bpy.ops.object.editmode_toggle()
            
            bones = [add_bones(bone, armature) for bone in mdl.bones]
            
            

            for i, bone in enumerate(mdl.bones):
                bone: MDLD_Bone
                
                bbone = bones[i]
                if bone.parent > -1:
                    parent_bone = mdl.bones[bone.parent]
                    parent_bbone = bones[bone.parent]
                    
                else:
                    parent_bbone = None
                
                bbone.parent = parent_bbone

            bpy.ops.object.editmode_toggle()


            meshdata = bpy.data.meshes.new(mdl.skeletonName)
            mesh_obj = bpy.data.objects.new(mdl.skeletonName, meshdata)

            mesh_obj.parent = armature_obj

            armature_modifier = mesh_obj.modifiers.new(name = mdl.skeletonName, type = 'ARMATURE')
            armature_modifier.object = armature_obj

            for bone in mdl.bones:
                mesh_obj.vertex_groups.new(name = bone.name)

            custom_normals = []

            bm = bmesh.new()
            uv_layer = bm.loops.layers.uv.new(f"UV")
            color_layer = bm.loops.layers.color.new(f"Color")
            vgroup_layer = bm.verts.layers.deform.new("Weights")

            for vertex in mdl.vertices:
                vert = bm.verts.new(vertex.position)
                custom_normals.append(vertex.normal)
                vert[vgroup_layer][vertex.boneIDs[0]] = 0
                vert[vgroup_layer][vertex.boneIDs[1]] = 0
                vert[vgroup_layer][vertex.boneIDs[2]] = 0
                vert[vgroup_layer][vertex.boneIDs[3]] = 0
                
                for boneID, weight in zip(vertex.boneIDs, vertex.weights):
                    vert[vgroup_layer][boneID] += weight

            bm.verts.ensure_lookup_table()

            for i, mat in enumerate(mdl.materialMeshes):
                mat: MDLD_MaterialMesh
                material = materialsDGKP.materials.get(mat.name)

                meshdata.materials.append(add_material(material))

                for tris in mat.triangles:
                    face = bm.faces.new((bm.verts[tris[0]], bm.verts[tris[1]], bm.verts[tris[2]]))
                    face.smooth = True
                    face.material_index = i
                    
                    face.loops[0][uv_layer].uv = (mdl.vertices[tris[0]].uv[0], 1 - mdl.vertices[tris[0]].uv[1])
                    face.loops[1][uv_layer].uv = (mdl.vertices[tris[1]].uv[0], 1 - mdl.vertices[tris[1]].uv[1])
                    face.loops[2][uv_layer].uv = (mdl.vertices[tris[2]].uv[0], 1 - mdl.vertices[tris[2]].uv[1])
                    
                    face.loops[0][color_layer] = [x / 255 for x in mdl.vertices[tris[0]].color]
                    face.loops[1][color_layer] = [x / 255 for x in mdl.vertices[tris[1]].color]
                    face.loops[2][color_layer] = [x / 255 for x in mdl.vertices[tris[2]].color]

            bm.to_mesh(meshdata)

            meshdata.normals_split_custom_set_from_vertices(custom_normals)

            #set active color
            mesh_obj.data.color_attributes.render_color_index = 0
            mesh_obj.data.color_attributes.active_color_index = 0

            bpy.context.collection.objects.link(mesh_obj)


    def insertFrames(action, group_name, data_path, values, values_count):
            if len(values):
                for i in range(values_count):
                    fc = action.fcurves.new(data_path=data_path, index=i, action_group=group_name)
                    fc.keyframe_points.add(len(values.keys()))
                    fc.keyframe_points.foreach_set('co', [x for co in list(map(lambda f, v: (f, v[i]), values.keys(), values.values())) for x in co])

                    fc.update()


    for anim in dgkp.animations:
        anim: ANUM
        
        if anim.skeletalAnimation:
            sklAnim = anim.skeletalAnimation

            action = bpy.data.actions.new(sklAnim.name)

            #set fps to 30
            bpy.context.scene.render.fps = 60

            #adjust the timeline
            bpy.context.scene.frame_start = 0
            bpy.context.scene.frame_end = sklAnim.frameCount

            target_armature = bpy.context.object
            target_armature.animation_data_create()
            target_armature.animation_data.action = action

            bones = sorted([b.name for b in target_armature.pose.bones])

            for curve in sklAnim.curves:
                curve: TOMF_Curve
                group_name = action.groups.new(name = bones[curve.index]).name
                bone_path = f'pose.bones["{group_name}"]'
                
                bbone = target_armature.data.bones.get(bones[curve.index])
                if bbone.parent:
                    matrix = Matrix(bbone.parent["matrix"]).inverted() @ Matrix(bbone["matrix"])
                else:
                    matrix = Matrix(bbone["matrix"])
                    
                loc, rot, scale = matrix.decompose()

                brot = matrix.to_quaternion()
                
                
                data_path = f'{bone_path}.{"location"}'
                curve.locationFrames = {f: Vector(location) - (loc) for f, location in curve.locationFrames.items()}
                insertFrames(action, group_name, data_path, curve.locationFrames, 3)

                data_path = f'{bone_path}.{"rotation_quaternion"}'
                curve.rotationFrames = {f: (rotation[3], *rotation[:3]) for f, rotation in curve.rotationFrames.items()}

                insertFrames(action, group_name, data_path, curve.rotationFrames, 4)

                data_path = f'{bone_path}.{"scale"}'
                insertFrames(action, group_name, data_path, curve.scaleFrames, 3)

        if anim.cameraAnimation:
            camAnim = anim.cameraAnimation

            #set fps to 30
            bpy.context.scene.render.fps = 60

            #adjust the timeline
            bpy.context.scene.frame_start = 0
            bpy.context.scene.frame_end = camAnim.frameCount
            
            camera_obj = bpy.context.scene.camera
            if not camera_obj:
                camera = bpy.data.cameras.new("Camera")
                camera_obj = bpy.data.objects.new("Camera", camera)
                bpy.context.collection.objects.link(bpy.data.objects.get(camera_obj.name))

                bpy.context.scene.camera = camera_obj
            
            
            #create a separate action for each camera
            camera_action = bpy.data.actions.new(f"{camAnim.name} ({camera_obj.name})")

            group_name = camera_action.groups.new(name = camera_obj.name).name
            
            #apply the animation to the camera
            camera_obj.animation_data_create()
            camera_obj.animation_data.action = camera_action
            camera_obj.scale = (10,10,10)
            camera_obj.data.lens = camera_obj.data.sensor_width / (2 * tan(radians(camAnim.FoV) / 2))

            locations = {}
            rotations = {}
            fovs = {}
            for frame, values in camAnim.frames.items():
                loc, rot, scale, fov = values
                rot = list(rot)
                rot[0] -= 180
                locations[frame] = Vector(loc)
                rotation = [radians(r) for r in rot]
                
                rotations[frame] = rotation
                #fovs[frame] = [camera_obj.data.sensor_width / (2 * tan(radians(fov) / 2))]

            data_path = f'{"location"}'
            insertFrames(camera_action, group_name, data_path, locations, 3)
            
            data_path = f'{"rotation_euler"}'
            insertFrames(camera_action, group_name, data_path, rotations, 3)
            
            #data_path = f'{"data.lens"}'
            #insertFrames(camera_action, group_name, data_path, fovs, 1)

        


def menu_func_import(self, context):
    self.layout.operator(DGKP_IMPORTER_OT_IMPORT.bl_idname,
                        text='DGKP Archive Importer')