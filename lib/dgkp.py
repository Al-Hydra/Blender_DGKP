from .PyBinaryReader.binary_reader import *


class DGKP(BrStruct):
    def __init__(self) -> None:
        super().__init__()
    def __br_read__(self, br: BinaryReader, *args):
        
        self.magic = br.read_str(4)
        br.seek(8,1)
        self.fileCount = br.read_uint32()
        headerSize = br.read_uint32()
        br.seek(28,1)

        self.textures = []
        self.models = []
        self.animations = []
        self.materials = {}
        self.allFiles = {}

        for i in range(self.fileCount):
            fileType = br.read_str(4)
            fileHeaderSize = br.read_uint32()
            dataSize = br.read_uint32()
            fileOffset = br.read_uint32()
            fileName = br.read_str(128)

            currentPos = br.pos()
            br.seek(fileOffset)
            fileData = br.read_bytes(dataSize)
            br.seek(currentPos)

            if fileType == "TEXD":
                texBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = texBuffer.read_struct(TEXD, None, dataSize)
                self.textures.append(file)
            elif fileType == "MDLD":
                modelBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = modelBuffer.read_struct(MDLD)
                file.name = fileName
                self.models.append(file)
            elif fileType == "ANUM":
                anmBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = anmBuffer.read_struct(ANUM)
                self.animations.append(file)
            elif fileType == "MATD":
                matBuffer = BinaryReader(fileData, Endian.LITTLE, "cp932")
                file = matBuffer.read_struct(MATF)
                self.materials[file.name] =  file

            else:
                file = DGKPFile(fileName, fileType, fileData)
            
            file.data = fileData
            self.allFiles[fileName] = file
    
    
    def __br_write__(self, br: BinaryReader):
        #header
        br.write_str("DGKP") #magic
        br.write_uint64(131072) #version maybe?
        br.write_uint32(len(self.allFiles))
        br.write_uint32(48)
        br.write_int8([0]*28) #padding


        file_buf_ofs = {}

        #files
        for name, file in self.allFiles.items():
            if file.type == "MDLD":
                br.write_str(file.type)
                br.write_uint32(144) #header size

                file_buf = BinaryReader()
                file_buf.write_struct(file)
                br.write_uint32(file_buf.size()) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file_buf.buffer())
            
            elif file.type == "TEXD":
                br.write_str(file.type)
                br.write_uint32(144) #header size
                
                file_buf = BinaryReader()
                file_buf.write_struct(file)
                br.write_uint32(file_buf.size()) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file.data)


            else:
                br.write_str(file.type)
                br.write_uint32(144) #header size
                br.write_uint32(len(file.data)) #file size

                fileOfsPos = br.pos()
                br.write_uint32(0) #offset
                br.write_str_fixed(name, 128)

                file_bytes = bytes(file.data)
            
            file_buf_ofs[fileOfsPos] = file_bytes
        
        for ofs, fileBuffer in file_buf_ofs.items():
            currentPos = br.pos()

            br.seek(ofs)
            br.write_uint32(currentPos)

            br.seek(currentPos)
            br.write_bytes(fileBuffer)
            br.align(16)
        


class DGKPFile:
    def __init__(self, name, type) -> None:
        self.type = type
        self.name = name
        self.data = b""
        

class TEXD(BrStruct):
    def __init__(self):
        self.name = ""
        self.type = "TEXD"
        self.data = b""
    def __br_read__(self, br: BinaryReader, fileSize):
        self.magic = br.read_uint16()
        self.width = br.read_uint16()
        self.height = br.read_uint16()
        self.unk = br.read_uint16()
        headerSize = br.read_uint32()
        self.name = br.read_str(64)
        br.seek(4,1)
        
        self.textureData = br.read_bytes(fileSize - headerSize)
    
    def __br_write__(self, br: BinaryReader, *args) -> None:
        br.write_uint16(0)
        br.write_uint16(self.width)
        br.write_uint16(self.height)
        br.write_uint16(self.unk)
        br.write_uint32(80)
        br.write_str_fixed(self.name, 64)
        br.align(16)
        br.write_bytes(self.textureData)

