#! /usr/bin/env python3
#
# Install webserver and configure it for ship board use
#
# March-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
import datetime
import os
import grp as group
import re
from tempfile import NamedTemporaryFile
import sys

def execCmd(cmd:tuple[str], inputText:bytes=None, qIgnoreOutput:bool=False) -> None:
    if isinstance(inputText, str):
        inputText = bytes(inputText, "utf-8")

    s = subprocess.run(cmd, input=inputText, shell=False, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if s.returncode: # Instead of check=True
        try:
            print("ERROR executing", " ".join(cmd))
            print("Return code", s.returncode)
            print(str(s.stdout, "utf-8"))
            sys.exit(1)
        except Exception as e:
            raise e

    if not qIgnoreOutput and s.stdout:
        try:
            print(str(s.stdout, "utf-8"))
        except:
            print(s.stdout)
    return s.stdout

def setupRoot(args:ArgumentParser) -> None:
    rootDir = os.path.abspath(os.path.expanduser(args.root))
    os.makedirs(rootDir, mode=0o755, exist_ok=True)
    with open("index.php", "rb") as ifp, open(os.path.join(rootDir, "index.php"), "wb") as ofp:
        ofp.write(ifp.read())

def siteFile(args:ArgumentParser) -> int:
    fn = os.path.join(args.nginxRoot, "sites-available", os.path.basename(args.siteFile))
    enableDir = os.path.join(args.nginxRoot, "sites-enabled")
    fnEnabled = os.path.join(enableDir, os.path.basename(fn))

    rootDir = os.path.abspath(os.path.expanduser(args.root))

    content = ""
    with open(args.siteFile, "r") as fp:
        for line in fp.readlines():
            content += re.sub(r"@ROOT@", rootDir, line)

    if not args.force and os.path.isfile(fn) and \
            os.path.islink(fnEnabled) and (os.path.abspath(os.readlink(fnEnabled)) == fn):
        with open(fn, "r") as fp: original = fp.read()
        if content == original: return 0

    print("Updating", fn)
    with NamedTemporaryFile("w") as fp:
        fp.write(content)
        fp.flush()
        execCmd((args.sudo, args.cp, fp.name, fn)) # Copy as root
        execCmd((args.sudo, args.chmod, "0644", fn)) # Make world readable

    cmd = [args.sudo, args.rm, "-f"]
    for name in os.listdir(enableDir): cmd.append(os.path.join(enableDir, name))
    execCmd(cmd)
    execCmd((args.sudo, args.ln, "-s", fn, enableDir))
    execCmd((args.sudo, args.nginx, "-t"))
    return 1

def nginxConfig(args:ArgumentParser) -> int:
    fn = os.path.join(args.nginxRoot, "nginx.conf")
    original = ""
    content = ""
    with open(fn, "r") as fp:
        for line in fp.readlines():
            original += line
            content += re.sub(r"\s*user\s+[\w-]+;", f"user {args.user};", line)
    if not args.force and (content == original): return 0 # No need to update
    print("Updating", fn)
    with NamedTemporaryFile("w") as fp:
        fp.write(content)
        fp.flush()
        date = datetime.date.today().strftime("%Y%m%d")
        execCmd((args.sudo, args.cp, fn, fn + "." + date))  # Make a dated backup copy
        execCmd((args.sudo, args.cp, fp.name, fn)) # Copy as root
        execCmd((args.sudo, args.chmod, "0644", fn)) # Make world readable
    execCmd((args.sudo, args.nginx, "-t"))
    return 1

def phpfpmConfig(args:ArgumentParser) -> None:
    fn = os.path.join(args.phpRoot, "pool.d", "www.conf")
    content = ""
    original = ""
    with open(fn, "r") as fp:
        for line in fp.readlines():
            original += line
            line = re.sub(r"^\s*(user|listen.owner)\s*=\s*[\w-]+\s*$",
                    r"\1 = " + args.user + "\n", line)
            line = re.sub(r"^\s*(group|listen.group)\s*=\s*[\w-]+\s*$",
                    r"\1 = " + args.group + "\n", line)
            content += line
    if not args.force and (content == original): return # Nothing to be updated
    print("Updating", fn)
    with NamedTemporaryFile("w") as fp:
        fp.write(content)
        fp.flush()
        execCmd((args.sudo, args.cp, fp.name, fn)) # Copy as root
        execCmd((args.sudo, args.chmod, "0644", fn)) # Make world readable

    execCmd((args.sudo, args.systemctl, "restart", args.phpService))
    execCmd((args.sudo, args.systemctl, "--no-pager", "status", args.phpService))

parser = ArgumentParser()
parser.add_argument("--force", action="store_true", help="Force updating files")
grp = parser.add_argument_group(description="Program flow options")
grp.add_argument("--noinstall", action="store_true", help="Don't do installation step")
grp.add_argument("--nosite", action="store_true", help="Don't do site file step")
grp.add_argument("--noconfig", action="store_true", help="Don't do config step")
grp.add_argument("--nophpconfig", action="store_true", help="Don't do php config step")

grp = parser.add_argument_group(description="configuration options")
grp.add_argument("--user", type=str, help="Username to run webserver as")
grp.add_argument("--group", type=str, help="Group to run webserver as")
grp.add_argument("--root", type=str, default="~/public_html", help="web server root")
grp.add_argument("--siteFile", type=str, default="arcterx", help="web server sitec configuration")
grp.add_argument("--nginxRoot", type=str, default="/etc/nginx", help="NGINX configuraton directory")
grp.add_argument("--nginxService", type=str, default="nginx.service",
        help="systemctl nginx fpm service name")
grp.add_argument("--phpRoot", type=str, default="/etc/php/8.1/fpm", 
        help="php-fpm configuraton directory")
grp.add_argument("--phpService", type=str, default="php8.1-fpm.service",
        help="systemctl php fpm service name")
grp = parser.add_argument_group(description="Command full paths")
grp.add_argument("--sudo", type=str, default="/usr/bin/sudo", help="Full path to sudo")
grp.add_argument("--cp", type=str, default="/usr/bin/cp", help="Full path to cp")
grp.add_argument("--chmod", type=str, default="/usr/bin/chmod", help="Full path to chmod")
grp.add_argument("--ln", type=str, default="/usr/bin/ln", help="Full path to ln")
grp.add_argument("--rm", type=str, default="/usr/bin/rm", help="Full path to rm")
grp.add_argument("--tee", type=str, default="/usr/bin/tee", help="Full path to tee")
grp.add_argument("--apt", type=str, default="/usr/bin/apt-get", help="Full path to apt-get")
grp.add_argument("--systemctl", type=str, default="/usr/bin/systemctl",
        help="Full path to systemctl")
grp.add_argument("--nginx", type=str, default="/usr/sbin/nginx", help="Full path to nginx")
args = parser.parse_args()

if args.user is None: args.user = os.getlogin()
if args.group is None:
    (rgid, egid, sgid) = os.getresgid()
    args.group = group.getgrgid(rgid).gr_name

if not args.noinstall: # Install nginx, php-fpm, ...
    execCmd((args.sudo, args.apt, "--assume-yes", "install", "nginx", "php-fpm"))

setupRoot(args)

qNGINX = 0

if not args.nosite: # Set up the site specific file
    qNGINX += siteFile(args)

if not args.noconfig: # Configure the main configuration file
    qNGINX += nginxConfig(args)

if not args.nophpconfig: # Configure php-fpm
    phpfpmConfig(args)

if qNGINX:
    execCmd((args.sudo, args.nginx, "-t")) # Check the configuration is okay
    execCmd((args.sudo, args.systemctl, "restart", args.nginxService))
    execCmd((args.sudo, args.systemctl, "--no-pager", "status", args.nginxService))

