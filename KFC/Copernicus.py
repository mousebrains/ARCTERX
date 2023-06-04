#! /usr/bin/env python3
#
# Play with example at
# https://help.marine.copernicus.eu/en/articles/5182598-how-to-consume-the-opendap-api-and-cas-sso-using-python
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import xarray as xr
import os
from pydap.client import open_url
from pydap.cas.get_cookies import setup_session
from TPWUtils.Credentials import getCredentials
from Config import loadConfig

def saveFile(ds:xr.Dataset, fn:str) -> None:
    encodings = {}
    for name in ds.data_vars: encodings[name] = {"zlib": True, "complevel": 9}
    logger.info("Saving %s", fn)
    ds.to_netcdf(fn, encoding=encodings)

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--yaml", type=str, default="Copernicus.yaml", help="YAML config file")
parser.add_argument("--credentials", type=str, default="~/.config/Copernicus/.copernicus",
        help="Copernicus credentials")
parser.add_argument("--data", type=str, default="~/Sync.ARCTERX/Shore/KFC",
        help="Directory to store data in")
parser.add_argument("--ndays", type=int, default=1, help="How many days from the end to save")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

info = loadConfig(args.yaml,
        ("urlLogin", "urlPrefixes", "dataSets", "latMin", "latMax", "lonMin", "lonMax"))

latMin = min(info["latMin"], info["latMax"])
latMax = max(info["latMin"], info["latMax"])
lonMin = min(info["lonMin"], info["lonMax"])
lonMax = max(info["lonMin"], info["lonMax"])

args.data = os.path.abspath(os.path.expanduser(args.data))

if not os.path.isdir(args.data):
    logger.info("Making %s", args.data)
    os.makedirs(args.data, mode=0o755, exist_ok=True)

(username, password) = getCredentials(args.credentials)

session = setup_session(info["urlLogin"], username, password)
session.cookies.set("CASTGC", session.cookies.get_dict()['CASTGC'])

for dsName in info["dataSets"]:
    data_store = None
    for urlPrefix in info["urlPrefixes"]:
        url = urlPrefix + "/" + dsName
        try:
            # needs PyDAP >= v3.3.0 see https://github.com/pydap/pydap/pull/223/commits
            data_store = xr.backends.PydapDataStore(open_url(url, 
                session=session, user_charset='utf-8'))
            break
        except:
            continue
    if data_store is None:
        logger.error("Unable to find a dataset for %s", dsName)
        continue
    with xr.open_dataset(data_store) as ds:
        ds = ds.sel(
                latitude=slice(latMin, latMax),
                longitude=slice(lonMin, lonMax),
                )
        ds = ds.isel(
                time=slice(-args.ndays,None),
                )
        for t in ds.time:
            tStr = str(t.dt.strftime("%Y%m%d").data)
            fn = os.path.join(os.path.expanduser(args.data), dsName + "." + tStr + ".nc")
            saveFile(ds.sel(time=t), fn)
