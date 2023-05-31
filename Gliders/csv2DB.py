#! /usr/bin/env python3
#
# Increamentally read a growing CSV file and store the results into a PostgreSQL database
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from TPWUtils import INotify
from TPWUtils.Thread import Thread
from TPWUtils.loadAndExecuteSQL import loadAndExecuteSQL
from argparse import ArgumentParser
import logging
import pyinotify
import time
import queue
import psycopg
import re
import glob
import os.path

class Reader(Thread):
    def __init__(self, args:ArgumentParser, q:queue.Queue) -> None:
        Thread.__init__(self, "RDR", args)
        self.__queue = q

    def runIt(self) -> None:
        dbOpt = f"dbname={self.args.db}"
        dt = self.args.delay
        exp = re.compile(r".?[.]csv")
        logging.info("exp %s", exp)
        q = self.__queue

        with psycopg.connect(dbOpt) as db: 
            for fn in glob.glob(os.path.join(args.csv, "*.csv")):
                if not exp.fullmatch(os.path.basename(fn)): continue
                self.__loadFile(db, fn, args.group)

        while True:
            (t0, fn) = q.get()
            q.task_done()
            if not exp.fullmatch(os.path.basename(fn)): continue
            time.sleep(dt)
            logging.info("Woke up")
            with psycopg.connect(dbOpt) as db: self.__loadFile(db, fn)

    @staticmethod
    def __loadFile(db, fn:str, grp:str) -> bool:
        sql0 = "INSERT INTO glider (grp,id,t,lat,lon)"
        sql0+= " VALUES(%s,%s,%s,%s,%s)"
        sql0+= " ON CONFLICT DO NOTHING;"

        sql1 = "SELECT position FROM filePosition WHERE filename=%s;"

        sql2 = "INSERT INTO filePosition VALUES (%s,%s)"
        sql2+= " ON CONFLICT (filename) DO UPDATE SET position=excluded.position;"

        cur = db.cursor()
        pos = None
        for row in cur.execute(sql1, [fn]):
            pos = row[0]
            break
        cur.execute("BEGIN TRANSACTION;")
        cnt = 0;
        with open(fn, "r") as fp:
            if pos:
                fp.seek(pos)
            for line in fp:
                fields = line.strip().split(",")
                if len(fields) < 4: continue # Truncated line so ignore
                try:
                    args = (
                            grp,
                            fields[0],
                            fields[1],
                            float(fields[2]) if fields[2] != "None" else None,
                            float(fields[3]) if fields[2] != "None" else None,
                            )
                    cur.execute(sql0, args)
                    cnt += 1
                except:
                    continue
            if cnt:
                ipos = pos
                pos = fp.tell()
                cur.execute(sql2, (fn, pos))
                logging.info("Loaded %s cnt %s pos %s -> %s", fn, cnt, ipos, pos)
                db.commit();
            else:
                logging.info("Nothing from %s pos %s", fn, pos)
                db.rollback();
        
parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--group", type=str, default="AUV", help="Group name being saved to")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Gldiers",
        help="Input directory to monitor for changes")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--delay", type=float, default=10,
        help="Number of seconds after an update until loading the changes")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))

if not os.path.isdir(args.csv):
    logging.error("%s is not a directory", args.csv)
    sys.exit(1)

with psycopg.connect(f"dbname={args.db}") as db:
    loadAndExecuteSQL(db, args.sql, "glider")

flags = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO

inotify = INotify.INotify(args, flags)
rdr = Reader(args, inotify.queue)

inotify.start()
rdr.start()

inotify.addTree(args.csv)

try:
    Thread.waitForException()
except:
    logging.exception("Exception from INotify")
