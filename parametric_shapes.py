# Core imports
import pyglet
from pyglet.window import key
import math

def add_degenerates(alist, chunksize):
    return [*alist[:chunksize], *alist, *alist[-chunksize:]]

# helper function to make a vertical cylinder given center, radius, and height
def makePlane(batch, texgroup, cx, cy, cz, width, height, facing="left", color=[0.25, 0.25, 0.25], 
              texHScaling=1.0, texVScaling=1.0, alpha=1.0):

    # This function will return a TriStrip plane object
    #  We'll encode as a 4-component color, 3-component normal, and 3-component vertex position
    #  Moreover, we'll include the Texture Coordinates in a separate 2-component list

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

    vertices = []
    normals = []
    if facing.lower() == "front": # In our world, forward is the plus y direction, (left is the negative x direction)
        vertices.extend([cx - w_2, cy, cz - h_2])
        vertices.extend([cx + w_2, cy, cz - h_2])
        vertices.extend([cx - w_2, cy, cz + h_2])
        vertices.extend([cx + w_2, cy, cz + h_2])

        # The normals have to be consistent with the triangle strips (which follow the right hand rule)
        for i in range(4):
            normals.extend([0, -1, 0])

    elif facing.lower() == "left":
        vertices.extend([cx, cy + w_2, cz - h_2])
        vertices.extend([cx, cy - w_2, cz - h_2])
        vertices.extend([cx, cy + w_2, cz + h_2])
        vertices.extend([cx, cy - w_2, cz + h_2])

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            normals.extend([-1, 0, 0])

    elif facing.lower() == "right":
        vertices.extend([cx, cy - w_2, cz - h_2])
        vertices.extend([cx, cy + w_2, cz - h_2])
        vertices.extend([cx, cy - w_2, cz + h_2])
        vertices.extend([cx, cy + w_2, cz + h_2])

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            normals.extend([1, 0, 0])
    
    elif facing.lower() == "up":
        vertices.extend([cx - w_2, cy - h_2, cz])
        vertices.extend([cx + w_2, cy - h_2, cz])
        vertices.extend([cx - w_2, cy + h_2, cz])
        vertices.extend([cx + w_2, cy + h_2, cz])

        # The normals have to be consistent with the triangle strips (right hand rule)
        for i in range(4):
            normals.extend([0, 0, 1])

    else:
        raise(ValueError("Unknown facing parameter: {}".format(facing)))
    

    colors = []
    for i in range(4):
        colors.extend([*color, alpha])

    tex_coords = []
    tex_coords.extend([0.0, 0.0])
    tex_coords.extend([1.0 * texHScaling, 0.0])
    tex_coords.extend([0.0, 1.0 * texVScaling])
    tex_coords.extend([1.0 * texHScaling, 1.0* texVScaling])


    vlist = batch.add_indexed(4+2, pyglet.gl.GL_TRIANGLE_STRIP, texgroup,
                range(4+2), # index is just 0, 1, 2, 3
                ('v3f', add_degenerates(vertices,3)),
                ('c4f', add_degenerates(colors,4)),
                ('n3f', add_degenerates(normals,3)),
                ('t2f', add_degenerates(tex_coords,2))
            )

    return vlist


# helper function to make a vertical cylinder given center, radius, and height
def makeCylinder(batch, texgroup, cx, cy, cz, radius, height, num_divisions=30, facing="outward",
                 texHScaling=1.0, texVScaling=1.0, color=[0.25, 0.25, 0.25],
                 alpha=1.0):

    theta = [(2 * math.pi * k / num_divisions) for k in range(num_divisions)]
    theta.append(0)

    vertices = []
    normals = []
    colors = []
    tex_coords = []
    tri_indices = []

    for k, th in enumerate(theta):
        if facing.lower()=="outward":
            vertices.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), cz + height/2])
            vertices.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), cz - height/2])
        elif facing.lower()=="inward":
            vertices.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), cz - height/2])
            vertices.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), cz + height/2])
        else:
            raise(ValueError("Cylinder facing direction unknown. ({})".forward(facing)))

        normals.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), 0])
        normals.extend([cx + radius*math.cos(th), cy + radius*math.sin(th), 0])

        # adding different colors to the vertex for visibility
        colors.extend([*color, alpha])
        colors.extend([*color, alpha])

        tex_coords.extend([k/num_divisions * texHScaling, 1.0 * texVScaling])
        tex_coords.extend([k/num_divisions * texHScaling, 0.0])

        tri_indices.append(2*k)
        tri_indices.append(2*k+1)

    vlist = batch.add_indexed(len(tri_indices)+2, pyglet.gl.GL_TRIANGLE_STRIP, texgroup,
            range((num_divisions+3)*2), 
            ('v3f', add_degenerates(vertices,3)),
            ('c4f', add_degenerates(colors,4)),
            ('n3f', add_degenerates(normals,3)),
            ('t2f', add_degenerates(tex_coords,2))
        )            

    return vlist
