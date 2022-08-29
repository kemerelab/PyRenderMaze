# Core imports
# from panda3d.core import *
# from direct.showbase.ShowBase import ShowBase
# from direct.gui.OnscreenText import OnscreenText
# # Task managers
# from direct.task.Task import Task
# # GUI
# from panda3d.core import loadPrcFileData

# Utilities
import time
from ctypes import c_int
import pyglet
from pyglet.window import key

import zmq
import math
import yaml
from subprocess import check_output

import platform
import socket

# Local code
from ParametricShapes import makeCylinder, makePlane

version = '1.1'
DISPLAY_FPS = True

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


class Window(pyglet.window.Window):

    def setLock(self, state):
        self.lock = state
        self.set_exclusive_mouse(state)

    lock = False
    mouse_lock = property(lambda self:self.lock, setLock)

    def __init__(self, synced_position, *args, **kwargs):
        display = pyglet.canvas.Display()
        screen = display.get_default_screen()
        self.screen_h_res = screen.width
        self.screen_v_res = screen.height

        # super().__init__(width=self.screen_h_res, height=self.screen_v_res,
        #                 #  style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
        #                  caption="PyRenderMaze", *args, **kwargs)
        super().__init__(fullscreen=True, caption="PyRenderMaze", *args, **kwargs)

        self._synced_position = synced_position

        # Read YAML file
        with open("display_config.yaml", 'r') as stream:
            display_config = yaml.safe_load(stream)

        self.keys = key.KeyStateHandler()
        self.push_handlers(self.keys)
        pyglet.clock.schedule(self.update)

        if DISPLAY_FPS:
            self.fps_display = pyglet.window.FPSDisplay(self)

        self.mouseHeight = display_config.get('MouseEyeHeight', 3) # The mouse's eye position relative to the top of the wheel
        self.cameraHeight = 0 + self.mouseHeight # The height of the eye/camera relative to 0

        self.camera_view_angle = display_config.get('ViewAngle', 0) # default to straight ahead (this is actually 90 degrees!)

        self.player = Player((0,0,1),(90, self.camera_view_angle))
        
        # Physical geometry and placement of the screen(s)
        monitor_width, monitor_height = display_config.get('MonitorSize', [51, 29]) # default to a big, 51x29 cm screen

        phys_disp_region = display_config.get('DisplayRegion', 
                                                  [0,0,monitor_width, monitor_height]) # default to full screen
        self.screen_width, self.screen_height = phys_disp_region[2], phys_disp_region[3]

        # window size in pixels
        h_res, v_res = self.width, self.height

        self.display_regions = [int(phys_disp_region[0] / float(monitor_width) * h_res), # display region in pixels
                                int(phys_disp_region[1] / float(monitor_height) * v_res),
                                       int(phys_disp_region[2] / float(monitor_width) * h_res),
                                int(phys_disp_region[3] / float(monitor_height) * v_res),]


        self.distance = display_config.get('MonitorDistance', 24) # default to 24 cm distance

        self.z_clipping = display_config.get('ClippingDistance', 0.05) # default to clipping only the closest 5 mm
        self.max_clipping_distance = 1000

        self.screen_h_v_offsets = display_config.get('MonitorOffset', [0,0]) # default to no display center offset

        self.model = None
        self.show_IP = True

        IP = self.get_IP_address()

        self.IP_label = pyglet.text.Label(IP,
                          font_name='Arial',
                          font_size=36,
                          x=self.width, y=self.height,
                          anchor_x='right', anchor_y='top')

    def get_IP_address(self):
        IP = None
        if platform.system() == 'Linux':
            IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
            while len(IP) < 7:
                IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
        elif platform.system() == 'Darwin':
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s: 
                s.connect(('8.8.8.8', 80)) 
                IP = s.getsockname()[0]
        
        return IP

    def construct_model(self, config={}):
        if self.model:
            del(self.model)
        self.model = Model(config)

    def on_mouse_motion(self,x,y,dx,dy):
        if self.mouse_lock: self.player.mouse_motion(dx,dy)

    def on_key_press(self, KEY, _MOD):
        if KEY == key.ESCAPE:
            self.has_exit = True
        elif KEY == key.E:
            self.mouse_lock = not self.mouse_lock

    def update(self, dt):
        self.player.update(dt, self.keys)

    def on_draw(self):
        self.clear()
        pyglet.gl.glViewport(0, 0, self.width, self.height)

        if self.show_IP: # Show IP Address if model is not defined
            pyglet.gl.glMatrixMode(pyglet.gl.GL_MODELVIEW)
            pyglet.gl.glPushMatrix()
            pyglet.gl.glLoadIdentity()

            pyglet.gl.glMatrixMode(pyglet.gl.GL_PROJECTION)
            pyglet.gl.glPushMatrix()
            pyglet.gl.glLoadIdentity()
            pyglet.gl.glOrtho(0, self.width, 0, self.height, -1, 1)

            self.IP_label.draw()                

            pyglet.gl.glPopMatrix()

            pyglet.gl.glMatrixMode(pyglet.gl.GL_MODELVIEW)
            pyglet.gl.glPopMatrix()

        if DISPLAY_FPS:
            self.fps_display.draw()

        pyglet.gl.glViewport(*self.display_regions)
        # Projection
        pyglet.gl.glMatrixMode(pyglet.gl.GL_PROJECTION)
        pyglet.gl.glLoadIdentity()

        clip_scale = self.z_clipping/self.distance
        pyglet.gl.glFrustum(clip_scale * (-self.screen_width/2 - self.screen_h_v_offsets[0]), 
                            clip_scale *  (  self.screen_width/2 - self.screen_h_v_offsets[0]), 
                            clip_scale *  (-self.screen_height/2 - self.screen_h_v_offsets[1]),
                            clip_scale * ( self.screen_height/2 - self.screen_h_v_offsets[1]),
                            self.z_clipping, self.max_clipping_distance)
        # pyglet.gl.gluPerspective(self.fov_h_v[1], self.aspect, 0.05, 1000)
        # Model
        pyglet.gl.glMatrixMode(pyglet.gl.GL_MODELVIEW)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glPushMatrix()
        rot = self.player.rot
        pos = self.player.pos
        pyglet.gl.glRotatef(-rot[0],1,0,0)
        pyglet.gl.glRotatef(-rot[1],0,0,1)
        # pyglet.gl.glTranslatef(-pos[0], -pos[1], -pos[2])
        pyglet.gl.glTranslatef(0, -pos[1], 0)
        # pyglet.gl.glTranslatef(0, self._synced_position.value, 0)

        self.model.draw()

        pyglet.gl.glPopMatrix(  )

