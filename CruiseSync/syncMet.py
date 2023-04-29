#! /usr/bin/env python3
#
# Copy ship.nc for Thompson to Sync.ARCTERX/Ship for sending to shore
#
# April-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
import logging
from argparse import ArgumentParser
import os

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--output", type=str, default="~/Sync.ARCTERX/Ship", 
        help="Where ship.nc file is copied to")
parser.add_argument("--met", type=str, default="/mnt/share/TN417/data/ship/ship.nc",
        help="Where shp.nc file is")
args = parser.parse_args()

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.met = os.path.abspath(os.path.expanduser(args.met))
args.output = os.path.abspath(os.path.expanduser(args.output))

outdir = os.path.dirname(args.output)
if not os.path.isdir(outdir):
    logging.info("Creating %s", outdir)
    os.makedirs(outdir, mode=0o755, exist_ok=True)

ofn = os.path.join(args.output, os.path.basename(args.met))

logging.info("Copying %s to %s", args.met, ofn)
with open(args.met, "rb") as ifp, open(ofn, "wb") as ofp:
    ofp.write(ifp.read())
