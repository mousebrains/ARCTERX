#! /usr/bin/env python3
#
# Extract the ship's position from a db and save it in a CSV file
#
# April-2023, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import logging
import time
import psycopg
import os

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Ship/pos.csv",
        help="Output directory to save CSV files into")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--delay", type=float, default=900, help="Number of seconds between updates of CSV file")
parser.add_argument("--force", action="store_true", help="Force rebuild of CSV file")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))
qAdjust = args.force

sql0 = "CREATE TEMPORARY TABLE tpwShip (LIKE ship);"

sql1 = "WITH updated AS ("
sql1+= "UPDATE ship SET qCSV=True"
if not args.force: sql1+= " WHERE NOT qCSV"
sql1+= " RETURNING id,t,lat,lon"
sql1+= ")"
sql1+= " INSERT INTO tpwShip SELECT * FROM updated;"

sql2 = "SELECT id,t,lat,lon FROM tpwShip ORDER BY t;"

if args.force:
    with open(args.csv, "w") as fp:
        fp.write("id,t,lat,lon\n");

now = time.time()

while True:
    with psycopg.connect(f"dbname={args.db}") as db:
        cur = db.cursor()
        cur.execute("BEGIN TRANSACTION;")
        cur.execute(sql0);
        cur.execute(sql1);
        cur.execute(sql2);
        with open(args.csv, "a") as fp:
            for row in cur:
                fp.write(f"{row[0]},{row[1]},{row[2]},{row[3]}\n")
        db.commit()

    if qAdjust:
        qAdjust = False
        sql1 = "WITH updated AS ("
        sql1+= "UPDATE ship SET qCSV=True"
        sql1+= " WHERE NOT qCSV"
        sql1+= " RETURNING id,t,lat,lon"
        sql1+= ")"
        sql1+= " INSERT INTO tpwShip SELECT * FROM updated;"

    tNext = now + args.delay
    dt = tNext - time.time()
    now = tNext
    time.sleep(max(dt, 0.01))
