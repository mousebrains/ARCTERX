#! /usr/bin/env python3
#
# Fetch Luca's Wave Glider information
#
# June-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import requests
import psycopg
import json
import numpy as np
from TPWUtils import Logger
import logging
import sys

def parseJSON(items:list, grp:str) -> list:
    rows = [];
    for item in items:
        row = [grp]
        for key in ("vehicleName", "lastLocationFix", "latitude", "longitude"):
            if key not in item: continue
            row.append(item[key])
        row[2] = np.datetime64(row[2])
        row[3] = float(row[3])
        row[4] = float(row[4])
        rows.append(row)
    return rows

def parseInput(fn:str, grp:str) -> list:
    with open(fn, "r") as fp: items = json.load(fp)
    return parseJSON(items, grp)

def urlFetch(url:str, grp:str) -> list:
    with request.get(url) as r:
        if r.ok:
            return parseJSON(r.json(), grp)
        logging.error("Unable to fetch %s, %s, %s", url, r.status_code, r.reason)
        return None

def saveRows(cur, rows:list) -> bool:
    sql = "INSERT INTO glider (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
    sql+= " ON CONFLICT DO NOTHING;"
    for row in rows:
        cur.execute(sql, row)
    return True

def saveCSV(db, tbl:str, qForce:bool) -> None:
    sql0 = "CREATE TEMPORARY TABLE tpw LIKE (glider);"
    sql1 = "WITH updated As ("
    sql1+=f"UPDATE {tbl} SET qCSV=TRUE"
    sql1+=" WHERE grp=%s"
    if not qForce: sql1 += " AND NOT qCSV"
    sql1+= " RETURNING id,t,lat,lon"
    sql1+= ")"
    sql1+= "INSERT INTO tpw SELECT * FROM updated;"

    sql2 = "SELECT id,t,lat,lon FROM tpw ORDER BY t;"

    cur = db.cursor()
    cur.execute(sql0)
    cur.execute(sql1)

    nCreated = 0
    nOpened = 0
    cnt = 0
    yyyymmdd = None
    fp = None
    for row in cur.execute(sql2):
        base = row[1].strftime("%Y%m%d")
        if base != yyyymmdd:
            yyyymmdd = base
            if fp: fp.close()
            fn = os.path.join(dirname, f"drifter.{base}.csv")
            if args.force or not os.path.exists(fn):
                logging.info("Creating %s", fn)
                nCreated += 1
                fp = open(fn, "w")
                fp.write("id,t,lat,lon,sst,slp,battery,drogue\n")
            else:
                logging.info("Opening %s", fn)
                nOpened += 1
                fp = open(fn, "a")
        fp.write(",".join(map(str, row)) + "\n")
        cnt += 1

    if fp: fp.close()
    logging.info("Fetched %s CSV records created %s opened %s", cnt, nCreated, nOpened)

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--input", type=str, help="File of input JSON records")
grp.add_argument("--url", type=str, help="URL to fetch data from")
parser.add_argument("--csv", type=str, help="Directory to store CSV files in")
parser.add_argument("--group", type=str, default="WG", help="Wave Glider group")
parser.add_argument("--force", action="store_true", help="Force full regeneration of CSV file")
args = parser.parse_args()

Logger.mkLogger(args)

if args.input:
    rows = parseInput(args.input, args.group)
elif args.url:
    rows = urlFetch(args.fetch, args.group)

if not rows: sys.exit(0)

for row in rows: print(row)
with psycopg.connection(f"dbname={args.db}") as db:
    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;")
    if saveRows(db, rows): saveCSV(db)
    db.commit()
