#! /usr/bin/env python3
#
# Install a service for the ripping out of DB into a CSV file
#
# Feb-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
from tempfile import NamedTemporaryFile
import os
import sys

parser = ArgumentParser()
parser.add_argument("--service", type=str, default="shipDB2CSV.service", help="Service file")
parser.add_argument("--serviceDirectory", type=str, default="/etc/systemd/system",
        help="Where to copy service file to")
parser.add_argument("--systemctl", type=str, default="/usr/bin/systemctl",
        help="systemctl executable")
parser.add_argument("--cp", type=str, default="/usr/bin/cp",
        help="cp executable")
parser.add_argument("--sudo", type=str, default="/usr/bin/sudo",
        help="sudo executable")
args = parser.parse_args()

root = os.path.abspath(os.path.expanduser(args.serviceDirectory))

fn = os.path.join(root, os.path.basename(args.service))
print("Writing to", fn)
subprocess.run((args.sudo, args.cp, args.service, fn), shell=False, check=True)

print("Forcing reload of daemon")
subprocess.run((args.sudo, args.systemctl, "daemon-reload"), shell=False, check=True)

print(f"Enabling {args.service}")
subprocess.run((args.sudo, args.systemctl, "enable", args.service), shell=False, check=True)

print(f"Starting {args.service}")
subprocess.run((args.sudo, args.systemctl, "start", args.service), shell=False, check=True)

print(f"Status {args.service}")
s = subprocess.run((args.sudo, args.systemctl, "--no-pager", "status", args.service),
        shell=False, check=False)
