#! /usr/bin/env python3
#
# Update a fresh copy of the glider files
# Harvest the log files into NetCDF files
# Harvest the s?d and t?d files into NetCDF files
# Combine the harvested information into a NetCDF file for distribution
#
# June-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
from TPWUtils import Logger
import logHarvest
from mkCombined import mkCombo
import logging
import glob
import os
import sys

def myMkDir(directory:str) -> None:
    if os.path.isdir(directory): return
    logging.info("Creating %s", directory)
    os.makedirs(directory, mode=0o755, exist_ok=True) # exist_ok for race conditions

def runCmd(cmd, returnCodes:tuple=(0,)) -> bool:
    logging.debug("cmd %s", cmd)
    a = subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if a.returncode in returnCodes:
        if a.stdout:
            logging.debug("Ran %s", " ".join(cmd))
            try:
                logging.debug("%s", str(a.stdout, "UTF-8"))
            except:
                logging.debug("%s", a.stdout)
        return True

    if a.stdout:
        logging.info("Ran %s", " ".join(cmd))
        try:
            logging.info("%s", str(a.stdout, "UTF-8"))
        except:
            logging.info("%s", a.stdout)
    return False

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--hostname", type=str, default="fs2", help="Hostname to rsync from")
parser.add_argument("--src", type=str, action="append", help="Input source for rsync")
parser.add_argument("--rsync", type=str, default="/usr/bin/rsync", help="rsync path")
parser.add_argument("--dbd2netCDF", type=str, default="/usr/local/bin/dbd2netCDF",
                    help="dbd2netCDF path")
parser.add_argument("--glider", type=str, action="append", help="Glider(s) to process")
parser.add_argument("--t0", type=str, default="20230527T000000",
                    help="Earliest time to consider in logfiles")
parser.add_argument("--tgt", type=str, default="gliders", help="Output directory for rsync")
parser.add_argument("--output", type=str, default="data",
                    help="Output directory for log/sbd/tbd NetCDF files")
parser.add_argument("--combo", type=str, default="~/mnt/GDrive/OSU_glider",
                    help="Output directory for combined NetCDF files")
args = parser.parse_args()

if args.glider is None:
    args.glider = ("osu684", "osu685", "osu686")

if args.src is None:
    args.src = (
            f"{args.hostname}:/data/Dockserver/gliderfmc0/osu68?",
            f"{args.hostname}:/data/tpw/cache",
            )

args.rsync = os.path.abspath(os.path.expanduser(args.rsync))
args.dbd2netCDF = os.path.abspath(os.path.expanduser(args.dbd2netCDF))
args.tgt = os.path.abspath(os.path.expanduser(args.tgt))
args.output = os.path.abspath(os.path.expanduser(args.output))
args.combo = os.path.abspath(os.path.expanduser(args.combo))

Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

try:
    myMkDir(args.tgt)
    myMkDir(args.output)
    myMkDir(args.combo)

    cmdBase = [args.rsync, "--compress", "--archive", "--delete"]
    if args.verbose or args.debug: cmdBase.append("--verbose")
    for src in args.src:
        cmd = list(cmdBase) # Make a local copy
        cmd.extend([src, args.tgt])
        if not runCmd(cmd): sys.exit(1)

    logHarvest.processFiles(
            glob.glob(os.path.join(args.tgt, "*/logs/*.log")),
            args.t0,
            os.path.join(args.output, "log.nc"))

    cmdBase = [args.dbd2netCDF, "--repair", "--skipFirst",
               "--cache", os.path.join(args.tgt, "cache")]
    if args.verbose or args.debug: cmdBase.append("--verbose")
    cmdBase.append("--output")

    for glider in args.glider:
        log = os.path.join(args.output, f"log.nc")
        flt = os.path.join(args.output, f"flt.{glider}.nc")
        sci = os.path.join(args.output, f"sci.{glider}.nc")
        logging.info("Working on %s", glider)
        cmd = list(cmdBase)
        cmd.append(flt)
        cmd.extend(glob.glob(os.path.join(args.tgt, glider, "from-glider", "*.s?d")))
        if not runCmd(cmd): sys.exit(3)
        cmd = list(cmdBase)
        cmd.append(sci)
        cmd.extend(glob.glob(os.path.join(args.tgt, glider, "from-glider", "*.t?d")))
        if not runCmd(cmd): sys.exit(4)

        mkCombo(glider, 
                os.path.join(args.combo, f"{glider}.nc"),
                log, flt, sci)
except:
    logging.exception("Unexpected exception, %s", args)
