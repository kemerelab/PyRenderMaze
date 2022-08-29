# Core imports
import pyglet
from pyglet.window import key
from ctypes import c_int
import yaml

# Used to get IP address
from subprocess import check_output
import platform
import socket

# Local code
from render_model import Model

version = '1.1'
DISPLAY_FPS = True

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

        if DISPLAY_FPS:
            self.fps_display = pyglet.window.FPSDisplay(self)

        self.mouseHeight = display_config.get('MouseEyeHeight', 3) # The mouse's eye position relative to the top of the wheel
        self.cameraHeight = 0 + self.mouseHeight # The height of the eye/camera relative to 0

        self.camera_view_angle = display_config.get('ViewAngle', 0) # default to straight ahead (this is actually 90 degrees!)

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

    def on_key_press(self, KEY, _MOD):
        if KEY == key.ESCAPE:
            self.has_exit = True

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

        # Model
        pyglet.gl.glMatrixMode(pyglet.gl.GL_MODELVIEW)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glPushMatrix()
        pyglet.gl.glRotatef(-90,1,0,0) # Our model has Z pointing up
        pyglet.gl.glRotatef(-self.camera_view_angle,0,0,1) # Adjust for camera view
        pyglet.gl.glTranslatef(0, self._synced_position.value, 0)

        self.model.draw()

        pyglet.gl.glPopMatrix(  )

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

        if (window):
            window.dispatch_events() # Needed to catch 'ESC' key to exit
            window.dispatch_event('on_draw')
            window.flip()

    communicator_process.join()
