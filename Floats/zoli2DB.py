#! /usr/bin/env python3
#
# Update PostgreSQL glider table when Zoli sends new information
#
# May-2022, Pat Welch, pat@mousebrains.com

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
import re
import glob
import sys
import os

class Reader(Thread):
    def __init__(self, args:ArgumentParser, q:queue.Queue) -> None:
        Thread.__init__(self, "RDR", args)
        self.__queue = q

    def runIt(self) -> None:
        dbOpt = f"dbname={self.args.db}"
        dt = self.args.delay
        exp = re.compile(r".+[.]txt")
        logging.info("exp %s", exp)
        q = self.__queue

        cnt = 0
        with psycopg.connect(dbOpt) as db: 
            for fn in glob.glob(os.path.join(args.zoli, "*gps_log.txt")):
                if "share" in fn: continue
                cnt += self.__loadFile(db, fn, args.group)
            if cnt:
                self.__saveCSV(db, args)

        while True:
            (t0, fn) = q.get()
            q.task_done()
            if not exp.fullmatch(os.path.basename(fn)): continue
            time.sleep(dt)
            logging.info("Woke up")
            with psycopg.connect(dbOpt) as db: 
                if self.__loadFile(db, fn, args.group):
                    self.__saveCSV(db, args)

    @staticmethod
    def __loadFile(db, fn:str, grp:str) -> int:
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

        ident = os.path.basename(os.path.dirname(fn))
        qAlto = "alto" in fn
        if qAlto:
            tFormat = "%Y-%m-%dT%H:%M:%SZ"
        else:
            tFormat = "%m/%d/%Y %H:%M:%S"
        cur.execute("BEGIN TRANSACTION;")
        cnt = 0;
        with open(fn, "r") as fp:
            if pos:
                fp.seek(pos)
            for line in fp:
                fields = line.strip().split(",")
                if len(fields) < (4+qAlto): continue # Truncated line, so ignore
                if fields[0] in ("flnum", "id"): continue # Alto header
                try:
                    if qAlto and ((fields[1] == "divenum") or (float(fields[1]) < 0)):
                        continue # Skip prep testing
                    args = (
                            grp,
                            ident,
                            datetime.datetime.strptime(fields[1+qAlto], tFormat),
                            float(fields[2+qAlto]),
                            float(fields[3+qAlto]),
                            )
                    cur.execute(sql0, args)
                    cnt += 1
                except:
                    logging.exception("Line %s", line)
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
        return cnt

    @staticmethod
    def __saveCSV(db, args:ArgumentParser):
        sql0 = "CREATE TEMPORARY TABLE tpw (LIKE glider);"

        sql1 = "WITH updated AS ("
        sql1+= "UPDATE glider SET qCSV=TRUE"
        sql1+= " WHERE grp=%s"
        if not args.force: sql1+= " AND NOT qCSV"
        sql1+= " RETURNING grp,id,t,lat,lon"
        sql1+= ")"
        sql1+= "INSERT INTO tpw SELECT * FROM updated;"

        sql2 = "SELECT id,ROUND(EXTRACt(EPOCH FROM t)),ROUND(lat::NUMERIC,6),ROUND(lon::NUMERIC,6)"
        sql2+= " FROM tpw ORDER BY t;"

        cur = db.cursor()
        cur.execute(sql0)
        cur.execute(sql1, (args.group,))

        nCreated = 0
        nOpened = 0
        cnt = 0
        fp = None
        for row in cur.execute(sql2):
            if not fp:
                if args.force or not os.path.exists(args.csv):
                    logging.info("Creating %s", args.csv)
                    nCreated += 1
                    fp = open(args.csv, "w")
                    fp.write("id,t,lat,lon\n")
                else:
                    logging.info("Opening %s", args.csv)
                    nOpened += 1
                    fp = open(args.csv, "a")
            fp.write(",".join(map(str, row)) + "\n")
            cnt += 1

        if fp: fp.close()
        logging.info("Fetched %s CSV records created %s opened %s", cnt, nCreated, nOpened)
        
parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--group", type=str, default="FL", help="Group name being saved to")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Floats/zoli.csv",
        help="Output directory")
parser.add_argument("--zoli", type=str, default="~zszuts/floatdata/*/*arc1",
        help="Input directory to monitor for changes")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--delay", type=float, default=10,
        help="Number of seconds after an update until loading the changes")
parser.add_argument("--force", action="store_true", help="Force CSV rebuild");
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.zoli = os.path.abspath(os.path.expanduser(args.zoli))
args.csv = os.path.abspath(os.path.expanduser(args.csv))

if not os.path.isdir(os.path.dirname(args.csv)):
    dirname = os.path.dirname(args.csv)
    logging.info("Creating %s", dirname)
    os.makedirs(dirname, 0o744, exist_ok=True)

flags = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO

inotify = INotify.INotify(args, flags)
rdr = Reader(args, inotify.queue)

inotify.start()
rdr.start()

try:
    for dirname in glob.glob(args.zoli):
        inotify.addTree(dirname)

    Thread.waitForException()
except:
    logging.exception("Exception from INotify")
