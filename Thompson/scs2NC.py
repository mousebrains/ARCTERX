#! /usr/bin/env python3
#
# Process various Sonic wind bow sensor for true speed and direction
#
# April-2023, Pat Welch, pat@mousebrains.com

import logging
import os.path
import glob
import datetime
import math
import re
import time
import numpy as np
import pandas as pd
from mkNC import createNetCDF
from netCDF4 import Dataset
import psycopg

def mkFilenames(paths:tuple, cur) -> dict:
    regexp = re.compile("^(FLUOROMETER|SS|TSG|SBE38|CNAV3050-(GGA|VTG)|SONIC-TWIND|PAR)-RAW_(\d+)-\d+.Raw$")
    sql = "SELECT position FROM fileposition WHERE filename=%s;"
    info = {}
    for path in paths:
        for fn in glob.glob(os.path.join(path, "*", "*.Raw")):
            name = os.path.basename(fn)
            matches = regexp.match(name)
            if not matches:
                continue

            cur.execute(sql, (fn,))
            pos = None
            for row in cur:
                pos = row[0]
                break

            if pos == os.path.getsize(fn): continue

            date = datetime.datetime.strptime(matches[3], "%Y%m%d").date()
            if date not in info: info[date] = {}
            info[date][fn] = pos
    return info

def decodeDegMin(degMin:str, direction:str) -> float:
    degMin = float(degMin)
    sgn = -1 if degMin < 0 else 1
    sgn*= -1 if direction.upper() in ("S", "W") else 1
    degMin = abs(degMin)
    deg = math.floor(degMin/100)
    minutes = degMin % 100
    return sgn * (deg + minutes / 60)

def procTWind(fields:tuple) -> dict:
    return {"wSpd": float(fields[3]), "wDir": float(fields[4])}

def procGGA(fields:tuple) -> dict:
    return {
            "lat": decodeDegMin(fields[4], fields[5]),
            "lon": decodeDegMin(fields[6], fields[7]),
            }

def procVTG(fields:tuple) -> dict:
    return {
            "cog": float(fields[3]),
            "sog": float(fields[7]),
            }

def procPAR(fields:tuple) -> dict:
    return {
            "par": float(fields[3]),
            "Tair": float(fields[4]),
            }

def procSpeedOfSound(fields:tuple) -> dict:
    return {
            "spdSound": float(fields[2]),
            }

def procSBE38(fields:tuple) -> dict:
    return {
            "Tinlet": float(fields[2]),
            }

def procTSG(fields:tuple) -> dict:
    return {
            "Ttsg": float(fields[2]),
            "cond": float(fields[3]),
            "salinity": float(fields[4]),
            }

def procFluorometer(fields:tuple) -> dict:
    items = fields[2].split("\t")
    if len(items) < 6: return None
    return {
            "fluorometer": int(items[4]),
            "flThermistor": int(items[5]),
            }

codigos = {
        "$TWIND": procTWind,
        "$GPGGA": procGGA,
        "$GPVTG": procVTG,
        "$PPAR": procPAR,
        "SBE38": procSBE38,
        "TSG": procTSG,
        "SS": procSpeedOfSound,
        "FLUOR": procFluorometer,
        }

def procLine(line:str, codigo:str=None) -> dict:
    if not line: return None
    fields = line.strip().split(",")
    if len(fields) < 3: return None
    try:
        t = datetime.datetime.strptime(fields[0] + " " + fields[1], "%m/%d/%Y %H:%M:%S.%f")
        tt = t.replace(microsecond=0)
        if t.microsecond >= 500000: tt += datetime.timedelta(seconds=1)
        t  = np.datetime64(t)
        tt = np.datetime64(tt)
        dt = (t - tt).astype("timedelta64[ms]").astype(float) / 1000

        codigo = fields[2] if codigo is None else codigo

        if codigo not in codigos:
            logging.warning("Unsupported record type, %s", codigo)
            return None

        val = codigos[codigo](fields)
        return ({"t": tt, "dt": dt} | val) if val else None
    except:
        logging.exception("codigo %s Fields %s", codigo, fields)

def loadFile(fn:str, pos:int) -> tuple:
    basename = os.path.basename(fn)
    if basename.startswith("TSG-"):
        codigo = "TSG"
    elif basename.startswith("SBE38-"):
        codigo = "SBE38"
    elif basename.startswith("SS-"):
        codigo = "SS"
    elif basename.startswith("FLUOROMETER-"):
        codigo = "FLUOR"
    else:
        codigo = None
    items = []
    with open(fn, "r") as fp:
        if pos: fp.seek(pos)
        for line in fp:
            val = procLine(line, codigo)
            if val: items.append(val)
        pos = fp.tell()
    if not items: return (None, None) # In case there is nothing
    df = pd.DataFrame(items)
    return (df, pos)

def saveDataframe(nc, df:pd.DataFrame, tBase:np.int64) -> None:
    t = (df.t - tBase).astype("timedelta64[s]").astype(np.int64)

    nc.variables["t"][t] = t

    for key in df:
        if key in ["t", "dt"]: continue
        nc.variables[key][t] = df[key].to_numpy()
   
def getTimeOffset(nc) -> np.int64:
    units = nc.variables["t"].getncattr("units")
    since = "since "
    index = units.find(since) + len(since)
    return np.datetime64(units[index:])

def loadIt(paths:list, nc:str, dbName:str) -> None:
    sql = "INSERT INTO filePosition VALUES (%s, %s)"
    sql+= " ON CONFLICT (filename) DO UPDATE SET position=EXCLUDED.position;"

    with psycopg.connect(f"dbname={dbName}") as db:
        cur = db.cursor()
        filenames = mkFilenames(paths, cur)
        for date in sorted(filenames): print(date, len(filenames[date]))

        cur.execute("BEGIN TRANSACTION;")

        for date in sorted(filenames):
            logging.info("Working on %s", date)
            frames = []
            for fn in filenames[date]:
                logging.info("Working on %s", fn)
                (df, pos) = loadFile(fn, filenames[date][fn])
                cur.execute(sql, (fn, pos))
                if df is not None and not df.empty: 
                    frames.append(df)
    
            if not os.path.isfile(nc):
                tMin = None
                for df in frames:
                    tMin = df.t.min() if tMin is None else min(tMin, df.t.min())
                createNetCDF(nc, tMin.to_datetime64())

            with Dataset(nc, "a") as nc:
                tBase = getTimeOffset(nc)
                for df in frames: saveDataframe(nc, df, tBase)

            break # TPW
        db.commit()

if __name__ == "__main__":
    from argparse import ArgumentParser
    from TPWUtils import Logger

    parser = ArgumentParser()
    Logger.addArgs(parser)
    parser.add_argument("directory", type=str, nargs="+", help="Directories to look in")
    parser.add_argument("--nc", type=str, required=True, help="Output filename")
    parser.add_argument("--db", type=str, default="arcterx", help="Database name")
    args = parser.parse_args()

    Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

    args.nc = os.path.abspath(os.path.expanduser(args.nc))
    directories = []
    for directory in args.directory:
        directories.append(os.path.abspath(os.path.expanduser(directory)))

    loadIt(directories, args.nc, args.db)
