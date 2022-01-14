#
# Send decoded AIS messages as a JSON message to UDP ports
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import logging
import queue
import socket
import re
import json
import time

class AIS2UDP(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "AIS2UDP", args)
        self.__queue = queue.Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="AIS2UDP related options")
        grp.add_argument("--ais2udp", type=str, action="append",
                help="IP:port or hostname:port to send JSON messages to")

    @staticmethod
    def qUse(args:ArgumentParser) -> bool:
        if args.ais2udp: return True

    def put(self, payload:dict) -> None:
        self.__queue.put(payload)

    def __mkTargets(self) -> set:
        targets = set()
        for item in self.args.ais2udp:
            matches = re.match(r"^(.*):(\d+)$", item)
            if matches is None:
                raise Exception(f"Invalid formatted --ais2udp option, {item}")
            host = matches[1]
            port = int(matches[2])
            try:
                info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
                targets.add(info[0][-1]) # (addr,port) pair
            except Exception as e:
                logging.error("Unable to resolve %s", item)
                raise e
        return targets

    def runIt(self): # Called on thread start
        q = self.__queue
        args = self.args
        targets = self.__mkTargets()
        logging.info("Starting %s", targets)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            payload = q.get()
            msg = json.dumps(payload)
            logging.debug("Recv: %s", msg)
            for tgt in targets:
                logging.debug("Sending to %s", tgt)
                sock.sendto(bytes(msg, "utf-8"), tgt)
            q.task_done()
