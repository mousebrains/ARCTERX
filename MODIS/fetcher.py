#! /usr/bin/env python3
#
# Pull NOAA/MODIS level 3 data
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import yaml
import os
from io import StringIO
import json
import datetime
import requests
import xarray as xr
import sys

def fetchFile(url:str, data:str, force:bool=False) -> str:
    ofn = os.path.join(data, os.path.basename(url))
    if not force and os.path.isfile(ofn): # Don't fetch a second time
        logger.info("%s already fetched", ofn)
        return ofn
    logger.info("Fetching %s", url)
    with requests.get(url) as r: # Using .netrc authentication method
        if r.status_code != 200:
            logger.error("RC=%s fetching %s\n%s", r.status_code, url, r.text)
            return None
        content = r.content
        logger.info("Writing %s bytes to %s", len(content), ofn)
        with open(ofn, "wb") as fp: fp.write(content)
        return ofn

parser = ArgumentParser(description="Download LAADS data and store them")
Logger.addArgs(parser)
parser.add_argument("--force", action="store_true", help="Force fetching of files")
parser.add_argument("--yaml", type=str, default="MODIS.yaml", help="YAML configuration file")
parser.add_argument("--data", type=str, default="data", help="Where to store full data files")
parser.add_argument("--pruned", type=str, default="~/Sync.ARCTERX/Shore/MODIS",
        help="Directory to store pruned data in")
parser.add_argument("--ndays", type=int, default=1, help="Number of days back to fetch data for")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

logger.info("args %s", args)

with open(args.yaml, "r") as fp: info = yaml.safe_load(fp)

for key in sorted(info):
    logger.info("info[%s] = %s", key, info[key])

for key in ("urlPrefix", "threshold", "latMin", "latMax", "lonMin", "lonMax", 
        "YearDOY", "YYYYMMDD"):
    if key not in info:
        logger.error("The %s entry is missing from %s", key, args.yaml)
        sys.exit(1)

urlPrefix = info["urlPrefix"]

args.data = os.path.abspath(os.path.expanduser(args.data))
args.pruned = os.path.abspath(os.path.expanduser(args.pruned))

for name in (args.data, args.pruned):
    if not os.path.isdir(name):
        logger.info("Creating %s", name)
        os.makedirs(name, mode=0o776, exist_ok=True)
 
# Get the current date
now = datetime.datetime.now(tz=datetime.timezone.utc)
if now.hour < info["threshold"]:
    logger.info("Backup up one day due to threshold, %s, %s", now, info["threshold"])
    now -= datetime.timedelta(days=1)
now = now.date()

toPrune = set() # Set of filename that were fetched, so they need pruned.

for n in range(args.ndays):
    today = now - datetime.timedelta(days=n)
    yesterday = today - datetime.timedelta(days=1)
    year = today.strftime("%Y")
    doy = yesterday.strftime("%j")
    logger.debug("n %s today %s yesterday %s year %s doy %s", n, today, yesterday, year, doy)
    for fn in info["YearDOY"]:
        toPrune.add(fetchFile(urlPrefix + fn.format(year, doy), args.data, args.force))
    for fn in info["YYYYMMDD"]:
        toPrune.add(fetchFile(urlPrefix + fn.format(yesterday.strftime("%Y%m%d")),
            args.data, args.force))

latMin = min(info["latMin"], info["latMax"])
latMax = max(info["latMin"], info["latMax"])
lonMin = min(info["lonMin"], info["lonMax"])
lonMax = max(info["lonMin"], info["lonMax"])

for fn in toPrune:
    if fn is None: continue
    ofn = os.path.join(args.pruned, os.path.basename(fn))
    if not os.path.isfile(fn):
        logger.error("File %s does not exist", fn)
        continue
    if os.path.isfile(ofn): # Check modification times
        if os.stat(fn).st_mtime < os.stat(ofn).st_mtime:
            logger.info("No need to prune %s", fn)
            continue
    logger.info("Pruning %s", fn)
    with xr.open_dataset(fn) as ds:
        logger.info("Original sizes %s", ds.sizes)
        ds = ds.sel(
            lat=slice(latMax, latMin), # Data ordered +90->90
            lon=slice(lonMin, lonMax), # Data ordered -180->180
            )
        logger.info("Pruned sizes %s", ds.sizes)
        ds.to_netcdf(ofn)
