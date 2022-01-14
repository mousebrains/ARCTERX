#! /usr/bin/env python3
#
# Listen to a UDP port or serial device for datagrams, 
# then forward copies to various consumers.
# The current consumers include:
#  - Write each raw datagram to a database.
#  - Split each datagram into raw NEMA sentences.
#    For each raw NEMA sentence the following are options:
#    -- Write each raw NEMA sentence to a database.
#    -- Integrity check the raw NEMA sentence and split it into fields.
#       For each valid NEMA sentence the following are options:
#       --- Write each split validated NEMA sentence to a database.
#       --- Build AIS payloads for multipart messages and then decrypt them.
#           For each decrypted AIS message the following are options:
#           ---- Write the full AIS payload to a database
#           ---- Write the decrypted AIS message in JSON format to a database.
#           ---- Send the decrypted AIS message in JSON format to host UDP ports.
#
# Possible special packages you might need to install:
#
# - libais
# - pyserial
# - sqlite3
# - psycopg3
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import sys
import queue
import time
import socket
import logging
import select
import serial

class Reader(Thread):
    ''' 
    Read from either a UDP port or a serial device.
    Read in the datagrams then forward them to a set of queues
    '''

    __Bytesizes = {
            5: serial.FIVEBITS,
            6: serial.SIXBITS,
            7: serial.SEVENBITS,
            8: serial.EIGHTBITS,
            }
    __Parity = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
            "Mark": serial.PARITY_MARK,
            "Spacer": serial.PARITY_SPACE,
            }
    __Stopbits = {
            1:   serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2:   serial.STOPBITS_TWO,
            }

    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "RDR", args)
        self.__queues = set() # Set of queues to send datagrams to

    @classmethod
    def addArgs(cls, parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        # NEMA sentences have a maximum size of 82 bytes, but there can
        # be multiple NEMA sentences in a datagram for multipart payloads.
        # so take a guess at 20 * NEMA+3
        grp.add_argument("--udpSize", type=int, default=20*85, help="Datagram size")
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument("--inputUDP", type=int, metavar="8982", help='UDP port to listen on')
        grp.add_argument("--inputSerial", type=str, metavar="/dev/tty-usb0", 
                help='Serial device to listen to')
        grp = parser.add_argument_group(description="Input serial related options")
        grp.add_argument("--serialBaudrate", type=int, default=115200, help="Serial port baudrate")
        grp.add_argument("--serialBytesize", type=int, default=8, 
                choices=sorted(cls.__Bytesizes), help="Serial port byte size")
        grp.add_argument("--serialParity", type=str, default="None", 
                choices=sorted(cls.__Parity), help="Serial port pairty")
        grp.add_argument("--serialStopbits", type=float, default=1, 
                choices=sorted(cls.__Stopbits), help="Serial port number of stop bits")

    def queue(self, q:queue.Queue) -> None:
        self.__queues.add(q)

    def runIt(self) -> None:
        '''Called on thread start '''
        self.__runUDP() if self.args.inputUDP else self.__runSerial()

    def __forward(self, t:float, addr:str, port:int, data:bytes) -> None:
        payload = (t, addr, port, data)
        logging.debug("Forwarding %s", payload)
        for q in self.__queues:
            q.put(payload)

    def __runUDP(self) -> None:
        args = self.args
        port = args.inputUDP
        sz = args.udpSize
        logging.info("Starting port=%s size=%s", port, sz)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logging.debug("Opened UDP socket")
            s.bind(('', port))
            logging.debug('Bound to port %s', port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(sz)
                t = time.time() # Timestamp just after the packet was received
                (ipAddr, port) = senderAddr
                self.__forward(t, ipAddr, port, data)

    def __runSerial(self) -> None:
        args = self.args
        device = args.inputSerial
        logging.info("Starting %s baud %s size %s parity %s stop %s", 
                device, args.serialBaudrate, args.serialBytesize, args.serialParity,
                args.serialStopbits)
        with serial.Serial(
                port=device,
                timeout=0, # Non-blocking
                baudrate=args.serialBaudrate,
                bytesize=self.__Bytesizes[args.serialBytesize],
                parity=self.__Parity[args.serialParity],
                stopbits=self.__Stopbits[args.serialStopbits],
                ) as s:
            logging.debug("Reading from %s", s)
            while s.is_open:
                (rlist, wlist, xlist) = select.select([s], [], [])
                t = time.time() # Time data became available
                try:
                    data = s.read(65536) # Read everything that is waiting
                except Exception as e:
                    dt = 1.1
                    logging.error("Exception while reading, waiting %s seconds", dt)
                    time.sleep(dt)
                    raise e
                self.__forward(t, None, None, data)
        raise Exception(f"EOF while reading from {device}") # Should not be reached
