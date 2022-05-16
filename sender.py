# Written by S. Mevawala, modified by D. Gitzel

import logging
import socket

import channelsimulator
import utils
import sys

import hashlib

MAX_SEQUENCE_NUMBER = 999

class Sender(object):

    def __init__(self, inbound_port=50006, outbound_port=50005, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.sndr_setup(timeout)
        self.simulator.rcvr_setup(timeout)

    def send(self, data):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoSender(Sender):

    def __init__(self):
        super(BogoSender, self).__init__()

    def send(self, data):
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        while True:
            try:
                self.simulator.u_send(data)  # send data
                ack = self.simulator.u_receive()  # receive ACK
                self.logger.info("Got ACK from socket: {}".format(
                    ack.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                break
            except socket.timeout:
                pass


class CustomSender(Sender):
    def __init__(self, max_size=959, timeout=0.01):
        super(CustomSender, self).__init__()
        self.max_size = max_size
        self.timeout = timeout
        # self.simulator.sndr_socket.settimeout(self.timeout)
        # self.simulator.rcvr_socket.settimeout(self.timeout)

    @staticmethod
    def _checksum(data):
        return hashlib.md5(data).hexdigest()

    def send(self, data):
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))

        start_num = 0
        resend = False
        data_to_send = None
        seq_number = 0
        prev_checksum = bytearray([0 for _ in range(32)])
        # 0 ~ 32: checksum
        # 32 ~ 64: previous checksum
        # 64 : seq_number
        # 65 ~ : data

        while True:
            try:
                if not resend:
                    # if not resend, send a new packet
                    # include sequence number, checksum, and data
                    data_to_send = bytearray([seq_number])
                    seq_number = (seq_number + 1) % MAX_SEQUENCE_NUMBER
                    data_to_send += data[start_num:start_num + self.max_size]
                    data_to_send = prev_checksum + data_to_send
                    checksum = self._checksum(data_to_send)
                    data_to_send = checksum + data_to_send
                    prev_checksum = checksum
                    start_num += self.max_size
                    self.simulator.u_send(data_to_send)
                else:
                    # if resend, send the previous packet
                    self.simulator.u_send(data_to_send)
                # receive ack
                ack = self.simulator.u_receive()
                # check checksum of ack
                if self._checksum(ack[32:]) == ack[0:32]:
                    if ack[32] == seq_number:
                        if start_num >= len(data):
                            break
                        resend = False
                    else:
                        resend = True
                else:
                    resend = True
            except socket.timeout:
                resend = True
            

if __name__ == "__main__":
    # test out BogoSender
    DATA = bytearray(sys.stdin.read())
    sndr = CustomSender()
    sndr.send(DATA)
