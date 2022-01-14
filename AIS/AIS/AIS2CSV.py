#
# Write a set of fields into a CSV file
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import logging
import queue
import os.path

class AIS2CSV(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "AIS2CSV", args)
        self.__queue = queue.Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="AIS2CSV related options")
        grp.add_argument("--csv", type=str, metavar="foo.csv",
                help="Filename to write CSV records to")
        grp.add_argument("--csvFields", type=str, action="append",
                help="Fields to write out, defaults to t,mmsi,x,y,sog,cog")

    @staticmethod
    def qUse(args:ArgumentParser) -> bool:
        if args.csv: return True

    def put(self, payload:dict) -> None:
        self.__queue.put(payload)

    def runIt(self): # Called on thread start
        q = self.__queue
        args = self.args
        fn = args.csv
        fields = ["t", "mmsi", "x", "y", "sog", "cog"]
        if args.csvFields:
            fields = args.csvFields
        logging.info("Starting %s <- %s", fn, fields)
        if not os.path.exists(fn): # Write the header
            with open(fn, "w") as fp:
                fp.write(",".join(fields) + "\n")

        while True:
            info = q.get()
            logging.debug("Recv: %s", info)
            values = []
            qWrite = False
            for fld in fields:
                if fld in info and info[fld]:
                    values.append(str(info[fld]))
                    qWrite = True
                else:
                    values.append("")
            if qWrite:
                logging.debug("Writing: %s %s -> %s", fn, fields, values)
                with open(fn, "a") as fp:
                    fp.write(",".join(values) + "\n")
            q.task_done()
