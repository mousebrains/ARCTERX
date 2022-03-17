#! /usr/bin/env python3
#
# Grab GHRSST-SSTfnd data from JPL/NASA
#
# I want to use eosdis_store, but the data is stored as "shuffle deflate"
# which zarr does not support.
#
# So grab the whole file and then prune to lat/lon box
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
from Credentials import getCredentials
import requests
import xarray as xr
import os
import datetime

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/NASA/.NASA.credentials",
        help="Where credentials are stored")
parser.add_argument("--provider", type=str, default="POCLOUD", help="Data provider")
parser.add_argument("--shortName", type=str, default="MUR-JPL-L4-GLOB-v4.1",
        help="Which glob to grab data from")
parser.add_argument("--daysBack", type=int, default=1,
        help="How many days into the past to end looking for data")
parser.add_argument("--ndays", type=int, default=2, help="How many days to fetch data for")
parser.add_argument("--latMin", type=float, default=10, help="Minimum latitude value")
parser.add_argument("--latMax", type=float, default=23, help="Maximum latitude value")
parser.add_argument("--lonMin", type=float, default=135, help="Minimum longitude value")
parser.add_argument("--lonMax", type=float, default=150, help="Maximum longitude value")
parser.add_argument("--cmrURL", type=str,
        default="https://cmr.earthdata.nasa.gov/search/granules.json",
        help="Where to get CMR catalog from")
parser.add_argument("--data", type=str, default="data", help="Where to store full dataset")
parser.add_argument("--pruned", type=str, default="~/Sync.ARCTERX/Shore/KFC",
        help="Where to store pruned dataset")
parser.add_argument("--skip", type=int, default=2, help="Number to skip")
parser.add_argument("--force", action="store_true", help="Force fetching")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

today = datetime.date.today()
fmt = "%Y-%m-%dT00:00:00Z"
start_time = (today - datetime.timedelta(days=args.daysBack+args.ndays)).strftime(fmt)
end_time   = (today - datetime.timedelta(days=args.daysBack)).strftime(fmt)
logger.info("Start %s end %s bbox [%s,%s], [%s,%s]", start_time, end_time,
        args.latMin, args.latMax, args.lonMin, args.lonMax)

lats = slice(min(args.latMin, args.latMax), max(args.latMin, args.latMax))
lons = slice(min(args.lonMin, args.lonMax), max(args.lonMin, args.lonMax))

response = requests.get(args.cmrURL,
                        params={
                            'provider': args.provider,
                            'short_name': args.shortName,
                            'temporal': f'{start_time},{end_time}',
                            'bounding_box': f'{lons.start},{lats.start},{lons.stop},{lats.stop}',
                            'page_size': 2000,
                            }
                       )

granules = response.json()['feed']['entry']
urls = set()
for granule in granules:
    for link in granule["links"]:
        if link["rel"].endswith("/data#"):
            urls.add(link["href"])
            break

(username, codigo) = getCredentials(args.credentials)

args.data = os.path.abspath(os.path.expanduser(args.data))
args.pruned = os.path.abspath(os.path.expanduser(args.pruned))

for name in (args.data, args.pruned):
    if not os.path.isdir(name):
        logger.info("Making %s", name)
        os.makedirs(name, mode=0o755, exist_ok=True)

files = set()
with requests.Session() as session:
    for url in urls:
        fn = os.path.join(args.data, os.path.basename(url))
        files.add(fn)
        if not args.force and os.path.isfile(fn):
            logger.info("%s already exists", fn)
            continue
        logger.info("Fetching %s", url)
        r1 = session.request("get", url)
        r = session.get(r1.url, auth=(username, codigo), stream=True)
        r.raise_for_status()
        with open(fn, "wb") as fp:
            for chunk in r.iter_content(chunk_size=1024*1024):
                fp.write(chunk)

        pfn = os.path.join(args.pruned, fn)

for fn in files:
    ofn = os.path.join(args.pruned, os.path.basename(fn))
    with xr.open_dataset(fn) as ds:
        ds = ds.sel(lat=lats, lon=lons)
        if args.skip > 1:
            ds = ds.isel(
                    lat=slice(0,ds.dims["lat"],args.skip),
                    lon=slice(0,ds.dims["lon"],args.skip),
                    )
        encodings = {}
        for name in ds.data_vars: encodings[name] = {"zlib": True, "complevel": 9}
        logger.info("Saving %s", ofn)
        ds.to_netcdf(ofn, encoding=encodings)

