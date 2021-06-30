import zmq
import random
import sys
import time
import numpy as np

port = "8556"
if len(sys.argv) > 1:
    port =  sys.argv[1]
    int(port)

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:%s" % port)

data = np.load('ExampleData.npy')
idx = 0
k = 0
# print(data.dtype, data.shape)

while True:
    k = (k + 1)
    if k == 100:
        socket.send(data[idx,:].tobytes())
        k  = 0
    idx = idx + 1
    if idx >= data.shape[0]:
        idx = 0

    if (data[idx,0] % 1000 == 0):
        pos = (data[idx, 1] * np.pi * 20.2 / 8192) % 240
        # print(data[idx,:], pos)
    time.sleep(0.002)
