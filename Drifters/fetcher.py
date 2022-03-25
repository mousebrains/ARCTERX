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

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--credentials", type=str, default="~/.config/Drifters/.drifters",
        help="Location of credentials file")
parser.add_argument("--url", type=str,
        default="https://gdp.ucsd.edu/cgi-bin/projects/arcterx/drifter.py?start_date=2022-03-20",
        help="URL to fetch")
parser.add_argument("--data", type=str, default="~/Sync.ARCTERX/Shore/Drifter",
        help="Where to store output")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.data = os.path.abspath(os.path.expanduser(args.data))

if not os.path.isdir(args.data):
    logger.info("Creating %s", args.data)
    os.makedirs(args.data, mode=0o755, exist_ok=True)

(username, codigo) = getCredentials(args.credentials)

with requests.get(args.url, auth=(username, codigo)) as r:
    fn = os.path.join(args.data, "drifter.csv")
    with open(fn, "w") as fp:
        txt = r.text
        logger.info("Saving %s bytes to %s", len(txt), fn)
        fp.write(txt)
