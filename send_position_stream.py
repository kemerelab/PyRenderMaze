import zmq
import random
import sys
import time
import numpy as np

import struct

port = "8556"
if len(sys.argv) > 1:
    port =  sys.argv[1]
    int(port)

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:%s" % port)

data = np.load('ExampleData.npy')
idx = 10000
k = 0
# print(data.dtype, data.shape)

while True:
    pos = (data[idx, 1] * np.pi * 20.2 / 8192) % 240
    socket.send(struct.pack('<Ld', int(data[idx,0]), pos))
    idx = idx + 1
    if idx >= data.shape[0]:
        idx = 0
    time.sleep(0.002)
