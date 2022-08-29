# Core imports
import pyglet
import math

# Local code
from parametric_shapes import makeCylinder, makePlane

class Model:
    def __init__(self, maze_config={}):
        self.trackLength = maze_config.get('TrackLength', 240)
        # The trackLength corresponds to a virtual thing. 
        self.wallHeight = maze_config.get('WallHeight', 20)
        self.wallDistance = maze_config.get('WallDistance', 24) # Ideally this is equal to the screen distances on the sides

        # The vertical position of the track should correspond to the physical height of the wheel because the running
        #  behavior is supposed to correspond with running on the virtual track. We assume in the model that this corresponds
        #  to vertical position 0. We use the Frustum to adjust to offset the model center.

        self.gl_objects = [] # track the vlist, associated texture, and a boolean for whether the texture was previously used
        self.batch = pyglet.graphics.Batch()

        if maze_config.get('EnableBackgroundTexture', True):
        # In order to provide motion cues, we define a large cylinder to hold a background
        # texture. The goal is that the wall of this cylinder is far enough from the mouse,
        # and the texture it carries is complex enough that they get a dynamic motion cue 
        # but not a precise a spatial cue.    
            roomSize = 750

            tex, texgroup = self.get_tex("textures/whitenoise.png")
            vlist = makeCylinder(self.batch, texgroup, 0, self.trackLength/2, -5*roomSize/2, roomSize, 10*roomSize, 
                         facing="inward", texHScaling=12, texVScaling=12, color=[1.0, 1.0, 1.0])
            self.gl_objects.append((vlist, tex, False))


        trackFeatures = maze_config.get('TrackFeatures', None)

        if trackFeatures:
            for featureName, feature in trackFeatures.items():
                color = feature.get('Color', [0.5, 0.5, 0.5])
                texScale = feature.get('TextureScaling', 1.0)
                alpha = feature.get('Alpha', 1.0)
                
                if 'Texture' in feature:
                    tex, texgroup = self.get_tex(feature['Texture'], feature.get('RotateTexture', 0))
                else:
                    tex = None

                if feature.get('Type') == 'Wall':
                    length = feature['Bounds'][1] - feature['Bounds'][0]
                    center = (feature['Bounds'][1] + feature['Bounds'][0])/2
                    x_offset = feature.get('XOffset', 0)

                    if feature.get('XLocation', 'Both').lower() in ['right', 'both']:
                        vlist = makePlane(self.batch, texgroup, self.wallDistance + x_offset, center, 0 + self.wallHeight/2, 
                                  length, self.wallHeight, facing="Left", color=color, alpha=alpha,
                                  texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                        self.gl_objects.append((vlist, tex, False))
                                  
                        if feature.get('DuplicateForward', True):
                            vlist = makePlane(self.batch, texgroup, self.wallDistance + x_offset, center + self.trackLength, 
                                      0 + self.wallHeight/2, 
                                      length, self.wallHeight, facing="Left", color=color, alpha=alpha,
                                      texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                            self.gl_objects.append((vlist, tex, True))

                    if feature.get('XLocation', 'Both').lower() in ['left', 'both']:
                        vlist = makePlane(self.batch, texgroup, -self.wallDistance - x_offset, center, 0 + self.wallHeight/2, 
                                  length, self.wallHeight, facing="Right", color=color, alpha=alpha,
                                  texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                        self.gl_objects.append((vlist, tex, feature.get('XLocation', 'left').lower() == 'Both'))
                        if feature.get('DuplicateForward', True):
                            vlist = makePlane(self.batch, texgroup, -self.wallDistance - x_offset, center + self.trackLength, 
                                      0 + self.wallHeight/2, 
                                      length, self.wallHeight, facing="Right", color=color, alpha=alpha,
                                      texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                            self.gl_objects.append((vlist, tex, True))

                elif feature.get('Type') == 'Plane':
                    width = feature.get('Width')
                    height = feature.get('Height')
                    vlist = makePlane(self.batch, texgroup, feature.get('XPos', 0), feature.get('YPos', 0), feature.get('ZPos', 0), 
                              width, feature.get('Height'), facing=feature.get('Facing'),
                              color=color, alpha=alpha, texHScaling=width/height*texScale, texVScaling=texScale)
                    self.gl_objects.append((vlist, tex, False))
                    if feature.get('DuplicateForward', True):
                        vlist = makePlane(self.batch, texgroup, feature.get('XPos', 0), feature.get('YPos', 0) + self.trackLength, 
                                  feature.get('ZPos', 0), 
                                  width, feature.get('Height'), facing=feature.get('Facing'),
                                  color=color, alpha=alpha, texHScaling=width/height*texScale, texVScaling=texScale)
                        self.gl_objects.append((vlist, tex, True))

                elif feature.get('Type') == 'WallCylinder':
                    h = feature.get('Height',self.wallHeight*2)
                    r = feature.get('Radius',5)

                    if feature.get('XLocation', 'Both').lower() in ['left', 'both']:
                        vlist = makeCylinder(self.batch, texgroup, -self.wallDistance, feature.get('YPos'), 
                                     0 + h/2, r, h, color=color, texHScaling=texScale, 
                                     texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                        self.gl_objects.append((vlist, tex, False))
                        if feature.get('DuplicateForward', True):
                            vlist = makeCylinder(self.batch, texgroup, -self.wallDistance, feature.get('YPos') + self.trackLength, 
                                        0 + h/2, r, h, color=color, texHScaling=texScale, 
                                        texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                            self.gl_objects.append((vlist, tex, True))
                    
                    if feature.get('XLocation', 'Both').lower() in ['right', 'both']:
                        makeCylinder(self.batch, texgroup, self.wallDistance, feature.get('YPos'), 
                                     0 + h/2, r, h, color=color, texHScaling=texScale, 
                                     texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                        self.gl_objects.append((vlist, tex, feature.get('XLocation', 'right').lower() == 'Both'))
                        if feature.get('DuplicateForward', True):
                            vlist = makeCylinder(self.batch, texgroup, self.wallDistance, feature.get('YPos') + self.trackLength, 
                                        0 + h/2, r, h, color=color, texHScaling=texScale, 
                                        texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                            self.gl_objects.append((vlist, tex, True))

                elif feature.get('Type') == 'Cylinder':
                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)
                    vlist = makeCylinder(self.batch, texgroup, feature.get('XPos'), feature.get('YPos'), 
                                 feature.get('ZPos', 0), r, h, facing=feature.get('Facing','outward'),
                                 color=color, texHScaling=texScale, 
                                 texVScaling=texScale * (math.pi * 2 * r) / h,
                                 alpha=alpha)
                    self.gl_objects.append((vlist, tex, False))
                    if feature.get('DuplicateForward', True):
                        makeCylinder(self.batch, texgroup, feature.get('XPos'), feature.get('YPos') + self.trackLength, 
                                    feature.get('ZPos', 0), r, h, facing=feature.get('Facing','outward'),
                                    color=color, texHScaling=texScale, 
                                    texVScaling=texScale * (math.pi * 2 * r) / h,
                                    alpha=alpha)
                        self.gl_objects.append((vlist, tex, True))



            # BIG TODO - add in sgments of default color featureless wall between the labeled sections.
            #          - we can do this in the YAML file, but it seems cleaner to have it done automatically.
            #          - need a function to (1) check that bounds never overlap, and (2) find residual
            #            segment boundaries


        else:
            # Default walls - light gray. Height could be parametric. These will fill any unspecified gaps
            vlist = makePlane(self.batch, None, self.wallDistance, self.trackLength/2, 0 + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="left", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)
            self.gl_objects.append((vlist, None, True))
            vlist = makePlane(self.batch, None, -self.wallDistance, self.trackLength/2, 0 + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="right", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)
            self.gl_objects.append((vlist, None, True))


            # TODO: Add back in IP Address!

        return


    def get_tex(self,file,rotation=0):
        tex = pyglet.image.load(file).get_texture()
        pyglet.gl.glTexParameterf(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        # pyglet.gl.glTexParameterf(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        return tex, pyglet.graphics.TextureGroup(tex)


    def draw(self):
        self.batch.draw()

    def __del__(self):
        for vlist, tex, tex_is_old in self.gl_objects:
            try:
                vlist.delete()
            except:
                pass
            if not tex_is_old:
                try:
                    del(tex)
                except:
                    pass

