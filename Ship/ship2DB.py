#! /usr/bin/env python3
#
# Extract the ship's position and store it in a DB and update CSV files
#
# April-2023, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from TPWUtils.loadAndExecuteSQL import loadAndExecuteSQL
from argparse import ArgumentParser
import datetime
import logging
import time
import psycopg
import os

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--ship", type=str, default="~/ship.csv", help="Ship's CSV file")
parser.add_argument("--id", type=str, default="Thompson", help="Ship's name")
parser.add_argument("--sql", type=str, default="ship.sql",
                    help="Filename with table definitions")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Ship/Ship",
        help="Output directory to save CSV files into")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--delay", type=float, default=60,
        help="Number of seconds between reads of the ship's file")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.sql = os.path.abspath(os.path.expanduser(args.sql))
args.csv = os.path.abspath(os.path.expanduser(args.csv))
args.ship = os.path.abspath(os.path.expanduser(args.ship))

with psycopg.connect(f"dbname={args.db}") as db:
    loadAndExecuteSQL(db, args.sql)

sql0 = "INSERT INTO ship (id,t,lat,lon,spd,hdg) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;"
sql1 = "SELECT position FROM filePosition WHERE filename=%s;"
sql2 = "INSERT INTO filePosition VALUES(%s,%s) ON CONFLICT (filename) DO UPDATE SET position=excluded.position;"

now = time.time()

while True:
    lastRow = None
    cnt = 0
    with psycopg.connect(f"dbname={args.db}") as db:
        cur = db.cursor()
        pos = None
        for row in cur.execute(sql1, [args.ship]):
            pos = row[0]
            break
        cur.execute("BEGIN TRANSACTION;")
        with open(args.ship, "r") as fp:
            if pos:
                fp.seek(pos)
            for line in fp:
                logging.info("line %s", line.strip())
                fields = line.strip().split(",")
                if len(fields) < 5: continue
                try:
                    a = [args.id]
                    a.append(datetime.datetime.fromtimestamp(float(fields[0]), datetime.timezone.utc))
                    a.append(float(fields[1]))
                    a.append(float(fields[2]))
                    a.append(float(fields[3]))
                    a.append(float(fields[4]))
                    cur.execute(sql0, a)
                    lastRow = a[1:]
                    cnt += 1
                except:
                    logging.exception("fields %s", fields)
            cur.execute(sql2, (args.ship, fp.tell()))
            db.commit()
    logging.info("Saved %s records from %s", cnt, args.ship)
    # Now update the CSV file
    ofn = os.path.join(args.csv, args.id + ".csv")
    if not os.path.isfile(ofn):
        dirname = os.path.dirname(ofn)
        if not os.path.isdir(dirname):
            logging.info("Creating %s", dirname)
            os.makedirs(dirname, 0o744, exist_ok=True)
        with open(ofn, "w") as fp:
            fp.write("t,lat,lon,spd,hdg\n")
    if lastRow:
        lastRow[0] = lastRow[0].timestamp()
        lastRow = map(str, lastRow)
        with open(ofn, "a") as fp:
            fp.write(",".join(lastRow) + "\n")

    tNext = now + args.delay
    dt = tNext - time.time()
    now = tNext
    time.sleep(max(dt, 0.01))
