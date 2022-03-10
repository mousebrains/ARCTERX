#! /usr/bin/env python3
#
# Pull NOAA/MODIS level 3 data
#
# March-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import os
import logging
from io import StringIO
import json
import datetime
import requests
import xarray as xr
import sys

def fetchFile(url:str, data:str) -> str:
    ofn = os.path.join(data, os.path.basename(url))
    if os.path.isfile(ofn): # Don't fetch a second time
        logging.info("%s already fetched", ofn)
        return ofn
    logging.info("Fetching %s", url)
    with requests.get(url) as r: # Using .netrc authentication method
        if r.status_code != 200:
            logging.error("RC=%s fetching %s\n%s", r.status_code, url, r.text)
            return None
        logging.info("Writing %s bytes to %s", len(r.content), ofn)
        with open(ofn, "wb") as fp: fp.write(r.content)
        return ofn

parser = ArgumentParser(description="Download LAADS data and store them")
parser.add_argument("--urlPrefix", metavar="URL",  
        default="https://oceandata.sci.gsfc.nasa.gov/ob/getfile/",
        help="URL prefix")
parser.add_argument("--filename", type=str, action="append",
        metavar="A{}{}.L3m_DAY_CHL_chl_ocx_4km.nc",
        help="Filename(s) to fetch, with year and day of year being filled in")
parser.add_argument("--MODIS", type=str, action="append",
        metavar="AQUA_MODIS.{}.L3m.DAY.NSST.sst.4km.NRT.nc",
        help="Filename(s) to fetch, with year and day of year being filled in")
parser.add_argument("--data", type=str, default="data", help="Where to store full data files")
parser.add_argument("--pruned", type=str, default="~/Sync.ARCTERX/Shore/MODIS",
        help="Where to store pruned data files")
parser.add_argument("--latMin", type=float, default=0, help="Minimum latitude")
parser.add_argument("--latMax", type=float, default=25, help="Maximum latitude")
parser.add_argument("--lonMin", type=float, default=120, help="Minimum longitude")
parser.add_argument("--lonMax", type=float, default=155, help="Maximum longitude")
parser.add_argument("--ndays", type=int, default=1, help="Number of days back to fetch data for")
grp = parser.add_argument_group(description="Logging options")
grp.add_argument("--verbose", action="store_true", help="Enable INFO messages")
grp.add_argument("--debug", action="store_true", help="Enable INFO+DEBUG messages")
args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.INFO)
elif args.debug:
    logging.basicConfig(level=logging.DEBUG)

if args.filename is None:
    args.filename = (
            "A{}{}.L3m_DAY_CHL_chlor_a_4km.nc",
            "A{}{}.L3m_DAY_CHL_chl_ocx_4km.nc",
            "A{}{}.L3m_DAY_FLH_ipar_4km.nc",
            "A{}{}.L3m_DAY_FLH_nflh_4km.nc",
            )

if args.MODIS is None:
    args.MODIS = (
            "AQUA_MODIS.{}.L3m.DAY.NSST.sst.4km.NRT.nc",
            )

args.data = os.path.abspath(os.path.expanduser(args.data))
args.pruned = os.path.abspath(os.path.expanduser(args.pruned))

os.makedirs(args.data, mode=0o776, exist_ok=True)
os.makedirs(args.pruned, mode=0o776, exist_ok=True)
  
toPrune = set()
for n in range(args.ndays):
    today = datetime.date.today() - datetime.timedelta(days=n)
    yesterday = today - datetime.timedelta(days=1)
    year = today.strftime("%Y")
    doy = yesterday.strftime("%j")
    logging.debug("n %s today %s yesterday %s year %s doy %s", n, today, yesterday, year, doy)
    for fn in args.filename:
        toPrune.add(fetchFile(args.urlPrefix + fn.format(year, doy), args.data))
    for fn in args.MODIS:
        toPrune.add(fetchFile(args.urlPrefix + fn.format(yesterday.strftime("%Y%m%d")), args.data))


for fn in toPrune:
    if fn is None: continue
    logging.info("Pruning %s", fn)
    ofn = os.path.join(args.pruned, os.path.basename(fn))
    with xr.open_dataset(fn) as ds:
        logging.info("Original sizes %s", ds.sizes)
        ds = ds.sel(
            lat=slice(max(args.latMin, args.latMax), min(args.latMin, args.latMax)),
            lon=slice(min(args.lonMin, args.lonMax), max(args.lonMin, args.lonMax)),
            )
        logging.info("Pruned sizes %s", ds.sizes)
        logging.info("Saving pruned to %s", ofn)
        ds.to_netcdf(ofn)
