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
import psycopg
import os
import requests

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
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
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
