#! /usr/bin/env python3
#
# Fetch drifter data
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
from Credentials import getCredentials
import requests
from requests.auth import HTTPDigestAuth
import os
import re
import pandas as pd
import numpy as np

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/Drifters/.drifters",
        help="Location of credentials file")
grp = parser.add_mutually_exclusive_group()
grp.add_argument("--ndays", type=float, help="Number of days back")
grp.add_argument("--start", type=str, help="Starting data to fetch data from")
parser.add_argument("--url", type=str,
        default="https://gdp.ucsd.edu/cgi-bin/projects/arcterx/drifter.py",
        help="URL to fetch")
parser.add_argument("--data", type=str, default="~/Sync.ARCTERX/Shore/Drifter",
        help="Where to store output")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.data = os.path.abspath(os.path.expanduser(args.data))

url = args.url
if args.start:
    url += f"?start_date={args.start}"
elif args.ndays:
    url += f"?days_ago={args.ndays}"
else:
    url += f"?start_date=2022-03-20"

if not os.path.isdir(args.data):
    logger.info("Creating %s", args.data)
    os.makedirs(args.data, mode=0o755, exist_ok=True)

(username, codigo) = getCredentials(args.credentials)

df = pd.DataFrame()
hdr = None
with requests.get(url, auth=(username, codigo)) as r:
    for line in r.text.split("\n"):
        if line == "": continue
        fields = line.split(",")
        if not len(fields): continue
        if re.match(r"\d+", fields[0]):
            df = df.append(pd.Series(fields), ignore_index=True)
        else:
            hdr = fields

df = df.sort_values([1, 2, 0])
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

fn = os.path.join(args.data, "drifter.csv")
logger.info("Saving %s rows to %s", df.shape[0], fn)
df.to_csv(fn, header=hdr, index=False)
