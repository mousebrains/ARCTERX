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
import logging
from argparse import ArgumentParser
from Credentials import getCredentials
import math
import datetime
import re
import psycopg
import os
import sys
import requests
from requests.auth import HTTPDigestAuth

def updateCSV(db, dirname:str, qForce:bool) -> None:
    sql0 = "CREATE TEMPORARY TABLE tpwDrifter (LIKE drifter);"
    sql1 = "WITH updated AS ("
    sql1+= "UPDATE drifter SET qCSV=TRUE"
    if not args.force: sql1+= " WHERE NOT qCSV"
    sql1+= " RETURNING ident,t,latitude,longitude,SST,SLP,battery,drogueCounts"
    sql1+= ")"
    sql1+= "INSERT INTO tpwDrifter SELECT * FROM updated;"

    sql2 = "SELECT ident,t,latitude,longitude,SST,SLP,battery,drogueCounts"
    sql2+= " FROM tpwDrifter ORDER BY t;"

    cur = db.cursor()
    cur.execute(sql0)
    cur.execute(sql1)

    nCreated = 0
    nOpened = 0
    cnt = 0
    yyyymmdd = None
    fp = None
    for row in cur.execute(sql2):
        base = row[1].strftime("%Y%W")
        if base != yyyymmdd:
            yyyymmdd = base
            if fp: fp.close()
            fn = os.path.join(dirname, f"drifter.{base}.csv")
            if args.force or not os.path.exists(fn):
                logging.info("Creating %s", fn)
                nCreated += 1
                fp = open(fn, "w")
                fp.write("ident,time,latitude,longitude,sst,slp,battery,drogue\n")
            else:
                logging.info("Opening %s", fn)
                nOpened += 1
                fp = open(fn, "a")
        fp.write(",".join(map(str, row)) + "\n")
        cnt += 1

    if fp: fp.close()
    logging.info("Fetched %s CSV records created %s opened %s", cnt, nCreated, nOpened)

def mkTable(db) -> None:
    sql = "CREATE TABLE IF NOT EXISTS drifter (\n"
    sql+= " ident VARCHAR(20) COMPRESSION lz4,\n"
    sql+= " t TIMESTAMP WITH TIME ZONE,\n"
    sql+= " latitude DOUBLE PRECISION NOT NULL,\n"
    sql+= " longitude DOUBLE PRECISION NOT NULL,\n"
    sql+= " SST DOUBLE PRECISION,\n"
    sql+= " SLP DOUBLE PRECISION,\n"
    sql+= " battery DOUBLE PRECISION,\n"
    sql+= " drogueCounts INTEGER,\n"
    sql+= " qCSV BOOLEAN DEFAULT FALSE,\n"
    sql+= " PRIMARY KEY(t, ident)\n"
    sql+= ");"

    sql1 = "CREATE INDEX IF NOT EXISTS drifter_ident ON drifter (ident);"

    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;");
    cur.execute(sql);
    cur.execute(sql1);
    db.commit()

def lastTime(db) -> None:
    cur = db.cursor()
    for row in cur.execute("SELECT max(t) FROM drifter;"):
        return row[0]
    return None

def fetchData(db, args:ArgumentParser) -> None:
    if args.nofetch: return # Nothing to do

    t = None if args.refetch else lastTime(db)
    if t is None:
        url = args.url + "?start_date=" + args.startDate
    else:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        dt = max(0, (now - t).total_seconds()) # seconds since last update
        dt += 300 # Add 5 minute to the fetch interval
        dt /= 86400 # Days ago
        dt = math.ceil(dt * 10000) / 10000 # round up to the longer 8.64 second interval
        url = args.url + f"?days_ago={dt}"
    logging.info("url %s", url)
    with requests.get(url, auth=(username, codigo)) as r:
        sql = "INSERT INTO drifter"
        sql+= "(ident,t,latitude,longitude,SST,SLP,battery,drogueCounts)"
        sql+= " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)"
        sql+= " ON CONFLICT (t,ident) DO UPDATE SET"
        sql +=" latitude=excluded.latitude"
        sql +=",longitude=excluded.longitude"
        sql +=",SST=excluded.SST"
        sql +=",SLP=excluded.SLP"
        sql +=",battery=excluded.battery"
        sql +=",drogueCounts=excluded.drogueCounts"
        sql+= ";"
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
            fields[1] = fields[1].replace(tzinfo=datetime.timezone.utc)
            cur.execute(sql, fields[0:8])
            cnt += 1
        db.commit()
        logging.info("Fetched %d bytes which is %d records", len(r.text), cnt)

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/Drifters/.drifters",
        help="Location of credentials file")
parser.add_argument("--startDate", type=str, default="2022-03-26",
        help="When to start fetching data from")
parser.add_argument("--url", type=str,
        default="https://gdp.ucsd.edu/cgi-bin/projects/arcterx/drifter.py",
        help="URL to fetch")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Drifter",
        help="Where to store CSV files")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--force", action="store_true", help="Rebuild the CSV file from scratch")
grp = parser.add_mutually_exclusive_group()
grp.add_argument("--refetch", action="store_true", help="Rebuild the DB from a full fetch")
grp.add_argument("--nofetch", action="store_true", help="Do not actually fetch fresh data")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))
args.credentials = os.path.abspath(os.path.expanduser(args.credentials))

if not os.path.isdir(os.path.dirname(args.csv)):
    dirname = os.path.dirname(args.csv)
    logging.info("Creating %s", dirname)
    os.makedirs(dirname, mode=0o755, exist_ok=True)

(username, codigo) = getCredentials(args.credentials) # login credentials for ucsd

with psycopg.connect(f"dbname={args.db}") as db: # Get the last time stored in the database
    mkTable(db)
    fetchData(db, args)
    updateCSV(db, args.csv, args.force)
