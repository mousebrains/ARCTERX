#! /usr/bin/env python3
#
# Extract rows from database where qCSV is true
# and save into a CSV file.
#
# Ripped out of UW_SG.py
#
# July-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils import Logger
import logging
import psycopg
import os

def openFile(fn:str, qForce:bool):
    if not qForce and os.path.isfile(fn):
        logging.info("Opening %s", fn)
        return open(fn, "a")

    dirname = os.path.dirname(fn)
    if not os.path.isdir(dirname):
        logging.info("Creating %s", dirname)
        os.makedirs(dirname, mode=0o755, exist_ok=True)

    logging.info("Creating %s", fn)
    fp = open(fn, "w")
    fp.write("id,t,lat,lon\n")
    return fp

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--grp", type=str, default="AUV", help="Group name")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Gliders/UW.csv",
                    help="Where to CSV filename")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--force", action="store_true", help="Rebuild the CSV file from scratch")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))

sql0 = "CREATE TEMPORARY TABLE TPW (LIKE glider);"

sql1 = "WITH updated AS ("
sql1+= "UPDATE glider SET qCSV=TRUE"
sql1+= " WHERE grp=%s"
if not args.force: sql1+= " AND NOT qCSV"
sql1+= " RETURNING grp,id,t,lat,lon"
sql1+= ")"
sql1+= "INSERT INTO TPW SELECT * FROM updated;"

sql2 = "SELECT id,t,lat,lon FROM TPW ORDER BY t;"

fp = None

with psycopg.connect(f"dbname={args.db}") as db: # Get the last time stored in the database
    try:
        cur = db.cursor()
        cur.execute(sql0)
        cur.execute("BEGIN TRANSACTION;")
        cur.execute(sql1, (args.grp,))

        cnt = 0
        for row in cur.execute(sql2):
            if fp is None: fp = openFile(args.csv, args.force)
            fp.write(",".join(map(str, row)) + "\n")
            cnt += 1

        if fp: fp.close()
        db.commit()
        logging.info("Fetched %s CSV records into %s", cnt, args.csv)
    except:
        db.rollback()
        logging.exception("Unexpected error %s", args)
