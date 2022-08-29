# Core imports
import zmq
import yaml
import pickle

import sys
import struct # Used to unpack timestamps and data from data stream
import setproctitle

from multiprocessing import Value
from multiprocessing import Queue
import multiprocessing

class Communicator:
    printStatements = True
    pos = 0

    def __init__(self, synced_state, synced_position, config_queue):

        self._synced_state = synced_state
        self._synced_position = synced_position
        self._config_queue = config_queue

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
        self._synced_state.value = -2

    def process_command_messages(self):
        """ process_command_messages(): receive ZMQ messages for data and configuration

            There are two sockets on which we listen for messages. The data_socket corresponds
            to a ZMQ PUB/SUB server which is streaming timestamp and position data. 
            The command_socket corresponds to a ZMQ server we start above that operates in the 
            DEALER/REP configuration.

            Here's a list of valid messages sent to the control server socket. All
            control messages are expected to be a pickled dictionary. Every control
            message has a "Command" field, and potentially other fields depending
            on the message. Here's a list of possible "Command"s:
                "QueryVersion": Reply is "Version:XXX;", where XXX is the version string
                "LoadModel": The maze YAML is taken from msg["MazeConfig"]. If this field
                    is missing, the default model is loaded (also if no MazeConfig is
                    given). If the maze is valid, the reply "ModelLoaded" is sent. Otherwise 
                    "ModelFailure" is sent, and the default is loaded.
                "UpdateDataServer": The address of the data server (IP/socket) is given in
                    msg["DataServerAddress"]. It's expected to be of the form
                    "tcp://host:port". If we successfully subscribe, "DataServerUpdated"
                    is sent. Otherwise "DataServerFailure".
                "Exit": This shuts down the VR system. Reply is "Exiting".
        """
        exit = False
        print("Starting communicator loop.")
        while not exit:
            if self._synced_state.value == -2:
                print("Goodbye!")
                exit = True
            msg_list = self.poller.poll(timeout=0.01)

            for sock, event in msg_list:
                if sock == self.data_socket:
                    msg = self.data_socket.recv()
                    self.last_timestamp, pos = struct.unpack('<Ld',msg)
                    if pos != self.pos:
                        self.pos = pos
                        self._synced_position.value = self.pos

                elif sock==self.command_socket:
                    print('Got a command message')
                    pickled_msg = self.command_socket.recv() # Command Socket Messages are pickled dictionaries
                    msg = pickle.loads(pickled_msg)
                    print("Message received: ", msg)
                    if msg['Command'] == 'QueryVersion':
                        self.command_socket.send("Version:{};".format(version).encode())
                    elif msg['Command'] == 'LoadModel':
                        self._config_queue.put(msg.get("MazeConfig", {}))
                        self._synced_state.value = 0
                        while (self._synced_state.value == 0):
                            pass
                        if self._synced_state.value == 1:
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
                        self._synced_state.value = -2
                        exit = True
                else:
                    msg = sock.recv()
                    print(msg)

        return


def start_commmunicator(synced_state, synced_position, config_queue):
    # signal.signal(signal.SIGINT, simple_handler)
    print(sys.stdout)
    multiprocessing.current_process().name = "python3 PyRenderMaze.Communicator"
    setproctitle.setproctitle(multiprocessing.current_process().name)

    print("Instantiating communicator.")

    communicator = Communicator(synced_state, synced_position, config_queue)

    try:
        communicator.process_command_messages()
    except KeyboardInterrupt:
        communicator.exit_fun() # Unclear whether this matters, but it makes things cleaner
    except Exception as e:
        print("Exception!!!", e)
