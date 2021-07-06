# Core imports
from panda3d.core import *
from direct.showbase.ShowBase import ShowBase
# Basic intervals
# from direct.interval.IntervalGlobal import *
from direct.interval.LerpInterval import *
# Task managers
from direct.task.Task import Task
# GUI
# from direct.gui.DirectGui import *
from panda3d.core import loadPrcFileData

# Utilities
import zmq
import numpy as np
import math
import yaml

import Xlib.display # pip install python-xlib

import sys

import struct

# Local code
from ParametricShapes import makeCylinder, makePlane


# Globally change window title name
windowTitle = "Linear Environment"
loadPrcFileData("", f"window-title {windowTitle}")

display = Xlib.display.Display()
root = display.screen(0).root # TODO: Handle multiple screens with different resolution
desktop = root.get_geometry()
loadPrcFileData("", "win-size {} {}".format(desktop.width, desktop.height))
# loadPrcFileData("", "fullscreen true") # causes some sort of bug where run loop doesn't start

# You can't normalize inline so this is a helper function
def normalized(*args):
    myVec = LVector3(*args)
    myVec.normalize()
    return myVec

class App(ShowBase):
    selectedTrack = "test.track"
    currentState = None
    printStatements = True
    playerMode = True #if false, using replay zmq
    posX = 0.0
    posY = 0.0
    posZ = 0.0

    # In order to provide motion cues, we define a large cylinder to hold a background
    # texture. The goal is that the wall of this cylinder is far enough from the mouse,
    # and the texture it carries is complex enough that they get a dynamic motion cue 
    # but not a precise a spatial cue.
    roomSize = 750

    # Use cm as units
    trackWidth = 15 # This is actually how wide our running wheel is

    # The trackLength corresponds to a virtual thing. The height of the track
    #  should correspond to the physical height of the wheel because the running
    #  behavior is supposed to correspond with running on the virtual track.
    trackVPos = 0 # 0 means the track is centered on the "virtual center" of 
                    # the screen. We'll adjust to offset the monitor later.


    def __init__(self):
        ShowBase.__init__(self)

        self.paused = False
        self.gameOverTime = 0 #for camera

        fileName="example-mazes/example_teleport.yaml"
        # Read YAML file
        with open(fileName, 'r') as stream:
            self.trackConfig = yaml.safe_load(stream)

        print(self.trackConfig)
        self.trackLength = self.trackConfig.get('TrackLength', 240)
        self.wallHeight = self.trackConfig.get('WallHeight', 20)
        self.wallDistance = self.trackConfig.get('WallDistance', 24) # Ideally this is equal to the screen distances on the sides


        # For the proper VR perspective, we need to define the mouse's eye position.
        #   Because we are only using 2D displays, we'll assume they are a cyclops.
        #   Our "cameras" are just different views from the eye of the world.
        self.mouseHeight = self.trackConfig.get('MouseEyeHeight', 3) # The mouse's eye position relative to the top of the wheel
        self.cameraHeight = self.trackVPos + self.mouseHeight # The height of the eye/camera relative to 0

        ### Set up whether this will be 1 screen or multiple screens
        display_config = self.trackConfig.get('DisplayConfig',None)
        if not display_config:
            self.n_views = 1
            self.use_separate_windows = False
            self.camera_view_angles = [0]
            self.display_regions = [[0, 1, 0, 1]]

            # Physical geometry and placement of the screen
            self.screen_width, screenHeight = [51], 29 # 29.376, 16.524
            self.screenDistance = [20] # needed to calculate FOV
            # Let's describe the shape of the screen in terms of the field of view
            fov_h = math.atan2(self.screen_width[0]/2, self.screenDistance[0])*2 / math.pi * 180
            fov_v = math.atan2(screenHeight/2, self.screenDistance[0])*2 / math.pi * 180
            self.fov_h_v = [[fov_h, fov_v]]

            #   Finally, let's describe the offset of the screen from center
            self.screen_h_v_offsets = [[0, 10]] # cm
        else:
            self.n_views = display_config.get('NViews', 1)
            self.use_separate_windows = display_config.get('UseSeparateWindows', False)
            self.camera_view_angles = display_config.get('ViewAngles', [0])
            if len(self.camera_view_angles) != self.n_views:
                raise(ValueError('Must specify one camera view angle for each view.'))
            if self.use_separate_windows:
                default_display_regions = [[0,1,0,1]]*self.n_views
                self.display_regions = display_config.get('DisplayRegions', default_display_regions)
            else:
                self.display_regions = display_config.get('DisplayRegions', [[0,1,0,1]])
            if len(self.display_regions) != self.n_views:
                raise(ValueError('Must specify one display region for each view.'))

            # Physical geometry and placement of the screen(s)
            widths_and_heights = display_config.get('MonitorSizes', [[51, 29]]*self.n_views)
            if len(widths_and_heights) != self.n_views:
                raise(ValueError('Must specify physical sizes of each display.'))
            distances = display_config.get('MonitorDistances', [24]*self.n_views)
            if len(distances) != self.n_views:
                raise(ValueError('Must specify distance from eye to each display.'))
            self.screen_h_v_offsets = display_config.get('MonitorOffsets', [[0,0]]*self.n_views)

            self.screen_width = []
            self.fov_h_v = []
            for n in range(self.n_views):
                width, height = widths_and_heights[n]
                self.screen_width.append(width)
                # Let's describe the shape of the screen in terms of the field of view
                fov_h = math.atan2(width/2, distances[n])*2 / math.pi * 180
                fov_v = math.atan2(height/2, distances[n])*2 / math.pi * 180
                self.fov_h_v.append([fov_h, fov_v])

        self.cameras = []
        # Set up view(s)
        for n in range(self.n_views):
            if (n > 0):
                if self.use_separate_windows:
                    window_properties = WindowProperties()
                    window_properties.setSize(800, 600)
                    window_properties.setTitle('win2')
                    self.second_view = base.openWindow(props=window_properties, keepCamera=False, makeCamera=True, requireWindow=True)

                    # mk = base.dataRoot.attachNewNode(MouseAndKeyboard(self.second_view, 0, 'w2mouse'))
                    # bt = mk.attachNewNode(ButtonThrower('w2mouse'))
                    # mods = ModifierButtons()
                    # mods.addButton(KeyboardButton.shift())
                    # mods.addButton(KeyboardButton.control())
                    # mods.addButton(KeyboardButton.alt())
                    # bt.node().setModifierButtons(mods)

                else:
                    new_dr = base.win.makeDisplayRegion(*self.display_regions[n])
                    print(self.display_regions[n])
                    new_dr.setClearColor(VBase4(0, 0, 0, 1))
                    new_dr.setClearColorActive(True)
                    new_dr.setClearDepthActive(True)

                    new_cam = Camera('cam{}'.format(n))
                    current_cam_node = self.render.attachNewNode(new_cam)
                    new_dr.setCamera(current_cam_node)
                    # self.camera.setHpr(90, 0, 0)

                    self.cameras.append(current_cam_node)
            else:
                if not self.use_separate_windows:
                    current_cam_node = self.cam
                    self.cam.node().getDisplayRegion(0).setDimensions(*self.display_regions[n])
                self.cameras.append(self.cam)

            # The definition of the "Lens" is where the magic of VR happens. In order for things
            #   to have the perceptually correct size and shapes, we need to know the physical
            #   geometry of the display(s) that are being used.
            # To get the screen set up properly, we will want to define an off-axis camera.
            #   we'll call "setFilmOffset(hor,ver)"  to adjust it. This requires
            #   defining the "film size". We adopt the model that our screen is actually the
            #   same size as the film - that simplifies everything. The cameras will look
            #   either forward or 90 degrees to either side (a box, though we could do other
            #   angles if desired!). Without offsets, the center of each screen corresponds
            #   to the mouse's eye's view (we'll abstract their binocular vision to a single
            #   cyclops-like eye). 

            current_cam_node.setH(self.camera_view_angles[n])
            lens = PerspectiveLens()
            lens.setFov(*self.fov_h_v[n])
            # lens.setAspectRatio(1.77) # 16:9
            lens.setFilmSize(self.screen_width[n]) # in cm
            lens.setFilmOffset(*self.screen_h_v_offsets[n]) # offset in cm

            lens.setNear(1)
            lens.setFar(5000.0)
            current_cam_node.node().setLens(lens)


        self.maze_geometry_root = None
        self.maze_geometry_root = self.init_track(self.trackConfig.get('TrackFeatures', None))

        base.setBackgroundColor(0, 0, 0)  # set the background color to black

        # ZMQ connection to position data server
        data_socket_port = "8556"
        # Socket to talk to server
        context = zmq.Context()
        self.data_socket = context.socket(zmq.SUB)
        self.data_socket.connect ("tcp://localhost:%s" % data_socket_port)
        self.data_socket.setsockopt(zmq.SUBSCRIBE, b"")

        # ZMQ server connection for commands
        command_socket_port = "8557"
        # Socket to talk to server
        context = zmq.Context()
        self.command_socket = context.socket(zmq.SUB)
        self.command_socket.connect ("tcp://localhost:%s" % command_socket_port)
        self.command_socket.setsockopt(zmq.SUBSCRIBE, b"")

        self.poller = zmq.Poller()
        self.poller.register(self.data_socket, zmq.POLLIN)
        self.poller.register(self.command_socket, zmq.POLLIN)

        self.last_timestamp = 0
        self.taskMgr.add(self.readMsgs, "ReadZMQMessages", priority=1)


        self.accept('escape', self.exit_fun)

        base.setFrameRateMeter(True)


    def remove_model(self):
        if self.maze_geometry_root:
            self.maze_geometry_root.removeNode()
            self.maze_geometry_root = None
    
    def draw_model(self):
        if self.maze_geometry_root:
            self.remove_model()
        self.maze_geometry_root = self.init_track(self.trackConfig.get('TrackFeatures', None))

    def init_track(self, trackFeatures):
        testTexture = loader.loadTexture("textures/numbers.png")
        checkerboard = loader.loadTexture("textures/checkerboard.png")
        noise = loader.loadTexture("textures/whitenoise.png")

        maze_root_node = GeomNode("maze_root_node")
        maze_geometry_root = self.render.attachNewNode(maze_root_node)

        room_wall_cylinder = makeCylinder(0, self.trackLength/2, -5*self.roomSize/2, self.roomSize, 10*self.roomSize, 
                                          facing="inward", texHScaling=12, texVScaling=12, fixedColor=1.0)

        snode = GeomNode('room_walls')
        snode.addGeom(room_wall_cylinder)
        room_walls = maze_geometry_root.attachNewNode(snode)
        room_walls.setTexture(noise)
        # walls_node.setTwoSided(True)


        # trackLength, trackWidth, wallDistance all could be parametric, but I think most likely these wouldn't need to change often
        track_parent = maze_geometry_root.attachNewNode(GeomNode('MazeParent'))

        # Floor - always the same. Really should make it slightly blue to match wheels
        floor = makePlane(0, self.trackLength/2, self.trackVPos, self.trackWidth, self.trackLength, facing="up", 
                                    fixedColor=0.1, texHScaling=10, texVScaling=self.trackLength/self.trackWidth*10)
        snode = GeomNode('floor')
        snode.addGeom(floor)
        floor_node = track_parent.attachNewNode(snode)
        floor_node.setTexture(noise) # The fiberglass wheel has a noise-like texture. Its more like cross hatching, but that's ok for now

        # if self.printStatements:
        #     print("i: -1",  "startPoint: ",  points[0]-100, "endPoint: ", 250)

        if trackFeatures:
            for featureName, feature in trackFeatures.items():
                if feature.get('Type') == 'Wall':
                    snode = GeomNode(featureName)
                    length = feature['Bounds'][1] - feature['Bounds'][0]
                    center = (feature['Bounds'][1] + feature['Bounds'][0])/2
                    texScale = feature.get('TextureScaling', 1.0)
                    right = makePlane(self.wallDistance, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="left", fixedColor=0.5,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                    snode.addGeom(right)
                    left = makePlane(-self.wallDistance, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="right", fixedColor=0.5,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                    snode.addGeom(left)
                    if feature.get('DuplicateForward', True):
                        wall_segment = track_parent.attachNewNode(snode)
                    else:
                        wall_segment = maze_geometry_root.attachNewNode(snode)
                    tex = loader.loadTexture(feature['Texture'])
                    wall_segment.setTexture(tex)
                    if 'RotateTexture' in feature:
                        wall_segment.setTexRotate(TextureStage.getDefault(), feature['RotateTexture'])
                elif feature.get('Type') == 'Plane':
                    snode = GeomNode(featureName)
                    width = feature.get('Width')
                    height = feature.get('Height')
                    texScale = feature.get('TextureScaling', 1.0)
                    plane = makePlane(feature.get('XPos', 0), feature.get('YPos', 0), feature.get('ZPos', 0), 
                                                    width, feature.get('Height'), facing=feature.get('Facing'),
                                                    fixedColor=0.75,texHScaling=width/height*texScale, texVScaling=texScale)
                    snode.addGeom(plane)
                    if feature.get('DuplicateForward', True):
                        plane_node = track_parent.attachNewNode(snode)
                    else:
                        plane_node = maze_geometry_root.attachNewNode(snode)                    
                    if 'Texture' in feature:
                        tex = loader.loadTexture(feature['Texture'])
                        wall_segment.setTexture(tex)
                        if 'RotateTexture' in feature:
                            wall_segment.setTexRotate(TextureStage.getDefault(), feature['RotateTexture'])
                elif feature.get('Type') == 'Cylinder':
                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)
                    texScale = feature.get('TextureScaling', 1.0)
                    snode = GeomNode(featureName)
                    if feature.get('XLocation', 'Both') in ['Left', 'Both']:
                        cylinder = makeCylinder(-self.wallDistance, feature.get('YLocation'), 
                                                            self.trackVPos, r, h, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h)
                        snode.addGeom(cylinder)
                    
                    if feature.get('XLocation', 'Both') in ['Right', 'Both']:
                        cylinder = makeCylinder(self.wallDistance, feature.get('YLocation'), 
                                                            self.trackVPos, r, h, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h)
                        snode.addGeom(cylinder)
                    if feature.get('DuplicateForward', True):
                        cylinder_node = track_parent.attachNewNode(snode)
                    else:
                        cylinder_node = maze_geometry_root.attachNewNode(snode)
                    
                    tex = loader.loadTexture(feature['Texture'])
                    cylinder_node.setTexture(tex)
                    if 'RotateTexture' in feature:
                        wall_segment.setTexRotate(TextureStage.getDefault(), feature['RotateTexture'])

            # BIG TODO - add in sgments of default color featureless wall between the labeled sections.
            #          - we can do this in the YAML file, but it seems cleaner to have it done automatically.
            #          - need a function to (1) check that bounds never overlap, and (2) find residual
            #            segment boundaries


        else:
            # Default walls - light gray. Height could be parametric. These will fill any unspecified gaps
            snode = GeomNode('default_walls')
            right = makePlane(self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="left", fixedColor=0.5,
                                            texHScaling=self.trackLength/self.wallHeight)
            snode.addGeom(right)
            left = makePlane(-self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="right", fixedColor=0.5,
                                            texHScaling=self.trackLength/self.wallHeight)
            snode.addGeom(left)
            walls = track_parent.attachNewNode(snode)



        # Make a copy of the walls and floor at the end of the maze. This makes it look like it goes on further
        node = GeomNode('track_copy')
        maze_geometry_copy_parent = maze_geometry_root.attachNewNode(node)
        second_maze = track_parent.copyTo(maze_geometry_copy_parent)
        maze_geometry_copy_parent.setPos(0, self.trackLength, 0)

        return maze_geometry_root

    def exit_fun(self):
        print('Exit called')
        sys.exit()

    def readMsgs(self, task):
        posY = self.posY
        msg_list = self.poller.poll(timeout=0.5)
        while msg_list:
            for sock, event in msg_list:
                if sock == self.data_socket:
                    msg = self.data_socket.recv()
                    self.last_timestamp, posY = struct.unpack('<Ld',msg)
                    if posY != self.posY:
                        self.posY = posY
                        # print(self.posY)
                elif sock==self.command_socket:
                    msg = self.command_socket.recv()
                    print("Message received: ", msg)
                    if msg == b'Reset':
                        self.draw_model()
                    elif msg == b'Exit':
                        self.exit_fun()
                else:
                    msg = sock.recv()
                    print(msg)
            msg_list = self.poller.poll(timeout=0.5)


        for c in self.cameras:
            c.setPos(self.posX, self.posY, self.posZ + self.cameraHeight)

        return Task.cont

    def getPos(self):
        return self.posX, self.posY, self.posZ

    def setPos(self, x, y, z):
        self.posX = x
        self.posY = y
        self.posZ = z

app = App()
app.run()
