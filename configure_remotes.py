import zmq
import yaml
import pickle


maze_config_filename = "example-mazes/example_teleport.yaml"
with open(maze_config_filename, "r") as stream:
    maze_config = yaml.safe_load(stream)


#
#  Lazy Pirate client
#  Use zmq_poll to do a safe request-reply
#  To run, start lpserver and then randomly kill/restart it
#
#   Author: Daniel Lundin <dln(at)eintr(dot)org>
#
import itertools
import sys

REQUEST_TIMEOUT = 2500
REQUEST_RETRIES = 3
SERVER_ENDPOINT = "tcp://localhost:8557"

context = zmq.Context()


msg = {'Command':'NewModel', 'MazeConfig':maze_config}

client_IPs = ['10.129.151.177', '10.129.151.185', '10.129.151.166']
client = context.socket(zmq.REQ)

for ip in client_IPs:
    SERVER_ENDPOINT = "tcp://{}:8557".format(ip)
    client.connect(SERVER_ENDPOINT)
    print('Sending maze')
    client.send(msg)  # actual message

    retries_left = REQUEST_RETRIES
    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            if reply == b'NewModelSuccess':
                print(reply)
                break
            else:
                continue

        retries_left -= 1
        print("No response from server")
        # Socket is confused. Close and remove it.
        client.setsockopt(zmq.LINGER, 0)
        client.close()
        if retries_left == 0:
            print("Server seems to be offline, abandoning")
            break

        print("Reconnecting to server…")
        # Create new connection
        client = context.socket(zmq.REQ)
        client.connect(SERVER_ENDPOINT)
        client.send(pickle.dumps(msg))

    client.close()

