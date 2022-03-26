#
# Decode NEMA sentences and then decrypt the AIS payload
# forward decoded messages to a set of queues
#
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import logging
import queue
import ais
import re
import time
from datetime import datetime

class Decrypter(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "Decrypt", args)
        self.__qInput = queue.Queue()
        self.__qOutput = set()
        self.__reNEMA = re.compile(b".*!(AIVD[MO],\d+,\d+,\d?,\w?,.*,[0-5])[*]([0-9A-Za-z]{2})\s*")
        self.__reIgnore = re.compile(b".*[$](PFEC|AI(ALR|ABK|TXT)),")
        self.__partials = {} # For accumulating multipart messages

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        pass # I don't have any options

    def qUse(self) -> bool:
        return len(self.__qOutput) # Somebody for me to send stuff to

    def queue(self, q:queue.Queue) -> None:
        self.__qOutput.add(q)

    def put(self, payload:tuple[float, str, int, bytes]) -> None:
        self.__qInput.put(payload)

    def __forward(self, payload:dict) -> None:
        logging.debug("Forwarding%s", payload)
        for q in self.__qOutput:
            q.put(payload)

    def runIt(self): # Called on thread start
        args = self.args
        q = self.__qInput
        logging.info("Starting %s", len(self.__qOutput))
        while True:
            (t, addr, port, data) = q.get()
            logging.debug("Received %s %s %s %s", t, addr, port, data)
            # there might be multiple messages in a single datagram
            for sentence in data.strip().split(b"\n"):
                fields = self.__denema(sentence)
                if fields is None: # Not a valid sentence, so skip it
                    continue
                fields = self.__accumulate(t, fields)
                if fields is None: continue # Partial payload, so wait for more

                info = ais.decode(fields[5], fields[6])
                if info is None: continue
                if "x" in info and abs(info["x"]) > 180: continue # Skip longitudes that are >180
                if "y" in info and abs(info["y"]) > 90: continue # Skip latitudes that are >90
                # Don't deal with timestamp, utc_min, and utc_hour, just use the time received
                info["t"] = t
                info["timestamp"] = \
                        datetime \
                        .utcfromtimestamp(t) \
                        .strftime("%Y-%m-%d %H:%M:%S.%f")
                self.__forward(info)
            q.task_done()

    def __denema(self, msg:bytes) -> list:
        # Check the NEMA sentence structure is good, then take the message apart into fields
        # field[0] -> !AIVD[MO]
        # field[1] -> Total number of fragments, for single part messages, this is 1
        # field[2] -> Fragment number, for single part messages this is 1
        # field[3] -> multipart identification count
        # field[4] -> Radio channel, A or 1 -> 161.975MHz B or 2 -> 162.025MHz
        # field[5] -> data payload
        # field[6] -> number of fill bits
        matches = self.__reNEMA.match(msg)
        if not matches:
            if not self.__reIgnore.match(msg): # Ignore these messages
                logging.warning("Unrecognized senentce %s", msg)
            return None

        chksum = 0
        for c in matches[1]: chksum ^= c

        sentChkSum = int(str(matches[2], "UTF-8"), 16)
        if chksum != sentChkSum:
            logging.warning("Bad checksum, %s != %s, %s", chksum, sentChkSum, msg)
            return None

        fields = str(matches[1], "UTF-8").split(",")
        if len(fields) != 7: 
            logging.warning("There weren't 7 fields in %s", msg)
            return None
        fields[1] = int(fields[1]) # Number of fragments
        fields[2] = int(fields[2]) # Fragment number
        fields[6] = int(fields[6]) # Fill bits
        return fields

    def __agePartials(self, t:float) -> None: # Maximum age to avoid memory leaks
        info = self.__partials # Partial message information

        toDrop = set()
        for ident in info:
            tAge = info[ident]["age"]
            # Give 1 minute for partial messages to accumulate
            if tAge > (t - 60): continue
            logging.warning("Aged out %s", ident)
            toDrop.add(ident)

        for ident in toDrop:
            del info[ident]

    def __accumulate(self, t, fields:list) -> bool:
        if fields[1] == 1: return fields # No need to Accumulate

        info = self.__partials # previous information on partial messages
        ident = fields[3] # Partial message identifier

        if ident not in info:  # First time this ident has been seen
            info[ident] = {"payloads": {}, "fillBits": 0, "age": t}

        info[ident]["payloads"][fields[2]] = fields[5] # Accumulate payloads

        if fields[1] == fields[2]: # Number of fill bits on last segment
            info[ident]["fillBits"] = fields[6]

        if len(info[ident]["payloads"]) != fields[1]: # Need to accumulate some more
            self.__agePartials(t) # Avoid memory leaks
            return None

        # Build
        payload = ""
        for key in sorted(info[ident]["payloads"]): # Assemble parts in correct order
            payload += info[ident]["payloads"][key]

        fields[5] = payload
        fields[6] = info[ident]["fillBits"]
        del info[ident]
        return fields
