import zmq
import random
import sys
import time
import numpy as np

port = "8557"
if len(sys.argv) > 1:
    port =  sys.argv[1]
    int(port)

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:%s" % port)

print('Sending')
while True:
    socket.send(b'HelloWorld')
    time.sleep(1)