class MDLD(BrStruct):
    def __init__(self):
        self.name = ""
        self.type = "MDLD"
        self.data = b""
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.version = br.read_uint32()
        
        materialsOffset = br.read_uint32()
        self.materialsCount = br.read_uint32()
        bonesOffset = br.read_uint32()
        self.bonesCount = br.read_uint32()
        vertexBufferOffset = br.read_uint32()
        vertexBufferSize = br.read_uint32()
        self.vertexCount = br.read_uint32()
        self.vertexFlags = br.read_uint16()
        self.vertexUnk = br.read_uint16()
        self.skeletonName = br.read_str(64)
        self.shaderString = br.read_str(128)
        self.boundingBoxData = br.read_bytes(64)

        br.seek(materialsOffset)
        self.materialMeshes = br.read_struct(MDLD_MaterialMesh, self.materialsCount)

        br.seek(bonesOffset)
        self.bones = br.read_struct(MDLD_Bone, self.bonesCount)

        br.seek(vertexBufferOffset)
        self.vertices = br.read_struct(MDLD_Vertex, self.vertexCount)
    
    
    def __br_write__(self, br: BinaryReader):
        #header
        br.write_str("LDMF") #magic
        br.write_uint32(160) #version
        br.write_uint32(296) #mat meshes offset
        br.write_uint32(len(self.materialMeshes)) #mat meshes count

        boneOfPos = br.pos()
        br.write_uint32(0) #bones offset
        br.write_uint32(len(self.bones))# bones count

        vBufOfPos = br.pos()
        br.write_uint32(0) #vertex buffer offset

        vertexSize = 52
        if self.vertexFlags & 32:
            vertexSize = 60

        br.write_uint32(len(self.vertices) * vertexSize) #vertex buffer size
        br.write_uint32(len(self.vertices)) #vertices count
        br.write_uint16(self.vertexFlags)
        br.write_uint16(2)
        br.write_str_fixed(self.skeletonName, 64)
        br.write_str_fixed(self.shaderString, 128)
        br.write_bytes(self.boundingBoxData)

        triangles = []
        
        for mesh in self.materialMeshes:
            mesh: MDLD_MaterialMesh
            br.write_struct(mesh)
        
        for mesh in self.materialMeshes:
            currentPos = br.pos()
            br.seek(mesh.trianglesOffsetPos)
            br.write_uint32(currentPos)

            br.seek(currentPos)

            for triangle in mesh.triangles:
                br.write_uint32(triangle)


        currentPos = br.pos()
        br.seek(boneOfPos)

        br.write_uint32(currentPos)
        br.seek(currentPos)

        for bone in self.bones:
            br.write_struct(bone)
        
        currentPos = br.pos()
        br.seek(vBufOfPos)

        br.write_uint32(currentPos)
        br.seek(currentPos)

        for vertex in self.vertices:
            br.write_struct(vertex)


