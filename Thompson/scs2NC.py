#! /usr/bin/env python3
#
# Process various Sonic wind bow sensor for true speed and direction
#
# April-2023, Pat Welch, pat@mousebrains.com

import logging
import os.path
import datetime
import math
import numpy as np
import pandas as pd
from netCDF4 import Dataset

tRef = int(datetime.datetime.strptime("2023-04-15 00:00:00", "%Y-%m-%d %H:%M:%S").replace(
    tzinfo=datetime.timezone.utc).timestamp())

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
    t = datetime.datetime.strptime(fields[0] + " " + fields[1],
                                   "%m/%d/%Y %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc)
    tt = t.replace(microsecond=0)
    if t.microsecond >= 500000: tt += datetime.timedelta(seconds=1)

    codigo = fields[2] if codigo is None else codigo

    if codigo not in codigos:
        logging.warning("Unsupported record type, %s", codigo)
        return None

    val = codigos[codigo](fields)
    return ({"t": tt, "dt": (t - tt).total_seconds()} | val) if val else None

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

def saveDataframe(nc, df) -> None:
    t = df.t.map(pd.Timestamp.timestamp).astype(np.int64) # Unix seconds
    t -= tRef

    nc.variables["t"][t] = t

    for key in df:
        if key in ["t", "dt"]: continue
        nc.variables[key][t] = df[key].to_numpy()
    

if __name__ == "__main__":
    from argparse import ArgumentParser
    from TPWUtils import Logger

    parser = ArgumentParser()
    Logger.addArgs(parser)
    parser.add_argument("nc", type=str, help="NetCDF filename")
    parser.add_argument("file", type=str, nargs="+", help="Filename(s) of TWIND file")
    args = parser.parse_args()

    Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

    frames = []
    for fn in args.file:
        (df, pos) = loadFile(fn, None)
        if not df.empty: frames.append(df)

    with Dataset(args.nc, "a") as nc:
        for df in frames:
            saveDataframe(nc, df)
