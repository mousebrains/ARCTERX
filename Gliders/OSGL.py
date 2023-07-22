#! /usr/bin/env python3
#
# Monitor glider console from SFMC and save position information into PostgreSQL
# Then to a CSV file for the ship
#
# May-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils import Logger
import logging
from TPWUtils.Thread import Thread
from queue import Queue
import datetime
import re
import math
import json
import psycopg
import subprocess
import os.path

class DBupdate(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "DB", args)
        self.__queue = Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser):
        grp = parser.add_argument_group(description="DB related options")
        grp.add_argument("--group", type=str, default="AUV", help="Device group")
        grp.add_argument("--db", type=str, default="arcterx", help="DB name")
        grp.add_argument("--table", type=str, default="glider",  help="DB table to store data in")
    
    def put(self, name:str, t:datetime.datetime, lat:float, lon:float) -> None:
        if name and t and lat and lon:
            self.__queue.put((name, t, lat, lon))

    def runIt(self) -> None: # Called on thread start
        q = self.__queue
        args = self.args

        sql = f"INSERT INTO {args.table} (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
        sql+= " ON CONFLICT DO NOTHING;"

        logging.info("Starting %s", sql)
        while True:
            (name, t, lat, lon) = q.get()
            q.task_done()
            fields = (args.group, name, t, lat, lon)
            logging.info("fields %s", fields)
            with psycopg.connect(f"dbname={args.db}") as db:
                cur = db.cursor();
                cur.execute("BEGIN TRANSACTION;")
                cur.execute(sql, fields)
                db.commit()

class Listener(Thread):
    def __init__(self, args:ArgumentParser, name:str, dialog:DBupdate) -> None:
        Thread.__init__(self, name, args)
        self.__dialog = dialog
        self.__time = None

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument("--apiListen", action="store_true",
                         help="Should the API be used to read the dialog?")
        grp.add_argument("--apiInput", type=str, metavar="filename",
                         help="Name of API file to read")
        grp.add_argument("--dialogInput", type=str, action='append', metavar="filename",
                         help="Name of dialog file to read")
        grp = parser.add_argument_group(description="API options")
        grp.add_argument("--nodeCommand", type=str, default="/usr/bin/node",
                         help="Node command path")
        grp.add_argument("--apiDir", type=str, metavar="dir",
                         default="~/sfmc-rest-programs",
                         help="Where SFMC's API JavaScripts are located")
        grp.add_argument("--apiCopy", type=str, metavar="filename",
                         help="Write out a copy of what is read from the API")

    def runIt(self) -> None: # Called on thread start
        logging.info("Starting")
        if args.apiListen:
            self.__apiListen()
        elif args.apiInput:
            self.__apiInput()
        else:
            self.__dialogInput()
    
    def __apiListen(self):
        args = self.args
        args.nodeCommand = os.path.abspath(os.path.expanduser(args.nodeCommand))
        args.apiDir = os.path.abspath(os.path.expanduser(args.apiDir))

        cmd = (args.nodeCommand, "output_glider_dialog_data.js", self.name)

        logging.info("Starting %s", cmd)

        if args.apiCopy:
            args.apiCopy = os.path.abspath(os.path.expanduser(args.apiCopy))
            logging.info("Saving api input to %s", args.apiCopy)
            fpCopy = open(args.apiCopy, "wb")
        else:
            fpCopy = None

        with subprocess.Popen(cmd,
                              cwd=args.apiDir,
                              shell=False,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as p:
            buffer = ""
            while True:
                line = p.stdout.readline()
                if fpCopy:
                    fpCopy.write(line)
                    fpCopy.flush()

                if re.match(b"Error attempting to get glider data", line) is not None:
                    logging.error("ERROR executing\ncmd=%s\ndir=%s\n%s", cmd, args.apiDir, line)
                    raise Exception("Error starting API Listener")

                if (len(line) == 0) and (p.poll() is not None):
                    logging.warning("Broken connection")
                    break # Broken connection

                buffer = self.__apiLine(line, buffer)

            self.__procBuffer(buffer, True)
  
    @staticmethod
    def __mkDegrees(degmin:str, direction:str) -> float:
        try:
            degmin = float(degmin)
            sgn = -1 if degmin < 0 else +1
            sgn*= -1 if direction.lower() in "ws" else +1
            degmin = abs(degmin)
            deg = math.floor(degmin/100)
            minutes = degmin % 100
            return sgn * (deg + minutes / 60)
        except:
            logging.exception("%s %s", degmin, direction)
            return None

    def __procLine(self, line:str) -> None:
        line = line.strip()
        matches = re.match(r"Curr\s+Time:\s+\w+\s+(\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)", line)
        if matches:
            self.__time = datetime.datetime.strptime(matches[1], "%b %d %H:%M:%S %Y")
            logging.info("Current time %s", self.__time)
            return
        matches = re.match(r"^GPS Location:\s*(\d+[.]\d+) ([NS]) (\d+[.]\d+) ([EW])", line)
        if matches:
            logging.info("GPS Location %s", line)
            lat = self.__mkDegrees(matches[1], matches[2])
            lon = self.__mkDegrees(matches[3], matches[4])
            if not self.__time or not lat or not lon: return
            logging.info("GPS t %s lat %s lon %s", self.__time, lat, lon)
            self.__dialog.put(self.name, self.__time, lat, lon)
            return

    def __procBuffer(self, buffer:str, qPartial:bool = False) -> str:
        logging.info("procBuff %s", buffer)
        while len(buffer):
            index = buffer.find("\n")
            if index < 0: # No newline found
                if qPartial:
                    self.__procLine(buffer)
                    return ""
                return buffer
            self.__procLine(buffer[0:(index+1)])
            buffer = buffer[(index+1):]
        return ""

    def __apiLine(self, line:bytearray, buffer:str) -> str:
        a = re.fullmatch(bytes(r"([{].+[}])\x00\n", "utf-8"), line)
        if a is None: return buffer
        msg = json.loads(a[1])
        if "data" not in msg: return buffer
        return self.__procBuffer(buffer + msg["data"], False)

    def __apiInput(self):
        args = self.args
        fn = os.path.abspath(os.path.expanduser(args.apiInput))
        logging.info("Starting apiInput %s", fn)
        with open(fn, "rb") as fp:
            buffer = ""
            for line in fp:
                buffer = self.__apiLine(line, buffer)
                self.__procBuffer(buffer, True) # Partial Line

    def __dialogInput(self):
        args = self.args
        for fn in args.dialogInput:
            fn = os.path.abspath(os.path.expanduser(fn))
            logging.info("Starting dialogInput %s", fn)
            with open(fn, "r") as fp:
                buffer = ""
                while True:
                    txt = fp.read(1024)
                    if len(txt) == 0: # EOF
                        self.__procBuffer(buffer, True)
                        return
                    buffer = self.__procBuffer(buffer + txt)

parser = ArgumentParser(description="Glider Position Harvester")
Logger.addArgs(parser)
DBupdate.addArgs(parser)
Listener.addArgs(parser)
parser.add_argument("--glider", type=str, action="append",
                    help="List of gliders to listen to")
args = parser.parse_args()

if not args.glider:
    args.glider = ("osu684", "osu685", "osu686")

Logger.mkLogger(args)
logging.info("args=%s", args)

try:
    dialog = DBupdate(args)
    thrds = []
    for glider in args.glider:
        thrds.append(Listener(args, glider, dialog))

    dialog.start()
    for thrd in thrds: thrd.start()

    Thread.waitForException()
except:
    logging.exception("Unexpected Exception")
