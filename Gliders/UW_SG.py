#! /usr/bin/env python3
#
# Fetch UW/APL Seaglider positions
#
# Store the data into a local database,
# then generate a CSV file of the records that have not been written to a CSV file.
# Also adapt the fetch data into the past, based on the last time stamps in the database.
#
# May-2023, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
import logging
from argparse import ArgumentParser
import datetime
import datetime
import psycopg
import os
import requests

def updateCSV(db, grp:str, fn:str, qForce:bool) -> None:
    sql0 = "CREATE TEMPORARY TABLE tpwUW (LIKE glider);"

    sql1 = "WITH updated AS ("
    sql1+= "UPDATE glider SET qCSV=TRUE"
    sql1+= " WHERE grp=%s"
    if not args.force: sql1+= " AND NOT qCSV"
    sql1+= " RETURNING grp,id,t,lat,lon"
    sql1+= ")"
    sql1+= "INSERT INTO tpwUW SELECT * FROM updated;"

    sql2 = "SELECT id,t,lat,lon"
    sql2+= " FROM tpwUW ORDER BY t;"

    cur = db.cursor()
    cur.execute(sql0)
    cur.execute(sql1, (grp,))

    nCreated = 0
    nOpened = 0
    cnt = 0
    fp = None
    for row in cur.execute(sql2):
        if not fp:
            if args.force or not os.path.exists(fn):
                logging.info("Creating %s", fn)
                nCreated += 1
                fp = open(fn, "w")
                fp.write("id,t,lat,lon\n")
            else:
                logging.info("Opening %s", fn)
                nOpened += 1
                fp = open(fn, "a")
        fp.write(",".join(map(str, row)) + "\n")
        cnt += 1

    if fp: fp.close()
    logging.info("Fetched %s CSV records created %s opened %s", cnt, nCreated, nOpened)

def loadURL(url:str) -> dict:
    with requests.get(url) as r:
        if not r.ok:
            logging.error("Fetching %s, %s, %s", url, r.status_code, r.reason)
        return r.json()

def saveToDB(cur, grp:str, ident:str, info:dict) -> None:
    sql = "INSERT INTO glider (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
    sql+= " ON CONFLICT (t,grp,id) DO UPDATE SET"
    sql+= " lat=excluded.lat"
    sql+= ",lon=excluded.lon"
    sql+= ";"
    t = datetime.datetime.fromtimestamp(info["epoch"]).replace(tzinfo=datetime.timezone.utc)
    args = (grp, ident, t, info["lat"], info["lon"])
    cur.execute(sql, args)

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--grp", type=str, default="AUV", help="Group name")
parser.add_argument("--url", type=str, action="append", help="URL(s) to fetch")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Gliders/UW.csv",
        help="Where to CSV filename")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--force", action="store_true", help="Rebuild the CSV file from scratch")
grp = parser.add_mutually_exclusive_group()
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

if not args.url:
    args.url = (
            "https://iopbase3.apl.washington.edu/pos/poll/141",
            "https://iopbase3.apl.washington.edu/pos/poll/526",
            "https://iopbase3.apl.washington.edu/pos/poll/528",
            "https://iopbase3.apl.washington.edu/pos/poll/687",
            )

args.csv = os.path.abspath(os.path.expanduser(args.csv))

if not os.path.isdir(os.path.dirname(args.csv)):
    dirname = os.path.dirname(args.csv)
    logging.info("Creating %s", dirname)
    os.makedirs(dirname, mode=0o755, exist_ok=True)

with psycopg.connect(f"dbname={args.db}") as db: # Get the last time stored in the database
    for url in args.url:
        ident = os.path.basename(url)
        info = loadURL(url)
        cur = db.cursor()
        saveToDB(cur, args.grp, ident, info)
        db.commit()
    updateCSV(db, args.grp, args.csv, args.force)
