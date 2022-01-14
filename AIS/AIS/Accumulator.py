#
# Build up AIS dictionary by updating from historical dictionaries.
# Then forward these dictionaries to consumers
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import logging
import queue
import time

class Accumulator(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "ACCUM", args)
        self.__qOutput = set()
        self.__qInput = queue.Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Accumulator related options")
        grp.add_argument("--accumAge", type=float,  default=3600,
                help="Trim the dictionary after this number of seconds")

    def qUse(self) -> bool:
        return len(self.__qOutput)

    def queue(self, q) -> None:
        self.__qOutput.add(q)

    def put(self, payload:dict) -> None:
        self.__qInput.put(payload)

    def send(self, payload:dict) -> None:
        for q in self.__qOutput:
            q.put(payload)

    def runIt(self): # Called on thread start
        q = self.__qInput
        args = self.args
        maxAge = args.accumAge if args.accumAge > 0 else None
        logging.info("Starting max age %s", maxAge)
        historical = {}
        ages = {}
        toDrop = {
                "ais_version", 
                "band_flag",  # Frequency band
                "commstate_cs_fill", "commstate_flag",
                "display_flag",
                "dsc_flag",
                "dte",
                "id",
                "keep_flag",
                "repeat_indicator",
                "received_stations",
                "slot_increment", "slot_number", "slot_offset", "slot_timeout", "slots_to_allocate",
                "spare", "spare2",
                "sync_state",
                "unit_flag",
                "utc_year", "utc_month", "utc_day", "utc_hour", "utc_min", "utc_spare",
                }
        while True:
            info = q.get().copy() # Make sure we have a local copy
            for key in toDrop:
                if key in info: # Drop flags I don't want to pass on
                    del info[key]
            for key in ["callsign", "destination", "name"]:
                if key in info:
                    info[key] = info[key].strip(" \t\n\r@")
            if maxAge and "mmsi" in info:
                mmsi = info["mmsi"]
                if mmsi not in historical:
                    historical[mmsi] = info
                else:
                    historical[mmsi].update(info)
                ages[mmsi] = time.time()
                info = historical[mmsi]
            self.send(info)
            q.task_done()
            if ages:
                t0 = time.time() - maxAge # Toss anything older than this
                for mmsi in list(ages.keys()): # list is to force a copy of all the keys
                    if ages[mmsi] <= t0: # Prune the unused entries
                        del historical[mmsi]
                        del ages[mmsi]
