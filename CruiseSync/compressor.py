#! /usr/bin/env python3
#
# Decimate the MET files to 1/minute so they are not so big, then put these into the
# Sync.ARCHIVE/ship directory to be sent to shore.
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import os
import bz2
import sqlite3
import math
import glob
import sys

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--output", type=str, default="~/Sync.ARCTERX/Ship/MET", 
        help="Where pruned output files go")
parser.add_argument("--met", type=str, default="/mnt/cruise/RR2202/data/met/data",
        help="Where *.MET files are located")
parser.add_argument("--extension", type=str, default="MET", help="File extension to look for")
parser.add_argument("--db", type=str, default="data/MET.db",
        help="Database of last file offsets processed")
parser.add_argument("--dt", type=int, default=15, help="Minimum seconds between samples")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.met = os.path.abspath(os.path.expanduser(args.met))
args.db = os.path.abspath(os.path.expanduser(args.db))
args.output = os.path.abspath(os.path.expanduser(args.output))

os.makedirs(args.output, mode=0o755, exist_ok=True)
os.makedirs(os.path.dirname(args.db), mode=0o755, exist_ok=True)

with sqlite3.connect(args.db) as db:
    cur = db.cursor()
    sql = "CREATE TABLE IF NOT EXISTS offsets (\n"
    sql+= " fn TEXT PRIMARY KEY,\n"
    sql+= " offset INTEGER);\n"
    cur.execute("BEGIN TRANSACTION;")
    cur.execute(sql)
    cur.execute("COMMIT;")
    for ifn in glob.glob(os.path.join(args.met, "*." + args.extension)):
        fnBase = os.path.basename(ifn)
        offset = 0
        for row in cur.execute("SELECT offset FROM offsets WHERE fn=?;", (fnBase,)):
            offset = row[0]
            break
        ofn = os.path.join(args.output, fnBase + ".bz2")
        with open(ifn, "rb") as ifp, bz2.open(ofn, mode="ab" if offset else "wb") as ofp:
            ifp.seek(offset)
            while True:
                buf = ifp.read(1024*1024)
                if not buf: break
                ofp.write(buf)
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("INSERT OR REPLACE INTO offsets VALUES(?,?);", (fnBase, ifp.tell()))
            cur.execute("COMMIT;")
            logger.info("Appended %s to %s", ifp.tell() - offset, ofn)