class Player:
    def __init__(self, pos=(0, 0, 0), rot=(0, 0)):
        self.pos = list(pos)
        self.rot = list(rot)

    def update(self,dt,keys):
        sens = 0.1
        s = dt*10
        rotY = -self.rot[1]/180*math.pi
        dx, dz = s*math.sin(rotY), math.cos(rotY)
        if keys[key.W]:
            self.pos[0] += dx*sens
            self.pos[2] -= dz*sens
        if keys[key.S]:
            self.pos[0] -= dx*sens
            self.pos[2] += dz*sens
        if keys[key.A]:
            self.pos[0] -= dz*sens
            self.pos[2] -= dx*sens
        if keys[key.D]:
            self.pos[0] += dz*sens
            self.pos[2] += dx*sens
        if keys[key.SPACE]:
            self.pos[1] += s
        if keys[key.LSHIFT]:
            self.pos[1] -= s

from communications_process import start_commmunicator
import multiprocessing
from ctypes import c_int, c_double

if __name__ == '__main__':

    config_queue = multiprocessing.Queue()
    synced_state = multiprocessing.Value(c_int)
    synced_position = multiprocessing.Value(c_double)

    synced_position.value = 0.0

    window = Window(synced_position, resizable=True, vsync=True)

    window.construct_model({})    
    synced_state.value = 1

    communicator_process = multiprocessing.Process(target=start_commmunicator, args=(synced_state, synced_position, config_queue))
    communicator_process.start()

    pyglet.gl.glClearColor(0,0,0,1)
    pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
    pyglet.gl.glEnable(pyglet.gl.GL_ALPHA_TEST)
    
    # pyglet.app.run()
    while True:
        if synced_state.value == 0: # communicator received a new model!
            model_config = config_queue.get()
            try:
                window.construct_model(model_config)
                synced_state.value = 1
                window.show_IP = False # We successfully updated model, so stop displaying IP
            except:
                synced_state = -1

        if (not window.visible):
            break

        if (window.has_exit):
            print("PyRenderMaze exiting.")
            synced_state.value = -2
            window.close()
            break

        if (synced_state == -2):
            window.close()
            break

        pyglet.clock.tick()

        if (window):
            window.dispatch_events()
            window.dispatch_event('on_draw')
            window.flip()

    communicator_process.join()
