# Core imports
from panda3d.core import Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTristrips
import math

# helper function to make a vertical cylinder given center, radius, and height
def makePlane(cx, cy, cz, width, height, facing="left", color=[0.25, 0.25, 0.25], 
              texHScaling=1.0, texVScaling=1.0, fixedAlpha=0.1):
    format = GeomVertexFormat.getV3n3cpt2()
    vdata = GeomVertexData('plane', format, Geom.UHDynamic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    vertexNormals = GeomVertexWriter(vdata, 'normal')
    vertexColors = GeomVertexWriter(vdata, 'color')
    vertexTexCoord = GeomVertexWriter(vdata, 'texcoord')

    tris = GeomTristrips(Geom.UHDynamic)

    # calculate corners:
    w_2 = width/2
    h_2 = height/2


    # Picture to have in mind:
    #
    #   3 ------ 4
    #   | \      |
    #   |  \     |
    #   |   \    |
    #   |    \   |
    #   |     \  |
    #   |      \ |
    #   1 ------ 2
    #
    #  Per the wikipedia page (https://en.wikipedia.org/wiki/Triangle_strip), this ordering 
    #   results in upwards-facing normals.

    if facing == "front": # In our world, forward is the plus y direction, (left is the negative x direction)
        vertex.addData3(cx - w_2, cy, cz - h_2)
        vertex.addData3(cx + w_2, cy, cz - h_2)
        vertex.addData3(cx - w_2, cy, cz + h_2)
        vertex.addData3(cx + w_2, cy, cz + h_2)

        # The normals have to be consistent with the triangle strips (which follow the right hand rule)
        for i in range(4):
            vertexNormals.addData3(0, -1, 0)

    elif facing == "left":
        vertex.addData3(cx, cy + w_2, cz - h_2)
        vertex.addData3(cx, cy - w_2, cz - h_2)
        vertex.addData3(cx, cy + w_2, cz + h_2)
        vertex.addData3(cx, cy - w_2, cz + h_2)

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            vertexNormals.addData3(-1, 0, 0)

    elif facing == "right":
        vertex.addData3(cx, cy - w_2, cz - h_2)
        vertex.addData3(cx, cy + w_2, cz - h_2)
        vertex.addData3(cx, cy - w_2, cz + h_2)
        vertex.addData3(cx, cy + w_2, cz + h_2)

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            vertexNormals.addData3(1, 0, 0)
    
    elif facing == "up":
        vertex.addData3(cx - w_2, cy - h_2, cz)
        vertex.addData3(cx + w_2, cy - h_2, cz)
        vertex.addData3(cx - w_2, cy + h_2, cz)
        vertex.addData3(cx + w_2, cy + h_2, cz)

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            vertexNormals.addData3(0, 0, 1)

    else:
        raise(ValueError("Unknown facing parameter: {}".format(facing)))
    

    for i in range(4):
        vertexColors.addData4f(*color, fixedAlpha)

    vertexTexCoord.addData2f(0.0, 0.0)
    vertexTexCoord.addData2f(1.0 * texHScaling, 0.0)
    vertexTexCoord.addData2f(0.0, 1.0 * texVScaling)
    vertexTexCoord.addData2f(1.0 * texHScaling, 1.0* texVScaling)
    
    tris.addVertex(0)
    tris.addVertex(1)
    tris.addVertex(2)
    tris.addVertex(3)

    wall = Geom(vdata)
    wall.addPrimitive(tris)

    return wall


# helper function to make a vertical cylinder given center, radius, and height
def makeCylinder(cx, cy, cz, radius, height, num_divisions=20, facing="outward",
                 texHScaling=1.0, texVScaling=1.0, color=[0.25, 0.25, 0.25],
                 alpha=1.0):
    format = GeomVertexFormat.getV3n3cpt2()
    vdata = GeomVertexData('cylinder', format, Geom.UHDynamic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    vertexNormals = GeomVertexWriter(vdata, 'normal')
    vertexColors = GeomVertexWriter(vdata, 'color')
    vertexTexCoord = GeomVertexWriter(vdata, 'texcoord')

    tris = GeomTristrips(Geom.UHDynamic)

    theta = [(2 * math.pi * k / num_divisions) for k in range(num_divisions)]
    theta.append(0)
    for k, th in enumerate(theta):
        if facing=="outward":
            vertex.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), cz + height/2)
            vertex.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), cz - height/2)
        elif facing=="inward":
            vertex.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), cz - height/2)
            vertex.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), cz + height/2)
        else:
            raise(ValueError("Cylinder facing direction unknown. ({})".forward(facing)))


        vertexNormals.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), 0)
        vertexNormals.addData3(cx + radius*math.cos(th), cy + radius*math.sin(th), 0)

        # adding different colors to the vertex for visibility
        vertexColors.addData4f(*color, alpha)
        vertexColors.addData4f(*color, alpha)

        vertexTexCoord.addData2f(k/num_divisions * texHScaling, 1.0 * texVScaling)
        vertexTexCoord.addData2f(k/num_divisions * texHScaling, 0.0)

        tris.addVertex(2*k)
        tris.addVertex(2*k+1)

    cylinder = Geom(vdata)
    cylinder.addPrimitive(tris)
    return cylinder
