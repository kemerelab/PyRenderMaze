# Core imports
from panda3d.core import *
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
# Task managers
from direct.task.Task import Task
# GUI
from panda3d.core import loadPrcFileData

# Utilities
import zmq
import numpy as np
import math
import yaml
import pickle
import datetime
import csv

import sys
from subprocess import check_output


import struct

# Local code
from ParametricShapes import makeCylinder, makePlane


# Read YAML file
with open("display_config.yaml", 'r') as stream:
    display_config = yaml.safe_load(stream)

# Globally change window title name
windowTitle = "PyRenderMaze"
loadPrcFileData("", f"window-title {windowTitle}")

w, h = display_config.get("WindowSize", (640, 480))
loadPrcFileData("", "win-size {} {}".format(w, h))
loadPrcFileData("", "fullscreen true") # causes some sort of bug where run loop doesn't start in Ubuntu
# loadPrcFileData("", "auto-flip 1") # try speed up
# loadPrcFileData("", "sync-video 0") # try speed up
# loadPrcFileData("", "back-buffers 0") # try speed up - this causes run loop not to start?


maze_config_filename = "example-mazes/example_teleport.yaml"
with open(maze_config_filename, "r") as stream:
    maze_config = yaml.safe_load(stream)

class App(ShowBase):
    printStatements = True
    IP_address_text = None # Will use to display IP address
    posX = 0.0
    posY = 0.0
    posZ = 0.0

    do_frame_synchronization = False # Make this true to enable a task which flashes squares per frame

    # In order to provide motion cues, we define a large cylinder to hold a background
    # texture. The goal is that the wall of this cylinder is far enough from the mouse,
    # and the texture it carries is complex enough that they get a dynamic motion cue 
    # but not a precise a spatial cue.
    roomSize = 750

    # Use cm as units
    # trackWidth = 15 # This is actually how wide our running wheel is

    # The trackLength corresponds to a virtual thing. The height of the track
    #  should correspond to the physical height of the wheel because the running
    #  behavior is supposed to correspond with running on the virtual track.
    trackVPos = 0 # 0 means the track is centered on the "virtual center" of 
                    # the screen. We'll adjust to offset the monitor later.

    def __init__(self, display_config={}, maze_config={}):
        ShowBase.__init__(self)
        
        # For the proper VR perspective, we need to define the mouse's eye position.
        #   Because we are only using 2D displays, we'll assume they are a cyclops.
        #   Our "cameras" are just different views from the eye of the world.
        self.mouseHeight = display_config.get('MouseEyeHeight', 3) # The mouse's eye position relative to the top of the wheel
        self.cameraHeight = self.trackVPos + self.mouseHeight # The height of the eye/camera relative to 0

        ### Support multiple views of the maze 
        # There are two ways that multiple views can be supported: (1) With different display regions within the
        # same large potentially multi-monitor-spanning window, or (2) With multiple windows, where each X screen
        # gets its own window. X on the Pi defaults to having one big screen set across multiple monitors, and ironically
        # it proves difficult to configure it to instantiate multiple screens (back in the day it was hard to convice X to
        # span windows!). Thus only option (1) is currently supported. For hints towards implementing (2), look at commit
        # d2ee4957bf81f6d2a24169a823065599df1d5083 and earlier.
        self.n_views = display_config.get('NViews', 1) # default to one view
        self.camera_view_angles = display_config.get('ViewAngles', [0]) # default to straight ahead
        if len(self.camera_view_angles) != self.n_views:
            raise(ValueError('Must specify one camera view angle for each view.'))

        self.display_regions = display_config.get('DisplayRegions', [[0,1,0,1]]) # default to full screen
        if len(self.display_regions) != self.n_views:
            raise(ValueError('Must specify one display region for each view.'))

        # Physical geometry and placement of the screen(s)
        widths_and_heights = display_config.get('MonitorSizes', [[51, 29]]*self.n_views) # default to a big, 51x29 cm screen
        if len(widths_and_heights) != self.n_views:
            raise(ValueError('Must specify physical sizes of each display.'))
        distances = display_config.get('MonitorDistances', [24]*self.n_views) # default to 24 cm distance
        if len(distances) != self.n_views:
            raise(ValueError('Must specify distance from eye to each display.'))
        self.screen_h_v_offsets = display_config.get('MonitorOffsets', [[0,0]]*self.n_views) # default to no display center offset

        # Initialize dimensions corresponding to each view
        self.screen_width = []
        self.fov_h_v = []
        for n in range(self.n_views):
            width, height = widths_and_heights[n]
            self.screen_width.append(width)
            # Let's describe the shape of the screen in terms of the field of view angles.
            #   (This requires a bit of geometry!)
            fov_h = math.atan2(width/2, distances[n])*2 / math.pi * 180
            fov_v = math.atan2(height/2, distances[n])*2 / math.pi * 180
            self.fov_h_v.append([fov_h, fov_v])

        self.cameras = []
        # Set up view(s)
        for n in range(self.n_views):
            if (n > 0):
                # The display region is the bread and butter of the view.
                new_dr = base.win.makeDisplayRegion(*self.display_regions[n])
                print(self.display_regions[n])
                new_dr.setClearColor(VBase4(0, 0, 0, 1)) # clear to black
                new_dr.setClearColorActive(True) # clear every frame
                new_dr.setClearDepthActive(True) # clear the z-buffer as wll

                # The camera the thing that looks at our model and sends data to the display region.
                #   For each view (monitor), we can have a different camera looking from a different angle/etc.
                new_cam = Camera('cam{}'.format(n))
                current_cam_node = self.render.attachNewNode(new_cam)
                new_dr.setCamera(current_cam_node)
                # self.camera.setHpr(90, 0, 0)

                self.cameras.append(current_cam_node)
            else:
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
        self.init_track(maze_config)

        base.setBackgroundColor(0, 0, 0)  # set the background color to black

        # ZMQ server connection for commands. 
        # We use a DEALER/REP architecture for reliability.
        command_socket_port = "8557"
        # Socket to talk to server
        context = zmq.Context()
        self.command_socket = context.socket(zmq.REP)
        self.command_socket.bind("tcp://*:%s" % command_socket_port)

        self.poller = zmq.Poller()
        self.poller.register(self.command_socket, zmq.POLLIN)

        self.data_socket = None # This will be configured by remote control

        self.last_timestamp = 0
        self.taskMgr.add(self.readMsgs, "ReadZMQMessages", sort=1)

        self.accept('escape', self.exit_fun)

        # -----------------------------------------
        # Instrumentation code
        if self.do_frame_synchronization:
            # Frame synchronization (if desired) is done with two squares in the bottom corners.
            # One will flash per frame, and the other in a less periodic pattern. We write the most
            #   recent position data and the square states to disk for post-hoc comparison with the
            #   recorded data.
            sync_square_width = 0.05
            left_square = makePlane(-1 + sync_square_width/2, 0, -1 + sync_square_width/2, 
                sync_square_width, sync_square_width, facing='front',color=[0, 0, 0])
            right_square = makePlane(1 - sync_square_width/2, 0, -1 + sync_square_width/2, 
                sync_square_width, sync_square_width, facing='front',color=[0, 0, 0])
            left_square_node = GeomNode("LeftSyncSquare")
            left_square_node.addGeom(left_square)
            right_square_node = GeomNode("RighteSyncSquare")
            right_square_node.addGeom(right_square)
            self.left_sync_square = render2d.attachNewNode(left_square_node)
            self.right_sync_square = render2d.attachNewNode(right_square_node)

            self.sync_state = 0
            self.taskMgr.add(self.syncSquares, "FlashSyncSquares", sort=2) # execute after the readMsgs function
            now = datetime.datetime.now()
            filename = '{}{}.csv'.format('ExperimentLog', now.strftime("%Y-%m-%d_%H%M"))
            self.sync_log_file = open(filename, 'w', newline='')
            self.sync_log_writer = csv.writer(self.sync_log_file)


        base.setFrameRateMeter(True) # Display frame rate


    def remove_model(self):
        if self.maze_geometry_root:
            self.maze_geometry_root.removeNode()
            self.maze_geometry_root = None
        if self.IP_address_text:
            self.IP_address_text.destroy()
            self.IP_address_text = None
    
    def draw_model(self, maze_config):
        if self.maze_geometry_root:
            self.remove_model()
        success = False
        try:
            self.init_track(maze_config)
            success = True
        except:
            self.init_track({})

        return success

    def init_track(self, trackConfig):
        trackFeatures = trackConfig.get('TrackFeatures', None)

        self.trackLength = trackConfig.get('TrackLength', 240)
        self.wallHeight = trackConfig.get('WallHeight', 20)
        self.wallDistance = trackConfig.get('WallDistance', 24) # Ideally this is equal to the screen distances on the sides

        testTexture = loader.loadTexture("textures/numbers.png")
        checkerboard = loader.loadTexture("textures/checkerboard.png")
        noise = loader.loadTexture("textures/whitenoise.png")

        maze_root_node = GeomNode("maze_root_node")
        self.maze_geometry_root = self.render.attachNewNode(maze_root_node)

        room_wall_cylinder = makeCylinder(0, self.trackLength/2, -5*self.roomSize/2, self.roomSize, 10*self.roomSize, 
                                          facing="inward", texHScaling=12, texVScaling=12, color=[1.0, 1.0, 1.0])

        if trackConfig.get('EnableBackgroundTexture', True):
            snode = GeomNode('room_walls')
            snode.addGeom(room_wall_cylinder)
            room_walls = self.maze_geometry_root.attachNewNode(snode)
            room_walls.setTexture(noise)
            # walls_node.setTwoSided(True)

        # trackLength, trackWidth, wallDistance all could be parametric, but I think most likely these wouldn't need to change often
        track_parent = self.maze_geometry_root.attachNewNode(GeomNode('MazeParent'))

        # if self.printStatements:
        #     print("i: -1",  "startPoint: ",  points[0]-100, "endPoint: ", 250)

        if trackFeatures:
            for featureName, feature in trackFeatures.items():
                color = feature.get('Color', [0.5, 0.5, 0.5])
                texScale = feature.get('TextureScaling', 1.0)
                snode = GeomNode(featureName)

                if feature.get('Type') == 'Wall':
                    length = feature['Bounds'][1] - feature['Bounds'][0]
                    center = (feature['Bounds'][1] + feature['Bounds'][0])/2
                    x_offset = feature.get('XOffset', 0)
                    right = makePlane(self.wallDistance + x_offset, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="left", color=color,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                    snode.addGeom(right)
                    left = makePlane(-self.wallDistance - x_offset, center, self.trackVPos + self.wallHeight/2, 
                                                    length, self.wallHeight, facing="right", color=color,
                                                    texHScaling=length/self.wallHeight*texScale, texVScaling=texScale)
                    snode.addGeom(left)

                elif feature.get('Type') == 'Plane':
                    width = feature.get('Width')
                    height = feature.get('Height')
                    plane = makePlane(feature.get('XPos', 0), feature.get('YPos', 0), feature.get('ZPos', 0), 
                                                    width, feature.get('Height'), facing=feature.get('Facing'),
                                                    color=color,texHScaling=width/height*texScale, texVScaling=texScale)
                    snode.addGeom(plane)

                elif feature.get('Type') == 'WallCylinder':
                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)
                    if feature.get('XLocation', 'Both') in ['Left', 'Both']:
                        cylinder = makeCylinder(-self.wallDistance, feature.get('YLocation'), 
                                                            self.trackVPos, r, h, color=color, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h)
                        snode.addGeom(cylinder)
                    
                    if feature.get('XLocation', 'Both') in ['Right', 'Both']:
                        cylinder = makeCylinder(self.wallDistance, feature.get('YPos'), 
                                                            self.trackVPos, r, h, color=color, texHScaling=texScale, 
                                                            texVScaling=texScale * (math.pi * 2 * r) / h)
                        snode.addGeom(cylinder)

                elif feature.get('Type') == 'Cylinder':
                    h = feature.get('Height',self.wallHeight*3)
                    r = feature.get('Radius',5)
                    cylinder = makeCylinder(feature.get('XPos'), feature.get('YPos'), 
                                                        self.trackVPos, r, h, facing=feature.get('Facing','outward'),
                                                        color=color, texHScaling=texScale, 
                                                        texVScaling=texScale * (math.pi * 2 * r) / h)
                    snode.addGeom(cylinder)

                if feature.get('DuplicateForward', True):
                    node = track_parent.attachNewNode(snode)
                else:
                    node = self.maze_geometry_root.attachNewNode(snode)

                if 'Texture' in feature:
                    tex = loader.loadTexture(feature['Texture'])
                    node.setTexture(tex)
                    if 'RotateTexture' in feature:
                        node.setTexRotate(TextureStage.getDefault(), feature['RotateTexture'])

            # BIG TODO - add in sgments of default color featureless wall between the labeled sections.
            #          - we can do this in the YAML file, but it seems cleaner to have it done automatically.
            #          - need a function to (1) check that bounds never overlap, and (2) find residual
            #            segment boundaries


        else:
            # Default walls - light gray. Height could be parametric. These will fill any unspecified gaps
            snode = GeomNode('default_walls')
            right = makePlane(self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="left", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)
            snode.addGeom(right)
            left = makePlane(-self.wallDistance, self.trackLength/2, self.trackVPos + self.wallHeight/2, 
                                            self.trackLength, self.wallHeight, facing="right", color=[0.5, 0.5, 0.5],
                                            texHScaling=self.trackLength/self.wallHeight)
            snode.addGeom(left)
            walls = track_parent.attachNewNode(snode)


            if not self.IP_address_text:
                # Render IP address by default
                IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
                while len(IP) < 7:
                    IP = check_output(['hostname', '-I']).decode("utf-8","ignore")
                self.IP_address_text = OnscreenText(text=IP, pos=(0, 0.75), scale=0.1, align=TextNode.ACenter, fg=[1, 0, 0, 1])


        # Make a copy of the walls and floor at the end of the maze. This makes it look like it goes on further
        node = GeomNode('track_copy')
        maze_geometry_copy_parent = self.maze_geometry_root.attachNewNode(node)
        second_maze = track_parent.copyTo(maze_geometry_copy_parent)
        maze_geometry_copy_parent.setPos(0, self.trackLength, 0)

        return self.maze_geometry_root


    def update_data_server(self, IP):
        # Initialize (or Re-initialize) ZMQ connection to position data server
        if self.data_socket:
            self.poller.unregister(self.data_socket)
            self.data_socket.close()

        success = False
        if IP:
            context = zmq.Context()
            self.data_socket = context.socket(zmq.SUB)
            try:
                self.data_socket.connect(IP)
                success = True
                self.data_socket.setsockopt(zmq.SUBSCRIBE, b"")
                self.poller.register(self.data_socket, zmq.POLLIN)
            except:
                print('Failed to connect to IP {}'.format(IP))
        
        #     data_socket_port = "8556"
        #     self.data_socket.connect ("tcp://localhost:%s" % data_socket_port)
        return success

    def exit_fun(self):
        print('Exit called')
        self.sync_log_file.close()
        sys.exit()

    def readMsgs(self, task):
        posY = self.posY
        msg_list = self.poller.poll(timeout=0.01)
        while msg_list:
            for sock, event in msg_list:
                if sock == self.data_socket:
                    msg = self.data_socket.recv()
                    self.last_timestamp, posY = struct.unpack('<Ld',msg)
                    if posY != self.posY:
                        self.posY = posY
                        # print(self.posY)
                elif sock==self.command_socket:
                    print('Got a command message')
                    pickled_msg = self.command_socket.recv() # Command Socket Messages are pickled dictionaries
                    msg = pickle.loads(pickled_msg)
                    print("Message received: ", msg)
                    if msg['Command'] == 'LoadModel':
                        success = self.draw_model(msg.get("MazeConfig", {}))
                        if success:
                            self.command_socket.send(b"ModelLoaded")
                        else:
                            self.command_socket.send(b"ModelFailure")
                    elif msg['Command'] == 'UpdateDataServer':
                        success = self.update_data_server(msg.get("DataServerAddress", None))
                        if success:
                            self.command_socket.send(b"DataServerUpdated")
                        else:
                            self.command_socket.send(b"DataServerFailure")

                    elif msg['Command'] == 'Exit':
                        self.command_socket.send(b"Exiting")
                        self.exit_fun()
                else:
                    msg = sock.recv()
                    print(msg)
            msg_list = self.poller.poll(timeout=0) # it seems like the whole point of poller
                                                   # should be to catch all of these, but...


        for c in self.cameras:
            c.setPos(self.posX, self.posY, self.posZ + self.cameraHeight)

        return Task.cont

    def getPos(self):
        return self.posX, self.posY, self.posZ

    def setPos(self, x, y, z):
        self.posX = x
        self.posY = y
        self.posZ = z

    def syncSquares(self, task):
        # TODO: update right square pattern with gold code: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.max_len_seq.html
        self.sync_state += 1
        if (self.sync_state % 2) == 1:
            self.left_sync_square.setColor(1, 1, 1, 1) # white on odd
        else:
            self.left_sync_square.setColor(0, 0, 0, 1) # black on even

        if (self.sync_state % 8) < 4:
            self.right_sync_square.setColor(1, 1, 1, 1) # white on first 4
        else:
            self.right_sync_square.setColor(0, 0, 0, 1) # black on rest

        self.sync_log_writer.writerow([self.last_timestamp, self.posY, self.sync_state])

        return Task.cont

app = App(display_config=display_config)
# app = App(display_config=display_config, maze_config=maze_config)

app.run()
