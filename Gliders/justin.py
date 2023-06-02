#! /usr/bin/env python3
#
# Fetch UW/APL Slocum positions
#
# Store the data into a local database,
# then generate a CSV file of the records that have not been written to a CSV file.
#
# May-2023, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
import logging
from argparse import ArgumentParser
from Credentials import getCredentials
import datetime
import psycopg
import os.path
import requests

def parseBody(body:bytes, grp:str, ident:str) -> list:
    if not body: return None

    rows = []

    for line in body.split(b"\n"):
        line = line.strip();
        fields = line.split()
        if len(fields) < 3: continue
        try:
            lat = float(str(fields[0], "UTF-8"))
            lon = float(str(fields[1], "UTF-8"))
            t = datetime.datetime.strptime(str(fields[2][:20], "UTF-8"), "%Y-%m-%dT%H:%M:%SZ")
            rows.append((grp, ident, t, lat, lon))
        except:
            logging.exception("Parsing %s", line)
    return rows if rows else None

def loadURL(url:str, fnCredentials:str) -> bytes:
    with requests.session() as session:
        session.auth = getCredentials(fnCredentials)
        with session.get(url, verify=False) as r:
            if r.ok: return r.content
            logging.error("Fetching %s, %s, %s", url, r.status_code, r.reason)
            return None

def saveToDB(cur, rows:list) -> None:
    sql = "INSERT INTO glider (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
    sql+= " ON CONFLICT (t,grp,id) DO NOTHING;"
    for row in rows:
        cur.execute(sql, row)

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--grp", type=str, default="AUV", help="Group name")
parser.add_argument("--url", type=str, action="append", help="URL(s) to fetch")
parser.add_argument("--db", type=str, default="arcterx", help="Which Postgresql DB to use")
parser.add_argument("--credentials", type=str, default="~/.config/.epsilonocean.json",
                    help="Where to store credentials")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

if not args.url:
    args.url = (
            "https://dockserver.epsilonocean.com/~jshapiro/boomer/boomer_pos_wps.txt",
            "https://dockserver.epsilonocean.com/~jshapiro/starbuck/starbuck_pos_wps.txt",
            )

args.credentials = os.path.abspath(os.path.expanduser(args.credentials))

with psycopg.connect(f"dbname={args.db}") as db:
    for url in args.url:
        ident = os.path.basename(os.path.dirname(url))
        rows = parseBody(loadURL(url, args.credentials), args.grp, ident)
        cur = db.cursor() # One per URL
        saveToDB(cur, rows)
        db.commit()
