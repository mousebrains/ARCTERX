#! /usr/bin/env python3
#
# Fetch UW SeaGlider data for the position of the latest surfacing
#
# April-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
from Credentials import getCredentials
import datetime
import pandas as pd
import xarray as xr
import requests
from tempfile import NamedTemporaryFile
import sys
import os

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--url", type=str,
        default="https://iop.apl.washington.edu/seaglider/sg526/current/data/sg526_ARCTERX_timeseries.nc",
        help="URL to fetch")
parser.add_argument("--credentials", type=str,  default="~/.config/SG/.credentials",
        help="Login credentials")
parser.add_argument("--csv", type=str,
        default="~/Sync.ARCTERX/Shore/WaveGlider/sg_526_positions.csv",
        help="Output CSV filename")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

args.csv = os.path.abspath(os.path.expanduser(args.csv))

os.makedirs(os.path.dirname(args.csv), mode=0o755, exist_ok=True)

with requests.get(args.url, auth=getCredentials(args.credentials)) as r:
    if r.status_code != 200:
        logger.warning("Error fetching %s\n%s", args.url, args.text)
        sys.exit(1)
    with NamedTemporaryFile() as fp:
        fp.write(r.content)
        fp.flush()
        with xr.open_dataset(fp.name) as ds:
            q = ds.end_time.max() == ds.end_time
            t = datetime.datetime.fromtimestamp(float(ds.end_time[q][0]) / 1e9)
            t = t.replace(tzinfo=datetime.timezone.utc)
            t = t.strftime("%Y-%m-%d %H:%M:%S")
            lat = float(ds.end_latitude[q][0])
            lon = float(ds.end_longitude[q][0])
            csv = pd.DataFrame()
            csv["t"] = [t]
            csv["lat"] = [lat]
            csv["lon"] = [lon]
            if os.path.isfile(args.csv):
                csv = csv.append(pd.read_csv(args.csv))
                csv = csv.drop_duplicates(subset="t")
                csv = csv.sort_values("t")
            csv.to_csv(args.csv, index=False)
