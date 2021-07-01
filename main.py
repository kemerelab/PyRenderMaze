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

# Local code
from ParametricShapes import makeCylinder, makePlane


# Globally change window title name
windowTitle = "Linear Environment"
loadPrcFileData("", f"window-title {windowTitle}")

# display = Xlib.display.Display()
# root = display.screen(0).root # TODO: Handle multiple screens with different resolution
# desktop = root.get_geometry()
# loadPrcFileData("", "win-size {} {}".format(desktop.width, desktop.height))
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

    # The trackLength corresponds to a virtual thing. The height of the track
    #  should correspond to the physical height of the wheel because the running
    #  behavior is supposed to correspond with running on the virtual track.
    trackVPos = 0 # This means the track is centered on the "virtual center" of
                  # the screen. We'll adjust to offset the monitor later.

    # To get the screen set up properly, we will want to define an off-axis camera.
    # Later on, we'll call "setFilmOffset(hor,ver)"  to adjust it. This requires
    #   defining the "film size". We adopt the model that our screen is actually the
    #   same size as the film - that simplifies everything. The cameras will look
    #   either forward or 90 degrees to either side (a box, though we could do other
    #   angles if desired!). Without offsets, the center of each screen corresponds
    #   to the mouse's eye's view (we'll abstract their binocular vision to a single
    #   cyclops-like eye). 

    #   Let's start by defining the camera height (mouse's eye position) relative to 0,
    #     where 0 means the center of the screen.
    mouseHeight = 3 # The mouse's eye position relative to the top of the wheel
    camHeight = trackVPos + mouseHeight # The mouse is a little bit above the wheel

    #   Next, let's describe the size of the screen in terms of the field of view
    screenWidth, screenHeight = 51, 29 # 29.376, 16.524
    screenDistance = 20 # needed to calculate FOV
    fov_h = math.atan2(screenWidth/2, screenDistance)*2 / math.pi * 180
    fov_v = math.atan2(screenHeight/2, screenDistance)*2 / math.pi * 180

    #   Finally, let's describe the offset of the screen from center
    screenHOffset, screenVOffset = 0, 10

    # In order to provide motion cues, we define a large cylinder to hold a background
    # texture. The goal is that the wall of this cylinder is far enough from the mouse,
    # and the texture it carries is complex enough that they get a dynamic motion cue 
    # but not a precise a spatial cue.
    roomSize = 750

    # Use cm as units
    trackWidth = 15 # This is actually how wide our running wheel is

    # Let's place the virtual side walls on the physical monitor location
    wallDistance = screenDistance

    def __init__(self):
        ShowBase.__init__(self)

        self.paused = False
        self.gameOverTime = 0 #for camera

        fileName="example-mazes/example1.yaml"
        # Read YAML file
        with open(fileName, 'r') as stream:
            self.trackConfig = yaml.safe_load(stream)

        print(self.trackConfig)
        self.trackLength = self.trackConfig.get('TrackLength', 240)
        self.wallHeight = self.trackConfig.get('wallHeight', 20)

        # Init camera
        self.camConfigDefault = "perspective"
        self.camConfig = self.camConfigDefault
        self.taskMgr.add(self.setCameraToPlayer, "SetCameraToPlayer")

        lens = PerspectiveLens()
        lens.setFov(self.fov_h, self.fov_v)
        # lens.setAspectRatio(1.77) # 16:9
        lens.setFilmSize(self.screenWidth) # in cm
        lens.setFilmOffset(self.screenHOffset, self.screenVOffset) # offset in cm

        lens.setNear(1)
        lens.setFar(5000.0)
        self.cam.node().setLens(lens)

        self.maze_geometry_root = None
        self.maze_geometry_root = self.init_track(self.trackConfig.get('TrackFeatures', None))

        base.setBackgroundColor(0, 0, 0)  # set the background color to black

        # Key movement
        self.isKeyDown = {}
        self.createKeyControls()

        # if (self.playerMode):
        self.taskMgr.add(self.keyPressHandler, "KeyPressHandler")
        # else:

        # Init ZMQ connection to server
        port = "8556"
        # Socket to talk to server
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        if self.printStatements:
            print("Collecting updates from keyboard server...")
        self.socket.connect ("tcp://localhost:%s" % port)
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.last_timestamp = 0
        self.taskMgr.add(self.readMsgs, "ReadZMQMessages", priority=1)


        window_properties = WindowProperties()
        window_properties.setSize(800, 600)
        window_properties.setTitle('win2')
        self.second_view = base.openWindow(props=window_properties, keepCamera=False, makeCamera=True, requireWindow=True)
        self.cam2 = base.camList[-1]
        self.camera = base.camList[0]
        print(self.camera, base.camList)

        mk = base.dataRoot.attachNewNode(MouseAndKeyboard(self.second_view, 0, 'w2mouse'))
        bt = mk.attachNewNode(ButtonThrower('w2mouse'))
        mods = ModifierButtons()
        mods.addButton(KeyboardButton.shift())
        mods.addButton(KeyboardButton.control())
        mods.addButton(KeyboardButton.alt())
        bt.node().setModifierButtons(mods)




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
                    wall_segment = track_parent.attachNewNode(snode)
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
                    cylinder_node = track_parent.attachNewNode(snode)
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
            
        # alight = AmbientLight('alight')
        # alight.setColor((1, 1, 1, 1))
        # alnp = self.render.attachNewNode(alight)
        # self.render.setLight(alnp)

        return maze_geometry_root

    def createKeyControls(self):
            functionToKeys = {
                "forward": [ "arrow_up", "w" ],     
                "backward": [ "arrow_down", "s" ],
            }

            for fn in functionToKeys:
                keys = functionToKeys[fn]

                # Initialise dictionary
                self.isKeyDown[fn] = 0

                for key in keys:
                    # Key Down
                    self.accept(key, self.setKeyDown, [fn, 1])
                    # Key Up
                    self.accept(key+"-up", self.setKeyDown, [fn, -1])

            keyReleaseMap = [
                (self.exit_fun, ["escape"], None),
                (self.remove_model, ["x"], None),
                (self.draw_model, ["m"], None),
                (self.setCameraView, ["1"], ["perspective"]),
                (self.setCameraView, ["2"], ["lookingLeft"]),
                (self.setCameraView, ["3"], ["lookingRight"]),
            ]

            for fn, keys, args in keyReleaseMap:
                for key in keys:
                    if isinstance(args, list) and len(args) > 0:
                        self.accept(key+"-up", fn, args)
                    else:
                        self.accept(key+"-up", fn)

    def exit_fun(self):
        print('Exit called')
        sys.exit()

    def setKeyDown(self, key, value):
        self.isKeyDown[key] += value
        if self.isKeyDown[key] < 0:
            self.isKeyDown[key] = 0

    def setCameraToPlayer(self, task):
        if self.camConfig == "lookingLeft":
            self.camera.setHpr(90, 0, 0)
        elif self.camConfig == "lookingRight":
            self.camera.setHpr(-90, 0, 0)
        else: # looking straight ahead
            # self.camera.setHpr(0, 0, 0)
            pass

        self.camera.setPos(self.posX, self.posY, self.posZ + self.camHeight)
        self.cam2.setPos(self.posX, self.posY, self.posZ + self.camHeight)
        # self.camera.setPos(self.posX + xOffset, (self.posY) % self.racetrack.treadmillLength, self.posZ + camHeight)

        return Task.cont

    def setCameraView(self, view):
        self.camConfig = view

    def keyPressHandler(self, task):
        flag = False
        if self.isKeyDown["forward"] > 0:
            self.posY += 1
            if (self.posY >= self.trackLength):
                self.posY = 0
            flag = True
        if self.isKeyDown["backward"] > 0:
            self.posY -= 1
            if (self.posY < 0):
                self.posY = self.trackLength
            flag = True
            
        if self.printStatements and flag:
            print(self.camera.getPos())
            
        return Task.cont

    def readMsgs(self, task):
        posY = self.posY
        msg_list = self.poller.poll(timeout=1)
        if msg_list:
            for sock, num in msg_list:
                msg = self.socket.recv()
                data = np.frombuffer(msg, dtype='int32', count=2)
                if (data[0] % 1000 == 0):
                    if self.printStatements: print(data)
                self.last_timestamp = data[0]
                posY = (data[1] * math.pi * 20.2 / 8192) % 240
        if posY != self.posY:
            self.posY = posY
            print(self.posY)

        return Task.cont

    def getPos(self):
        return self.posX, self.posY, self.posZ

    def setPos(self, x, y, z):
        self.posX = x
        self.posY = y
        self.posZ = z

app = App()
app.run()
