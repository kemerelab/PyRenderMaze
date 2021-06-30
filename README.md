# PyRenderMaze

(C) 2021 by Jiwon Kim and Caleb Kemere

This program is designed to run in concert with the [https://github.com/kemerelab/TreadmillIO] project, which includes
a hardware interface to a cylindrical treadmill as well as real-time virtual-position-based control of dynamic auditory
stimuli. PyRenderMaze is intended to run as a separate process, or indeed, even on separate computers. It is lightweight
enough that a Raspberry Pi 4B can render full-screen video at 60 FPS. Position data is received using a ZeroMQ PUB/SUB 
network interface. Virtual maze configuration is controlled by a YAML file (see `example-mazes/example1.yaml`).


To test,
+ run program after cloning this repo with `/usr/bin/python3 main.py`
+ you can use the up and down arrow keys to control position, or
+ you can set the `playerMode = False`, and run `send_position_stream.py` to simulate actual mouse movement data

TODO:
+ Implement receiving (and sending) maze configuration over a ZeroMQ connection (or other approach).
+ Maze configuration should also specify what the camera view is (i.e., left, right, or straight ahead)!
+ The virtual track length is not (and is not intended to be) infinite. However, it seems odd for the mouse to see
    the end of the maze as just an open space. We need to figure out that best way to avoid a cliff. Perhaps this should 
    be to replicate the maze once, and add fog at the end of the first (main) maze. This would make it look like there's
    something there. Or maybe we should just have a vertical "The End" wall. 
+ We should decide whether we want to have distal cues to give a motion signal independent of track location.
+ On the Raspberry Pi (running without a window manager), when we run fullscreen, we lose keyboard focus. This makes testing difficult.
