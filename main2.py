# Core imports
# from panda3d.core import *
# from direct.showbase.ShowBase import ShowBase
# from direct.gui.OnscreenText import OnscreenText
# # Task managers
# from direct.task.Task import Task
# # GUI
# from panda3d.core import loadPrcFileData

# Utilities
import pyglet
from pyglet.window import key

import zmq
# import numpy as np
import math
import yaml
import pickle
import datetime
import csv

import sys
from subprocess import check_output

import struct

import platform
import socket

# Local code
from ParametricShapes import makeCylinder, makePlane

version = '1.1'


class Model:
    # In order to provide motion cues, we define a large cylinder to hold a background
    # texture. The goal is that the wall of this cylinder is far enough from the mouse,
    # and the texture it carries is complex enough that they get a dynamic motion cue 
    # but not a precise a spatial cue.    
    roomSize = 750
    # The trackLength corresponds to a virtual thing. The height of the track
    #  should correspond to the physical height of the wheel because the running
    #  behavior is supposed to correspond with running on the virtual track.
    trackVPos = 0 # 0 means the track is centered on the "virtual center" of 
                    # the screen. We'll adjust to offset the monitor later.


    def init_track(self, trackConfig):
        trackFeatures = trackConfig.get('TrackFeatures', None)

        self.trackLength = trackConfig.get('TrackLength', 240)
        self.wallHeight = trackConfig.get('WallHeight', 20)
        self.wallDistance = trackConfig.get('WallDistance', 24) # Ideally this is equal to the screen distances on the sides


        self.nodes = []

        if trackConfig.get('EnableBackgroundTexture', True):
            batch = pyglet.graphics.Batch()
            noise = self.get_tex("textures/whitenoise.png")
            # background = pyglet.graphics.Batch()
            room_wall_cylinder = makeCylinder(batch, noise, 0, self.trackLength/2, -5*self.roomSize/2, self.roomSize, 10*self.roomSize, 
                                              facing="inward", texHScaling=12, texVScaling=12, color=[1.0, 1.0, 1.0])
            self.nodes.append((batch, noise))

        if trackFeatures:
            for featureName, feature in trackFeatures.items():
                color = feature.get('Color', [0.5, 0.5, 0.5])
                texScale = feature.get('TextureScaling', 1.0)
                alpha = feature.get('Alpha', 1.0)
                
                if 'Texture' in feature:
                    tex = self.get_tex(feature['Texture'])
                    # if 'RotateTexture' in feature:
                    #     node.setTexRotate(TextureStage.getDefault(), feature['RotateTexture'])
                else:
                    tex = None


                if feature.get('Type') == 'Wall':

                    length = feature['Bounds'][1] - feature['Bounds'][0]
                    center = (feature['Bounds'][1] + feature['Bounds'][0])/2
                    x_offset = feature.get('XOffset', 0)

                    batch = pyglet.graphics.Batch()

                    if feature.get('XLocation', 'Both').lower() in ['right', 'both']:
                        right = makePlane(batch, tex, self.wallDistance + x_offset, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="Left", color=color, alpha=alpha,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                    if feature.get('XLocation', 'Both').lower() in ['left', 'both']:
                        left = makePlane(batch, tex, -self.wallDistance - x_offset, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="Right", color=color, alpha=alpha,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)

                    self.nodes.append((batch, tex)) # Can batch draw both planes

                elif feature.get('Type') == 'Plane':
                    width = feature.get('Width')
                    height = feature.get('Height')
                    batch = pyglet.graphics.Batch()
                    plane = makePlane(batch, tex, feature.get('XPos', 0), feature.get('YPos', 0), feature.get('ZPos', 0), 
                                                    width, feature.get('Height'), facing=feature.get('Facing'),
                                                    color=color, alpha=alpha,
                                                    texHScaling=width/height*texScale, texVScaling=texScale)
                    self.nodes.append((batch, tex))

                elif feature.get('Type') == 'WallCylinder':
                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)

                    if feature.get('XLocation', 'Both').lower() in ['left', 'both']:
                        batch = pyglet.graphics.Batch()
                        cylinder = makeCylinder(batch, tex, -self.wallDistance, feature.get('YPos'), 
                                                            self.trackVPos, r, h, color=color, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                        self.nodes.append((batch, tex)) # Can't batch draw both cylinders b/c of glitching
                    
                    if feature.get('XLocation', 'Both').lower() in ['right', 'both']:
                        batch = pyglet.graphics.Batch()
                        cylinder = makeCylinder(batch, tex, self.wallDistance, feature.get('YPos'), 
                                                            self.trackVPos, r, h, color=color, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h, alpha=alpha)
                        self.nodes.append((batch, tex)) # Can't batch draw both cylinders b/c of glitching

                elif feature.get('Type') == 'Cylinder':
                    batch = pyglet.graphics.Batch()

                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)
                    cylinder = makeCylinder(batch, tex, feature.get('XPos'), feature.get('YPos'), 
                                                        feature.get('ZPos', self.trackVPos), r, h, facing=feature.get('Facing','outward'),
                                                        color=color, texHScaling=texScale, 
                                                        texVScaling=texScale * (math.pi * 2 * r) / h,
                                                        alpha=alpha)

                    self.nodes.append((batch, tex)) # Can't batch draw both cylinders b/c of glitching

                # if feature.get('DuplicateForward', True):
                #     node = track_parent.attachNewNode(snode)


            # BIG TODO - add in sgments of default color featureless wall between the labeled sections.
            #          - we can do this in the YAML file, but it seems cleaner to have it done automatically.
            #          - need a function to (1) check that bounds never overlap, and (2) find residual
            #            segment boundaries


        else:
            batch = pyglet.graphics.Batch()

            # Default walls - light gray. Height could be parametric. These will fill any unspecified gaps
            right = makePlane(batch, None, self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="left", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)

            left = makePlane(batch, None, -self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="right", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)
            self.nodes.append((batch, None)) # Can't batch draw both cylinders b/c of glitching


            if not self.IP_address_text:
                IP = None
                if platform.system() == 'Linux':
                    # Render IP address by default
                    IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
                    while len(IP) < 7:
                        IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
                elif platform.system() == 'Darwin':
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s: 
                        s.connect(('8.8.8.8', 80)) 
                        IP = s.getsockname()[0]
                # self.IP_address_text = OnscreenText(text=IP, pos=(0, 0.75), scale=0.1, align=TextNode.ACenter, fg=[1, 0, 0, 1])


        return


    def get_tex(self,file):
        tex = pyglet.image.load(file).get_texture()
        pyglet.gl.glTexParameterf(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        # pyglet.gl.glTexParameterf(pyglet.gl.GL_TEXTURE_2D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        return pyglet.graphics.TextureGroup(tex)

    def __init__(self):
            
        maze_config_filename = "example-mazes/example_teleport.yaml"
        with open(maze_config_filename, "r") as stream:
            maze_config = yaml.safe_load(stream)

        self.init_track(maze_config)

    def draw(self):
        for batch,_ in self.nodes:
            batch.draw()


class Window(pyglet.window.Window):

    def push(self,pos,rot):
        pyglet.gl.glPushMatrix()
        rot = self.player.rot
        pos = self.player.pos
        pyglet.gl.glRotatef(-rot[0],1,0,0)
        pyglet.gl.glRotatef(-rot[1],0,0,1)
        pyglet.gl.glTranslatef(-pos[0], -pos[1], -pos[2])

    def Projection(self):
        pyglet.gl.glMatrixMode(pyglet.gl.GL_PROJECTION)
        pyglet.gl.glLoadIdentity()

    def Model(self):
        pyglet.gl.glMatrixMode(pyglet.gl.GL_MODELVIEW)
        pyglet.gl.glLoadIdentity()

    def setupView(self):
        self.Projection()
        pyglet.gl.glFrustum(0.05/self.distance * (-self.screen_width/2 - self.screen_h_v_offsets[0]), 
                            0.05/self.distance * (  self.screen_width/2 - self.screen_h_v_offsets[0]), 
                            0.05/self.distance * (-self.screen_height/2 - self.screen_h_v_offsets[1]),
                            0.05/self.distance * ( self.screen_height/2 - self.screen_h_v_offsets[1]),
                            0.05, self.model.roomSize*1.5)
        # pyglet.gl.gluPerspective(70, self.screen_width/self.screen_height, 0.05, 1000)
        self.Model()

    def setLock(self, state):
        self.lock = state
        self.set_exclusive_mouse(state)

    lock = False
    mouse_lock = property(lambda self:self.lock, setLock)

    def __init__(self, *args, **kwargs):
        # Read YAML file
        with open("display_config.yaml", 'r') as stream:
            display_config = yaml.safe_load(stream)

        # Globally change window title name
        # windowTitle = "PyRenderMaze"

        w, h = display_config.get("WindowSize", (800, 600))

        super().__init__(fullscreen=True, caption="PyRenderMaze", *args, **kwargs)

        # loadPrcFileData("", "fullscreen true") # causes some sort of bug where run loop doesn't start in Ubuntu

        self.keys = key.KeyStateHandler()
        self.push_handlers(self.keys)
        pyglet.clock.schedule(self.update)

        self.model = Model()

        self.fps_display = pyglet.window.FPSDisplay(self)

        self.mouseHeight = display_config.get('MouseEyeHeight', 3) # The mouse's eye position relative to the top of the wheel
        self.cameraHeight = self.model.trackVPos + self.mouseHeight # The height of the eye/camera relative to 0


        self.camera_view_angle = display_config.get('ViewAngle', 0) # default to straight ahead (this is actually 90 degrees!)

        self.display_regions = display_config.get('DisplayRegion', [0,1,0,1]) # default to full screen

        self.player = Player((0,0,1),(90, self.camera_view_angle))
        
        # Physical geometry and placement of the screen(s)
        self.screen_width, self.screen_height = display_config.get('MonitorSize', [51, 29]) # default to a big, 51x29 cm screen
        self.distance = display_config.get('MonitorDistance', 24) # default to 24 cm distance
        self.screen_h_v_offsets = display_config.get('MonitorOffset', [0,0]) # default to no display center offset

        # Let's describe the shape of the screen in terms of the field of view angles.
        #   (This requires a bit of geometry!)
        # fov_h = math.atan2(width/2, distance)*2 / math.pi * 180
        # fov_v = math.atan2(height/2, distance)*2 / math.pi * 180
        # self.fov_h_v = [fov_h, fov_v]
        

    def on_mouse_motion(self,x,y,dx,dy):
        if self.mouse_lock: self.player.mouse_motion(dx,dy)

    def on_key_press(self, KEY, _MOD):
        if KEY == key.ESCAPE:
            self.close()
        elif KEY == key.E:
            self.mouse_lock = not self.mouse_lock

    def update(self, dt):
        self.player.update(dt, self.keys)

    def on_draw(self):
        self.clear()
        self.setupView()
        self.push(self.player.pos,self.player.rot)
        self.model.draw()
        pyglet.gl.glPopMatrix()
        pyglet.gl.glViewport(*self.display_regions)

        self.fps_display.draw()

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
            print(self.pos)
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
            print(self.pos)
        if keys[key.LSHIFT]:
            self.pos[1] -= s

if __name__ == '__main__':
    window = Window(resizable=True)
    pyglet.gl.glClearColor(0,0,0,1)
    pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
    pyglet.gl.glEnable(pyglet.gl.GL_ALPHA_TEST)
    pyglet.app.run()
