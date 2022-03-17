#! /usr/bin/env python3
#
# Install a service for the KFC's data harvester
#
# Feb-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
from tempfile import NamedTemporaryFile
import os
import sys

parser = ArgumentParser()
parser.add_argument("--service", type=str, action="append", help="Service file(s)")
parser.add_argument("--timer", type=str, action="append", help="Timer file(s)")
parser.add_argument("--serviceDirectory", type=str, default="/etc/systemd/system",
        help="Where to copy service and timer files to")
parser.add_argument("--systemctl", type=str, default="/usr/bin/systemctl",
        help="systemctl executable")
parser.add_argument("--cp", type=str, default="/usr/bin/cp",
        help="cp executable")
parser.add_argument("--sudo", type=str, default="/usr/bin/sudo",
        help="sudo executable")
args = parser.parse_args()

if args.service is None:
    args.service = ["Copernicus.service", "earthdata.service"]

if args.timer is None:
    args.timer = ["Copernicus.timer", "earthdata.timer"]

root = os.path.abspath(os.path.expanduser(args.serviceDirectory))

for service in args.service:
    fn = os.path.join(root, os.path.basename(service))
    print("Writing to", fn)
    subprocess.run((args.sudo, args.cp, service, fn), shell=False, check=True)

for timer in args.timer:
    fn = os.path.join(root, os.path.basename(timer))
    print("Writing to", fn)
    subprocess.run((args.sudo, args.cp, timer, fn), shell=False, check=True)

print("Forcing reload of daemon")
subprocess.run((args.sudo, args.systemctl, "daemon-reload"), shell=False, check=True)

print(f"Enabling {args.service} {args.timer}")
cmd = [args.sudo, args.systemctl, "enable"]
cmd.extend(args.service)
cmd.extend(args.timer)
subprocess.run(cmd, shell=False, check=True)

print(f"Starting {args.timer}")
cmd = [args.sudo, args.systemctl, "start"]
cmd.extend(args.timer)
subprocess.run(cmd, shell=False, check=True)

print(f"Status {args.service} and {args.timer}")
cmd = [args.sudo, args.systemctl, "--no-pager", "status"]
cmd.extend(args.service)
cmd.extend(args.timer)
subprocess.run(cmd, shell=False, check=False)

print(f"List timer {args.timer}")
cmd = [args.sudo, args.systemctl, "--no-pager", "list-timers"]
cmd.extend(args.timer)
subprocess.run(cmd, shell=False, check=True)
