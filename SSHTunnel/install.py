#! /usr/bin/env python3
#
# Install a service for the SSH tunnel from this machine to shore
# so somebody on shore can log into the shipboard machine.
#
# Feb-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
from tempfile import NamedTemporaryFile
import yaml
import socket
import os
import re
import time
import sys

def barebones(content:str) -> list[str]:
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if (len(line) == 0) or (line[0] == "#"): continue
        lines.append(line)
    return lines

parser = ArgumentParser()
parser.add_argument("--template", type=str, default="SSHtunnel.template",
        help="Service template file to generate local service file from")
parser.add_argument("--service", type=str, default="SSHtunnel", help="Service name")
parser.add_argument("--serviceDirectory", type=str, default="/etc/systemd/system",
        help="Where to copy service file to")
grp = parser.add_argument_group(description="Service file translation related options")
grp.add_argument("--hostname", type=str, default="arcterx", help="Remote hostname")
grp.add_argument("--port", type=int, help="Port number on remote host")
grp.add_argument("--username", type=str, help="Local user to run service as")
grp.add_argument("--group", type=str, help="Local group to run service as")
grp.add_argument("--logfile", type=str, default="SSHtunnel.log",
        help="Local logfile directory")
grp.add_argument("--directory", type=str, help="Directory to change to for running the service")
grp.add_argument("--restartSeconds", type=int, default=300,
        help="Time before restarting the service after the previous instance exits")
grp.add_argument("--executable", type=str, default="tunnel.py",
        help="Executable name to be executed by service")
parser.add_argument("--force", action="store_true", help="Force writing a new file")
parser.add_argument("--systemctl", type=str, default="/usr/bin/systemctl",
        help="systemctl executable")
parser.add_argument("--cp", type=str, default="/usr/bin/cp", help="cp executable")
parser.add_argument("--chmod", type=str, default="/usr/bin/chmod", help="chmod executable")
parser.add_argument("--sudo", type=str, default="/usr/bin/sudo", help="sudo executable")
parser.add_argument("--knownHosts", type=str, help="Known host to port dictionary YAML file")
args = parser.parse_args()

root = os.path.dirname(os.path.abspath(__file__))

if args.knownHosts is None:
    args.knownHosts = os.path.join(root, "hostnames.yaml")

with open(args.knownHosts, "r") as fp:
    knownHosts = yaml.safe_load(fp)

hostname = socket.gethostname()

if args.port is None:
    if hostname not in knownHosts:
        parser.error(f"Unknown host, '{hostname}', so you must specify --port")
    args.port = knownHosts[hostname]

if args.service is None:
    args.service = f"SSHtunnel.service.{hostname}"

if args.username is None: # Get this process's username
    args.username = os.getlogin() # Since we may being run vi sudo, getlogin

if args.group is None: # Get this process's group
    args.group = args.username

if args.directory is None: # working directory to move to
    args.directory = os.path.expanduser(f"~{args.username}/logs")

with open(os.path.join(root, args.template), "r") as fp: 
    input = fp.read() # Load the entire template

wd = os.path.abspath(os.path.expanduser(args.directory)) # Working directory

input = re.sub(r"@DATE@", "Generated on " + time.asctime(), input)
input = re.sub(r"@GENERATED@", str(args), input)
input = re.sub(r"@USERNAME@", args.username, input)
input = re.sub(r"@GROUPNAME@", args.group, input)
input = re.sub(r"@DIRECTORY@", wd, input)
input = re.sub(r"@EXECUTABLE@", os.path.join(root, args.executable), input)
input = re.sub(r"@LOGFILE@", args.logfile, input)
input = re.sub(r"@HOSTNAME@", args.hostname, input)
input = re.sub(r"@PORT@", str(args.port), input)
input = re.sub(r"@RESTARTSECONDS@", str(args.restartSeconds), input)

fn = os.path.join(args.serviceDirectory, f"{args.service}.service")

if not args.force and os.path.exists(fn):
    try:
        with open (fn, "r") as fp:
            current = barebones(fp.read()) # Current contents
            proposed = barebones(input) # What we want to write
            if current == proposed:
                print("No need to update, identical")
                sys.exit(0)
    except:
        pass

if not os.path.isdir(wd):
    print("Making", wd)
    os.makedirs(args.directory, mode=0o755)

# Write to a temporary file, then copy as root via sudo
with NamedTemporaryFile(mode="w") as fp:
    fp.write(input)
    fp.flush()
    print("Writing to", fn)
    subprocess.run((args.sudo, args.cp, fp.name, fn), shell=False, check=True)
    subprocess.run((args.sudo, args.chmod, "0644", fn))

print("Forcing reload of daemon")
subprocess.run((args.sudo, args.systemctl, "daemon-reload"), shell=False, check=True)

print(f"Enabling {args.service}")
subprocess.run((args.sudo, args.systemctl, "enable", args.service), shell=False, check=True)

print(f"Starting {args.service}")
subprocess.run((args.sudo, args.systemctl, "restart", args.service), shell=False, check=True)

print(f"Status {args.service}")
s = subprocess.run((args.sudo, args.systemctl, "--no-pager", "status", args.service),
        shell=False, check=True)
