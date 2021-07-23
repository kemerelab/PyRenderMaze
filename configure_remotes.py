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




def send_command(msg, client_IPs, success_reply):
    context = zmq.Context()
    for ip in client_IPs:
        SERVER_ENDPOINT = "tcp://{}:8557".format(ip)
        client = context.socket(zmq.REQ)
        client.connect(SERVER_ENDPOINT)
        print('Sending to {}'.format(ip))
        client.send(pickle.dumps(msg))

        retries_left = REQUEST_RETRIES
        while True:
            if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                reply = client.recv()
                print(reply)
                if reply == success_reply:
                    break
                else:
                    continue

            retries_left -= 1
            # Socket is confused. Close and remove it.
            client.setsockopt(zmq.LINGER, 0)
            client.close()
            if retries_left == 0:
                print("Server {} seems to be offline, abandoning".format(ip))
                break

            print("+")
            # Create new connection
            client = context.socket(zmq.REQ)
            client.connect(SERVER_ENDPOINT)
            client.send(pickle.dumps(msg))

        client.close()


client_IPs = ['10.129.151.177', '10.129.151.185', '10.129.151.166']
msg = {'Command':'LoadModel', 'MazeConfig':maze_config}
success_reply = b'ModelLoaded'

send_command(msg, client_IPs, success_reply)


msg = {'Command':'UpdateDataServer', 'DataServerAddress':"tcp://10.129.151.168:8556"}
success_reply = b'DataServerUpdated'

send_command(msg, client_IPs, success_reply)

