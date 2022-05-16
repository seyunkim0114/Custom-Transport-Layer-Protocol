# Written by S. Mevawala, modified by D. Gitzel

import logging

import channelsimulator
import utils
import sys
import socket

import hashlib
MAX_SEQUENCE_NUMBER = 999 
class Receiver(object):

    def __init__(self, inbound_port=50005, outbound_port=50006, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.rcvr_setup(timeout)
        self.simulator.sndr_setup(timeout)

    def receive(self):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoReceiver(Receiver):
    ACK_DATA = bytes(123)

    def __init__(self):
        super(BogoReceiver, self).__init__()

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        while True:
            try:
                 data = self.simulator.u_receive()  # receive data
                 self.logger.info("Got data from socket: {}".format(
                     data.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
	         sys.stdout.write(data)
                 self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()

class CustomReceiver(Receiver):
    def __init__(self, timeout=0.01):
        super(CustomReceiver, self).__init__()
        self.timeout = timeout
        self.simulator.sndr_socket.settimeout(self.timeout)
        self.simulator.rcvr_socket.settimeout(self.timeout)
    @staticmethod
    def _checksum(data):
        return hashlib.md5(data).hexdigest()

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        
        # initialize parameters
        num_duplicates = 0
        prev_ack_number = -1
        recent_ack = bytearray([0 for _ in range(33)])
        prev_checksum = bytearray([0 for _ in range(32)])

        while True:
            try:
                data = self.simulator.u_receive()
                if self.timeout > 0.1:
                    num_duplicates = 0 
                    self.timeout /= 2
                    self.simulator.rcvr_socket.settimeout(self.timeout)

                # check checksum of the received portion 
                if self._checksum(data[32:]) == data[0:32]:
                    ack_number = (data[64] + 1) % MAX_SEQUENCE_NUMBER
                    # check the sequence number is correct and previous checksum is correct
                    # previous checksum is also checked to deal with total packet losses
                    if (data[64] == prev_ack_number or prev_ack_number == -1) and prev_checksum == data[32:64]:
                        # update sequence number and checksum
                        sys.stdout.write(data[65:])
                        sys.stdout.flush()
                        prev_ack_number = ack_number
                        prev_checksum = data[0:32]

                        # create ack packet and send
                        data_to_send = bytearray([ack_number])
                        data_to_send = self._checksum(data_to_send) + data_to_send
                        recent_ack = data_to_send
                        self.simulator.u_send(data_to_send)
                        
                        continue
                # if corrupt, send the most recent intact packet
                self.simulator.u_send(recent_ack)
            # if timeout, send the most recent intact packet
            except socket.timeout:
                self.simulator.u_send(recent_ack)
                num_duplicates += 1
                if num_duplicates == 3:
                    num_duplicates = 0
                    self.timeout *= 2
                    if self.timeout > 10:
                        sys.exit()
                    self.simulator.rcvr_socket.settimeout(self.timeout)

    
if __name__ == "__main__":
    # test out BogoReceiver
    rcvr = CustomReceiver()
    rcvr.receive()
