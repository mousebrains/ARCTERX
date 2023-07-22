#! /usr/bin/env python3
#
# Process the .mat files into position information
# The position information is then poured into a database
#
# There is an rclone mount process keeping everything synced with Google Drive
#
# The positions are poured into a CSV file for the ship via updateCSV.py
#
# June-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
from TPWUtils import Logger
import logging
import os
from scipy.io import matlab
import numpy as np
import pandas as pd
import psycopg
import sys

def harvestData(args:ArgumentParser) -> pd.DataFrame:
    matFiles = set()
    for (root, dirs, files) in os.walk(args.source):
        for fn in files:
            if fn.endswith(".mat"): matFiles.add(os.path.join(root, fn))

    items = []
    for fn in matFiles:
        if "spray_gliders" in fn:
            df = harvestMatFile(fn, "AUV", "spray")
        elif "solo_floats" in fn:
            df = harvestMatFile(fn, "FL", "solo")
        elif "SIO_OSU_FCS" in fn:
            df = harvestMatFile(fn, "FL", "FCS")
        else:
            logging.info("Unknown fn %s", fn)
            continue
        if df is not None and not df.empty: items.append(df)

    return pd.concat(items, ignore_index=True) if items else None

def harvestMatFile(fn:str, grp:str, prefix:str) -> pd.DataFrame:
    (ident, ext) = os.path.splitext(os.path.basename(fn))

    ds = matlab.loadmat(fn, variable_names="bindata")
    bindata = ds["bindata"]
    t = bindata[0,0]["time"].astype("datetime64[s]")
    sz = t.size
    df = pd.DataFrame([grp] * sz, columns=("grp",))
    df["id"] = [prefix + ident] * sz
    df["t"] = t
    df["lat"] = bindata[0,0]["lat"]
    df["lon"] = bindata[0,0]["lon"]
    return df

def saveData(df:pd.DataFrame, args:ArgumentParser) -> None:
    sql0 =f"CREATE TEMPORARY TABLE tpw (LIKE {args.table});"
    sql1 = "ALTER TABLE tpw DROP COLUMN qCSV;"
    sql2 =f"INSERT INTO {args.table} VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;"
    df = df[df.t.notnull()]
    with psycopg.connect(f"dbname={args.db}") as db:
        cur = db.cursor()
        cur.execute("BEGIN TRANSACTION;")
        cur.execute(sql0)
        cur.execute(sql1)
        for index in range(df.shape[0]):
            row = list(df.iloc[index])
            row[2] = row[2].to_pydatetime()
            cur.execute(sql2, row)
        db.commit() if not args.nodb else db.rollback()

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_argument_group(description="database related options")
grp.add_argument("--source", type=str, default="~/mnt/GDrive",
                 help="Where Google Drive files are located")
grp.add_argument("--nodb", action="store_true", help="Do not update the database")
grp.add_argument("--db", type=str, default="arcterx", help="Database name")
grp.add_argument("--table", type=str, default="glider", help="Database table to insert into")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.source = os.path.abspath(os.path.expanduser(args.source))

if not os.path.isdir(args.source):
    logging.error("%s is not a directory", args.source)
    sys.exit(1)

try:
    df = harvestData(args)
    logging.info("Harvested %s rows", df.shape[0])
    if df is not None: saveData(df, args)
except:
    logging.exception("args %s", args)
