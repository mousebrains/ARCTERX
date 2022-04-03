#! /usr/bin/env python3
#
# Copy ADCP files to Sync.ARCTERX/Ship/ADCP for sending to shore
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import os
import glob
import sys

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--output", type=str, default="~/Sync.ARCTERX/Ship/ADCP", 
        help="Where ADCP files are copied to")
parser.add_argument("--ADCP", type=str,
        default="/mnt/cruise/RR2203/data/adcp/RR2203/proc/os150nb/contour",
        help="Where UH ADCP files are")
parser.add_argument("--files", type=str, action="append", help="Filenames to copy if they exist")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

if args.files is None:
    args.files = ("allbins_depth.mat", "allbins_other.mat", 
            "allbins_u.mat", "allbins_v.mat", "allbins_w.mat",)
args.files = set(args.files)

args.output = os.path.abspath(os.path.expanduser(args.output))
os.makedirs(args.output, mode=0o755, exist_ok=True)

for fn in glob.glob(os.path.join(args.ADCP, "*.mat")):
    if os.path.basename(fn) not in args.files: 
        continue
    ofn = os.path.join(args.output, os.path.basename(fn))
    if os.path.isfile(ofn) and \
            (os.stat(fn).st_mtime < os.stat(ofn).st_mtime) and \
            (os.stat(fn).st_size == os.stat(ofn).st_size):
        logger.info("Skipping %s", fn)
        continue
    logger.info("Making a fresh copy from %s", fn)
    with open(fn, "rb") as ifp, open(ofn, "wb") as ofp:
        ofp.write(ifp.read())
