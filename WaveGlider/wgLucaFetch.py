#! /usr/bin/env python3
#
# Fetch Luca's Wave Glider information
#
# June-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Credentials import getCredentials
import requests
import psycopg
import json
import datetime
from TPWUtils import Logger
import logging
import os

def parseJSON(items:list, grp:str) -> list:
    rows = [];
    for item in items:
        row = [grp]
        for key in ("vehicleName", "lastLocationFix", "latitude", "longitude"):
            if key not in item: continue
            row.append(item[key])
        row[2] = datetime.datetime.strptime(row[2], "%Y-%m-%dT%H:%M:%S") \
                .replace(tzinfo=datetime.timezone.utc)
        row[3] = float(row[3])
        row[4] = float(row[4])
        rows.append(row)
    return rows

def parseInput(fn:str, grp:str) -> list:
    with open(fn, "r") as fp: items = json.load(fp)
    return parseJSON(items, grp)

def urlFetch(args:ArgumentParser, latestDate:datetime.datetime) -> list:
    with requests.session() as session:
        session.auth = getCredentials(args.credentials)
        if latestDate:
            t = (latestDate + datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = args.url + f"&start_date={t}"
        else:
            url = args.url + f"&days_ago={args.daysAgo}"
        with session.get(url) as r:
            if r.ok:
                return parseJSON(r.json(), args.group)
            logging.error("Unable to fetch %s, %s, %s", url, r.status_code, r.reason)
            return None

def saveRows(cur, rows:list, args:ArgumentParser) -> bool:
    sql =f"INSERT INTO {args.table} (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
    sql+= " ON CONFLICT DO NOTHING;"
    for row in rows:
        cur.execute(sql, row)
    return len(rows)

def saveCSV(db, args:ArgumentParser, rows:list) -> None:
    if not args.csv: return
    args.csv = os.path.abspath(os.path.expanduser(args.csv))
    if not args.csv:
        logging.info("Creating %s", args.csv)
        os.makedirs(args.csv, 0o755, exist_ok=True)

    sql0 =f"CREATE TEMPORARY TABLE tpw (LIKE {args.table});"
    sql1 = "WITH updated As ("
    sql1+=f"UPDATE {args.table} SET qCSV=TRUE"
    sql1+=" WHERE grp=%s AND id=%s"
    if not args.force: sql1 += " AND NOT qCSV"
    sql1+= " RETURNING grp,id,t,lat,lon"
    sql1+= ")"
    sql1+= " INSERT INTO tpw SELECT * FROM updated;"

    sql2 = "SELECT id,ROUND(EXTRACT(EPOCH FROM t)),ROUND(lat::numeric,6),ROUND(lon::numeric,6)"
    sql2+= " FROM tpw ORDER BY t;"

    cur = db.cursor()
    cur.execute(sql0)
    for row in rows:
        cur.execute(sql1, (args.group, row[1]))

    nCreated = 0
    nOpened = 0
    cnt = 0
    yyyymmdd = None
    fp = None
    fnPrev = None
    for row in cur.execute(sql2):
        vehicle = row[0]
        t = row[1]
        base = datetime.datetime.fromtimestamp(round(row[1]))\
                .replace(tzinfo=datetime.timezone.utc).strftime("%Y%W")
        fn = os.path.join(args.csv, f"{args.group}_{row[0]}_{base}.pos.csv")
        if fn != fnPrev:
            fnPrev = fn
            if fp: fp.close()
            if args.force or not os.path.exists(fn):
                logging.info("Creating %s", fn)
                nCreated += 1
                fp = open(fn, "w")
                fp.write("t,lat,lon\n")
            else:
                logging.info("Opening %s", fn)
                nOpened += 1
                fp = open(fn, "a")
        fp.write(",".join(map(str, row[1:])) + "\n")
        cnt += 1

    if fp: fp.close()
    logging.info("Fetched %s CSV records created %s opened %s", cnt, nCreated, nOpened)

def getLatestDate(db, args:ArgumentParser) -> datetime.datetime:
    sql =f"SELECT MAX(t) FROM {args.table} WHERE grp=%s AND id=%s;"
    for row in cur.execute(sql, (args.group, args.vehicleName)):
        return row[0]
    return None

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_mutually_exclusive_group()
grp.add_argument("--input", type=str, help="File of input JSON records")
grp.add_argument("--fetch", action="store_true", help="Fetch from the URL")
parser.add_argument("--csv", type=str, 
                    default="~/Sync.ARCTERX/Shore/WG",
                    help="Directory to store CSV files in")
parser.add_argument("--group", type=str, default="WG", help="Wave Glider group")
parser.add_argument("--force", action="store_true", help="Force full regeneration of CSV file")
parser.add_argument("--credentials", type=str, default="~/.config/.luca",
                    help="Where to store credentials")
parser.add_argument("--url", type=str,
                    default="https://ldl.ucsd.edu/cgi-bin/projects/arcterx/wgms.py?platform_id=591915973&output=json",
                    help="Base URL to fetch data from")
parser.add_argument("--daysAgo", type=float, default=10, help="Days back for first fetch")
parser.add_argument("--db", type=str, default="arcterx", help="Database name")
parser.add_argument("--table", type=str, default="glider", help="Database table name")
parser.add_argument("--vehicleName", type=str, default="WENDA", help="Vehicle name for max time")
args = parser.parse_args()

Logger.mkLogger(args)

with psycopg.connect(f"dbname={args.db}") as db:
    cur = db.cursor()
    if args.input:
        rows = parseInput(args.input, args.group)
    else:
        latestDate = getLatestDate(cur, args)
        rows = urlFetch(args, latestDate)

    if rows:
        cur.execute("BEGIN TRANSACTION;")
        nRows = saveRows(db, rows, args)
        logging.info("Saved %s rows", nRows)
        db.commit()
        if nRows:
            saveCSV(db, args, rows)
