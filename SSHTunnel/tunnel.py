#! /usr/bin/env python3
#
# Build a ssh connection to a target and add a tunnel back to my local ssh port
# 
# Jan-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
import logging
import time
import sys
from TPWUtils import Logger

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_argument_group(description="SSH related options")
grp.add_argument("--ssh", type=str, default="/usr/bin/ssh", help="SSH binary to use")
grp.add_argument("--interval", type=int, default=60, help="Value to set ServerAliveInterval to")
grp.add_argument("--count", type=int, default=3, help="Value to set ServerAliveCountMax to")
grp.add_argument("--identity", type=str, help="Public key filename")
grp.add_argument("--username", type=str, help="Remote username")
grp.add_argument("--host", type=str, required=True, help="Remote hostname")
grp.add_argument("--port", type=int, help="Remote host port to connect to")
grp.add_argument("--remotePort", type=int, help="Remote Port Number")
grp.add_argument("--localPort", type=int, default=22, help="Local Port Number")
grp.add_argument("--localHost", type=str, default="localhost", help="Local host to forward to")
grp.add_argument("--retries", type=int, default=1, help="Number of dropped connections to retry")
grp.add_argument("--delay", type=float, default=60, help="Number of seconds between retry attempts")
args = parser.parse_args()

Logger.mkLogger(args)

cmd = [args.ssh, "-N", "-x", "-T"]

if args.identity:
    cmd.extend(("-i", args.identity))

if args.interval > 0:
    cmd.extend(("-o", f"ServerAliveInterval={args.interval}"))
    if args.count > 0:
        cmd.extend(("-o", f"ServerAliveCountMax={args.count}"))

if args.remotePort:
    cmd.extend(("-R", f"{args.remotePort}:{args.localHost}:{args.localPort}"))

if args.username:
    cmd.extend(("-l", args.username))

if args.port:
    cmd.extend(("-p", args.port))

cmd.append(args.host)

logging.info("Command: %s", " ".join(cmd))

for retry in range(args.retries): # Number of times to retry an attempt
    logging.info("Starting, retry %s of %s", retry, args.retries)
    try:
        s = subprocess.run(
                cmd,
                capture_output=True,
                shell=False,
                )
        logging.warning("\n%s", s)
    except:
        logging.exception("Error in %s", cmd)

    if (args.delay > 0) and ((retry + 1) < args.retries):
        logging.info("Sleeping %s seconds before the next connection attempt", args.delay)
        time.sleep(args.delay)

logging.info("Exceeded maximum number of retries, %s", args.retries)
sys.exit(0)
