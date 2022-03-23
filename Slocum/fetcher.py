#! /usr/bin/env python3
#
# Fetch Slocum glider data from UW
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from Credentials import getCredentials
import os
import sys
from datetime import datetime
import sqlite3

def createTable(cur) -> None:
    sql = "CREATE TABLE IF NOT EXISTS position (\n"
    sql+= " t REAL PRIMARY KEY,\n"
    sql+= " lat REAL,\n"
    sql+= " lon REAL,\n"
    sql+= " wptLat REAL,\n"
    sql+= " wptLon REAL\n"
    sql+= ");\n"
    cur.execute(sql)

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/Slocum/.UW",
        help="Credentials for fetching UW data")
parser.add_argument("--url", type=str,
        default="https://dockserver.potechnic.com/~jshapiro/starbuck_pos_wps.txt",
        help="URL to fetch data from")
parser.add_argument("--db", type=str, default="data/pos.db",
        help="Where to store the output database")
parser.add_argument("--csv", type=str, default="~/Sync.ARCTERX/Shore/Slocum/pos.csv",
        help="Where to store the csv")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.csv = os.path.abspath(os.path.expanduser(args.csv))
args.db = os.path.abspath(os.path.expanduser(args.db))

os.makedirs(os.path.dirname(args.db), mode=0o755, exist_ok=True)
os.makedirs(os.path.dirname(args.csv), mode=0o755, exist_ok=True)

(username, codigo) = getCredentials(os.path.abspath(os.path.expanduser(args.credentials)))

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

rows = []
with requests.get(args.url, auth=(username, codigo), verify=False) as r:
    if r.status_code != 200:
        logger.error("Fetching %s, %s\n%s", r.url, r.status_code, r.content)
        sys.exit(1)
    for line in r.text.split("\n"):
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            lat0 = float(fields[0])
            lon0 = float(fields[1])
            t = datetime.strptime(fields[2], "%Y-%m-%dT%H:%M:%SZ")
            lat1 = float(fields[3])
            lon1 = float(fields[4])
            rows.append((t, lat0, lon0, lat1, lon1))
        except Exception as e:
            logger.exception("While convertings %s", line)

logger.info("Updating %s rows", len(rows))

with sqlite3.connect(args.db) as db:
    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;")
    createTable(cur)
    sql = "INSERT OR REPLACE INTO position values(?,?,?,?,?);"
    for row in rows:
        cur.execute(sql, row)
    cur.execute("COMMIT;")
    with open(args.csv, "w") as fp:
        fp.write("t,lat,lon,wptLat,wptLon\n")
        for row in cur.execute("SELECT * FROM position ORDER BY t DESC LIMIT 10;"):
            fp.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n")
