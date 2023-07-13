#! /usr/bin/env python3
#
# Pull lat/lon/time from NetCDF files and add to PostgreSQL database
#
# July-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import numpy as np
import pandas as pd
import xarray as xr
import datetime
import psycopg
import os.path

parser = ArgumentParser()
parser.add_argument("nc", type=str, nargs="+", help="Input NetCDF files")
parser.add_argument("--database", type=str, default="arcterx", help="Database to operate on")
parser.add_argument("--table", type=str, default="glider", help="Database table to operate on")
parser.add_argument("--group", type=str, default="AUV", help="group name")
parser.add_argument("--t0", type=str, default="2023-07-06 02:24:58",
                    help="Earliest time to consider")
args = parser.parse_args()

t0 = np.datetime64(args.t0)

sql =f"INSERT INTO {args.table} (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
sql+= " ON CONFLICT DO NOTHING;"

with psycopg.connect(f"dbname={args.database}") as db:
    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;")
    for fn in args.nc:
        with xr.open_dataset(fn) as ds:
            df = pd.DataFrame()
            if "ctd_time" in ds:
                if not np.any(ds.ctd_time > t0): continue
                df["t"] = ds.ctd_time.data.flatten()
                df["lat"] = ds.latitude.data.flatten()
                df["lon"] = ds.longitude.data.flatten()
            elif "time" in ds: 
                if not np.any(ds.time > t0): continue
                df["t"] = ds.time.data.flatten()
                df["lat"] = ds.latitude.data.flatten()
                df["lon"] = ds.longitude.data.flatten()
            else:
                continue
            df = df[df.t > t0]
            df = df.sort_values("t")
            df = df.iloc[-1]
            ident = os.path.basename(fn)[1:4]
            t = float(df.t.to_numpy().astype("datetime64[s]").astype(float))
            t = datetime.datetime.fromtimestamp(t).replace(tzinfo=datetime.timezone.utc)

            print(fn, ident, t, df.lat, df.lon)
            cur.execute(sql, (args.group, ident, t, float(df.lat), float(df.lon)))
    db.commit()
