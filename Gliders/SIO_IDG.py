#! /usr/bin/env python3
#
# Pull KMZ and .mat files from a Google Drive via rclone
# Then process the .mat files into position information
# The position information is then poured into a database
# The position information in the database is then poured a CSV file for the ship
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

def syncFiles(args:ArgumentParser) -> bool:
    if args.nosync: return True
    cmd = (args.rclone, "--verbose", "sync", args.src, args.dest)
    a = subprocess.run(cmd,
                       shell=False,
                       check=False,
                       stderr=subprocess.STDOUT,
                       stdout=subprocess.PIPE,
                       )
    if a.stdout:
        logging.info("RCLONE %s", " ".join(cmd))
        try:
            logging.info("\n%s", str(a.stdout, "UTF-8"))
        except:
            logging.info("\n%s", a.stdout)
    if a.returncode == 0: return True
    logging.error("RClone failed, %s\n%s", cmd, a)
    return False

def harvestData(args:ArgumentParser) -> pd.DataFrame:
    src = args.dest
    matFiles = set()
    for (root, dirs, files) in os.walk(args.dest):
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
        db.commit()

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_argument_group(description="rclone related options")
grp.add_argument("--nosync", action="store_true", help="Do not sync using rclone")
grp.add_argument("--rclone", type=str, default="~/bin/rclone", help="Path to rclone command")
grp.add_argument("--src", type=str, default="GDrive:2023 IOP/Data", help="rclone source directory")
grp.add_argument("--dest", type=str, default="~/public_html/data",
                 help="rclone destination directory")
grp = parser.add_argument_group(description="database related options")
grp.add_argument("--nodb", action="store_true", help="Do not update the database")
grp.add_argument("--db", type=str, default="arcterx", help="Database name")
grp.add_argument("--table", type=str, default="glider", help="Database table to insert into")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.rclone = os.path.abspath(os.path.expanduser(args.rclone))
args.dest   = os.path.abspath(os.path.expanduser(args.dest))

try:
    if not os.path.isdir(os.path.dirname(args.dest)):
        dirname = os.path.dirname(args.dest)
        logging.info("Creating %s", dirname)
        os.makedirs(dirname, 0o755, exist_ok=True)

    if syncFiles(args):
        df = harvestData(args)
        logging.info("Harvested %s rows", df.shape[0])
        if not args.nosync and df is not None: 
            saveData(df, args)
except:
    logging.exception("args %s", args)
