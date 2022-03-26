#! /usr/bin/env python3
#
# Extract my MMSI from the AIS data stream
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import pandas as pd
import sqlite3
import os
import time
import datetime
import sys

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--db", type=str, default="~/logs/ais.db", help="AIS database")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Ship/WaveGlider/ais.csv",
        help="AIS fixes for the WaveGlider")
parser.add_argument("--dt", type=float, default=15, help="Seconds between DB queries")
parser.add_argument("--force", action="store_true", help="Force rebuilding the CSV file")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

args.db = os.path.abspath(os.path.expanduser(args.db))
args.csv = os.path.abspath(os.path.expanduser(args.csv))

os.makedirs(os.path.dirname(args.csv), mode=0o755, exist_ok=True)

sqlX = "CREATE TEMPORARY TABLE xx AS SELECT mmsi,t,value AS lon FROM ais WHERE key='x';"
sqlY = "CREATE TEMPORARY TABLE yy AS SELECT mmsi,t,value AS lat FROM ais WHERE key='y';"
sqlJ = "SELECT xx.mmsi,datetime(xx.t, 'unixepoch') as dt,lon,lat,xx.t FROM xx"
sqlJ+= " INNER JOIN yy"
sqlJ+= " ON xx.mmsi=yy.mmsi AND xx.t==yy.t AND xx.t>?"
sqlJ+= " ORDER by xx.t;"

if args.force or not os.path.isfile(args.csv):
    logger.info("Creating header")
    with open(args.csv, "w") as fp:
        fp.write("mmsi,t,lat,lon,seconds\n")
    tPrev = 0
else:
    df = pd.read_csv(args.csv)
    tPrev = max(df.seconds)

while True:
    logger.info("tPrev %s", tPrev)
    info = {}
    with sqlite3.connect(args.db) as db, open(args.csv, "a") as fp:
        cur = db.cursor()
        cur.execute(sqlX)
        cur.execute(sqlY)
        cnt = 0
        for row in cur.execute(sqlJ, (tPrev,)):
            tPrev = row[4]
            fp.write(",".join([str(row[0]), row[1], str(row[2]), str(row[3]), str(tPrev)]) + "\n")
            cnt += 1

    logger.info("Wrote %s, sleeping for %s %s", cnt, args.dt, tPrev)
    time.sleep(args.dt)
