#! /usr/bin/env python3
#
# Fetch drifter data from SIO.
#
# Store the data into a local database,
# then generate a CSV file of the records that have not been written to a CSV file.
# Also adapt the fetch data into the past, based on the last time stamps in the database.
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
from Credentials import getCredentials
import math
import datetime
import re
import sqlite3
import os
import sys
import requests
from requests.auth import HTTPDigestAuth

def mkTable(db) -> None:
    sql = "CREATE TABLE IF NOT EXISTS drifter (\n"
    sql+= " ident TEXT,\n"
    sql+= " t TEXT,\n"
    sql+= " latitude FLOAT,\n"
    sql+= " longitude FLOAT,\n"
    sql+= " SST FLOAT,\n"
    sql+= " SLP FLOAT,\n"
    sql+= " battery FLOAT,\n"
    sql+= " drogueCounts INTEGER,\n"
    sql+= " qCSV INTEGER DEFAULT 0,\n"
    sql+= " PRIMARY KEY(t, ident)\n"
    sql+= ");"
    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;");
    cur.execute(sql);
    db.commit()

def lastTime(db) -> None:
    cur = db.cursor()
    for row in cur.execute("SELECT t FROM drifter ORDER BY t DESC LIMIT 1;"):
        return datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    return None

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/Drifters/.drifters",
        help="Location of credentials file")
parser.add_argument("--startDate", type=str, default="2022-03-26",
        help="When to start fetching data from")
parser.add_argument("--url", type=str,
        default="https://gdp.ucsd.edu/cgi-bin/projects/arcterx/drifter.py",
        help="URL to fetch")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Drifter/drifter.csv",
        help="Where to store output")
parser.add_argument("--db", type=str, default="~/logs/drifter.db",
        help="Where to store the database")
parser.add_argument("--force", action="store_true", help="Rebuild the CSV file from scratch")
grp = parser.add_mutually_exclusive_group()
grp.add_argument("--refetch", action="store_true", help="Rebuild the DB from a full fetch")
grp.add_argument("--nofetch", action="store_true", help="Do not actually fetch fresh data")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))
args.db = os.path.abspath(os.path.expanduser(args.db))
args.credentials = os.path.abspath(os.path.expanduser(args.credentials))

if not os.path.isdir(os.path.dirname(args.csv)):
    logger.info("Creating %s", os.path.dirname(args.data))
    os.makedirs(os.path.dirname(args.data), mode=0o755, exist_ok=True)

if not os.path.isdir(os.path.basename(args.db)):
    logger.info("Creating %s", os.path.basename(args.db))
    os.makedirs(os.path.basename(args.db), mode=0o755, exist_ok=True)

(username, codigo) = getCredentials(args.credentials) # login credentials for ucsd

with sqlite3.connect(args.db) as db: # Get the last time stored in the database
    mkTable(db)
    if not args.nofetch:
        t = None if args.refetch else lastTime(db)
        if t is None:
            url = args.url + "?start_date=" + args.startDate
        else:
            dt = (datetime.datetime.now() - t).total_seconds() / 86400
            dt += 300/86400 # Add 5 minute to the fetch interval
            dt = math.ceil(dt * 1000) / 1000
            url = args.url + f"?days_ago={dt}"
        logger.info("url %s", url)
        with requests.get(url, auth=(username, codigo)) as r:
            sql = "INSERT OR REPLACE INTO drifter (ident,t,latitude,longitude,SST,SLP,battery,drogueCounts)"
            sql+= " VALUES(?,?,?,?,?,?,?,?);"
            cur = db.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cnt = 0
            for line in r.text.split("\n"):
                if re.match(r"^Platform-ID", line): continue
                fields = line.split(",")
                if len(fields) < 8: continue;
                for i in range(len(fields)):
                    fields[i] = fields[i].strip() # Strip off leanding/trailing whitespace
                fields[1] = datetime.datetime.strptime(fields[1], "%Y-%m-%d %H:%M:%S")
                cur.execute(sql, fields[0:8])
                cnt += 1
            db.commit()
            logger.info("Fetched %d bytes which is %d records", len(r.text), cnt)

    # Now build the CSV file
    fn = args.csv
    sql = "SELECT ident,t,latitude,longitude,SST,SLP,battery,drogueCounts FROM drifter"
    if args.force or not os.path.isfile(fn):
        mode = "w"
    else:
        sql+= " WHERE qCSV!=1"
        mode = "a"
    sql+= " ORDER BY t,ident;"

    cur = db.cursor()
    wrote = []
    with open(fn, mode) as fp:
        if mode == "w":
            fp.write("Platform-ID,Timestamp(UTC),GPS-Latitude(deg),GPS-Longitude(deg),SST(degC),SLP(mB) Battery(volts),Drogue (cnts)\n")
        for row in cur.execute(sql):
            cnt += 1
            fp.write(",".join(map(str, row)) + "\n")
            wrote.append((row[1], row[0]))
        if len(wrote): # Update qCSV for these records
            cur.execute("BEGIN TRANSACTION;")
            for item in wrote:
                cur.execute("UPDATE drifter SET qCSV=1 WHERE t=? AND ident=?", item)
            db.commit()
        logger.info("Wrote %d records to %s", len(wrote), fn)
