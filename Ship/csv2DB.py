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
import datetime
import pyinotify
import time
import queue
import psycopg
import os.path

class Reader(Thread):
    def __init__(self, args:ArgumentParser, q:queue.Queue) -> None:
        Thread.__init__(self, "RDR", args)
        self.__queue = q

    def runIt(self) -> None:
        dbOpt = f"dbname={self.args.db}"
        args = self.args
        dt = args.delay
        q = self.__queue

        if os.path.isfile(args.csv):
            with psycopg.connect(dbOpt) as db: 
                self.__loadFile(db, args.csv)

        while True:
            (t0, fn) = q.get()
            q.task_done()
            if fn != args.csv: continue
            time.sleep(dt)
            with psycopg.connect(dbOpt) as db: self.__loadFile(db, fn)

    def __loadFile(self, db, fn:str) -> bool:
        sql0 = "INSERT INTO ship (id,t,lat,lon)"
        sql0+= " VALUES(%s,%s,%s,%s)"
        sql0+= " ON CONFLICT DO NOTHING;"

        sql1 = "SELECT position FROM filePosition WHERE filename=%s;"

        sql2 = "INSERT INTO filePosition VALUES (%s,%s)"
        sql2+= " ON CONFLICT (filename) DO UPDATE SET position=excluded.position;"

        cur = db.cursor()
        pos = None
        if self.args.force:
            self.args.force = False
        else:
            for row in cur.execute(sql1, [fn]):
                pos = row[0]
                break
        logging.info("fn %s pos %s", fn, pos)
        cur.execute("BEGIN TRANSACTION;")
        cnt = 0
        with open(fn, "r") as fp:
            if pos:
                fp.seek(pos)
            for line in fp:
                fields = line.strip().split(",")
                if len(fields) < 4: continue # Truncated line so ignore
                if fields[0] == "id": continue
                try:
                    # fields[1] = datetime.datetime.fromtimestamp(fields[1], datetime.timezone.utc)
                    fields[2] = float(fields[2])
                    fields[3] = float(fields[3])
                    cur.execute(sql0, fields)
                    cnt += 1
                except:
                    logging.exception("")
                    continue
            if cnt:
                ipos = pos
                pos = fp.tell()
                cur.execute(sql2, (fn, pos))
                logging.info("Loaded %s cnt %s pos %s -> %s", fn, cnt, ipos, pos)
                db.commit()
                return True
            else:
                logging.info("Nothing from %s pos %s", fn, pos)
                db.rollback()
                return False
        
parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--sql", type=str, default="ship.sql",
                    help="Filename with table definitions")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Ship/pos.csv",
        help="Input directory to monitor for changes")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--delay", type=float, default=10,
        help="Number of seconds after an update until loading the changes")
parser.add_argument("--force", action="store_true", help="Force loading entire CSV file")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))

with psycopg.connect(f"dbname={args.db}") as db:
    loadAndExecuteSQL(db, args.sql)

flags = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO

inotify = INotify.INotify(args, flags)
rdr = Reader(args, inotify.queue)

inotify.start()
rdr.start()

inotify.addTree(os.path.dirname(args.csv))

try:
    Thread.waitForException()
except:
    logging.exception("Exception from INotify")