class MDLD_MaterialMesh(BrStruct):
    def __init__(self):
        self.name = ""
        self.triangleIndicesCount = 0
        self.triangles = []
    
    def __br_read__(self, br: BinaryReader):
        self.name = br.read_str(64)
        trianglesOffset = br.read_uint32()
        trianglesbufferSize = br.read_uint32()
        self.triangleIndicesCount = br.read_uint32()
        self.type = br.read_uint32()
        self.boundingBoxData = br.read_bytes(96)

        pos = br.pos()

        br.seek(trianglesOffset)
        self.triangles = [br.read_uint32(3) for i in range(self.triangleIndicesCount//3)]

        br.seek(pos)
    
    def __br_write__(self, br: BinaryReader):
        br.write_str_fixed(self.name, 64)
        self.trianglesOffsetPos = br.pos()
        br.write_int32(0) #offset will be rewritten later
        br.write_uint32((len(self.triangles) * 3) * 4) #triangles buffer size
        br.write_uint32((len(self.triangles) * 3))  #Indices count
        br.write_uint32(4) # triangle type
        br.write_bytes(self.boundingBoxData)



class MDLD_Bone(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.rotation = [0,0,0,0]
        self.position = [0,0,0]
        self.scale = [0,0,0]
        self.parent = 0
    
    def __br_read__(self, br: BinaryReader):
        self.name = br.read_str(32)
        self.rotation = br.read_float(4)
        self.position = br.read_float(3)
        self.scale = br.read_float(3)
        self.parent = br.read_int32()
    
    def __br_write__(self, br: BinaryReader):
        br.write_str_fixed(self.name, 32)
        br.write_float(self.rotation)
        br.write_float(self.position)
        br.write_float(self.scale)
        br.write_int32(self.parent)
    

class MDLD_Vertex(BrStruct):
    def __init__(self) -> None:
        self.position = [0,0,0]
        self.color = [0,0,0,0]
        self.normal = [0,0,0]
        self.tangent = [0,0,0]
        self.uv = [0,0]
        self.boneIDs = [0,0,0,0]  
        self.weights = [0,0,0,0]  
        
    def __br_read__(self, br: BinaryReader):
        self.position = br.read_float(3)
        self.color = br.read_uint8(4)
        self.normal = br.read_half_float(3)
        br.align_pos(4)
        self.uv = br.read_half_float(2)
        self.tangent = br.read_half_float(3)
        br.align_pos(4)

        self.boneIDs = br.read_uint16(4)
        self.weights = br.read_float(4)
    
    def __br_write__(self, br: BinaryReader):
        br.write_float(self.position)
        br.write_uint8(self.color)
        br.write_half_float(self.normal)
        br.write_int16(0)
        br.write_half_float(self.uv)
        br.write_half_float(self.tangent)
        br.write_int16(0)
        br.write_uint16(self.boneIDs)
        br.write_float(self.weights)

class ANUM(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.type = "ANUM"
        self.data = b""
        self.skeletalAnimation = None
        self.cameraAnimation = None
        self.type = "ANUM"
    def __br_read__(self, br: BinaryReader):
        magic = br.read_str(4)

        if magic == "TOMF":
            self.skeletalAnimation = br.read_struct(TOMF)
        elif magic == "CAMF":
            self.cameraAnimation = br.read_struct(CAMF)


class TOMF(BrStruct):
    def __init__(self) -> None:
        self.frameCount = 0
        self.frameRate = 60
        self.bonesCount = 0
        self.modelsCount = 0
        self.curves = []
    def __br_read__(self, br: BinaryReader):
        self.version = br.read_uint32()
        self.name = br.read_str(32)
        br.seek(4,1)
        self.frameCount = br.read_uint32()
        self.frameRate = br.read_uint32()
        self.bonesCount = br.read_uint32()
        self.modelsCount = br.read_uint32()


        self.curves = [br.read_struct(TOMF_Curve, None, i) for i in range(self.bonesCount)]


class TOMF_Curve(BrStruct):
    def __init__(self) -> None:
        self.locationFrames = {}
        self.rotationFrames = {}
        self.scaleFrames = {}
    def __br_read__(self, br: BinaryReader, index = 0):
        self.index = index

        rotationOffset = br.read_uint32()
        self.rotationCount = br.read_uint32()
        locationOffset = br.read_uint32()
        self.locationCount = br.read_uint32()
        scaleOffset = br.read_uint32()
        self.scaleCount = br.read_uint32()

        pos = br.pos()
        br.seek(rotationOffset)
        self.rotationFrames = {br.read_int32(): br.read_float(4) for i in range(self.rotationCount)}

        br.seek(locationOffset)
        self.locationFrames = {br.read_int32(): br.read_float(3) for i in range(self.locationCount)}

        br.seek(scaleOffset)
        self.scaleFrames = {br.read_int32(): br.read_float(3) for i in range(self.scaleCount)}

        br.seek(pos)


class MATF(BrStruct):
    def __init__(self) -> None:
        self.name = ""
        self.type = "MATD"
        self.data = b""
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.version = br.read_uint32()
        self.name = br.read_str(64)

        if self.version == 100:
            br.seek(208,1)
        else:
            self.materialFormat = br.read_str(64)
            self.vertexShader = br.read_str(64)
            self.pixelShader = br.read_str(64)
            self.params = br.read_float(14)

        self.texturesCount = br.read_uint32()

        self.textures = [br.read_str(64) for i in range(self.texturesCount)]


class CAMF(BrStruct):
    def __br_read__(self, br: BinaryReader):
        self.version = br.read_uint32()
        self.headerSize = br.read_uint32()
        self.unk = br.read_uint32()
        self.name = br.read_str(32)
        self.cameraCount = br.read_int32()
        framesOffset = br.read_uint32()
        self.frameCount = br.read_uint16()
        self.frameRate = br.read_uint16()
        self.FoV = br.read_float()

        self.frames = {}

        pos = br.pos()
        br.seek(framesOffset)

        for i in range(self.frameCount):
            location = br.read_float(3)
            rotation = br.read_float(3)
            scale = br.read_float(3)
            fov = br.read_float()

            frame = br.read_int32()

            self.frames[frame] = (location, rotation, scale, fov)

        br.seek(pos)
        


def read_dgkp(path):
    with open(path, "br") as f:
        filebytes = f.read()

    br = BinaryReader(filebytes, Endian.LITTLE, "cp932")

    dgkp: DGKP = br.read_struct(DGKP)

    return dgkp


def write_dgkp(path,  dgkp: DGKP):
    br = BinaryReader(encoding= "cp932")
    br.write_struct(dgkp)
    with open(path, "wb") as f:
        f.write(br.buffer())

