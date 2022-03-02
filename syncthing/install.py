#! /usr/bin/env python3
#
# Install syncthing
#
# March-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
import os
import socket
import time
import sys

def execCmd(cmd:tuple[str], inputText:bytes=None, qIgnoreOutput:bool=False) -> None:
    if isinstance(inputText, str):
        inputText = bytes(inputText, "utf-8")

    s = subprocess.run(cmd, input=inputText, shell=False, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if not qIgnoreOutput and s.stdout:
        try:
            print(str(s.stdout, "utf-8"))
        except:
            print(s.stdout)
    return s.stdout

def myDeviceID(args:ArgumentParser) -> str:
    deviceID = execCmd([args.syncthing, "--device-id"], qIgnoreOutput=True)
    try:
        return str(deviceID, "utf-8").strip()
    except:
        print("Unable to convert deviceID to a string", deviceID)
        sys.exit(1)

def installSyncthing(args:ArgumentParser) -> str:
    if args.noinstall: # I'm not going to install anything, so just get the deviceID
        return myDeviceID(args)

    print("Installing syncthing with user", args.user)

    # Get the PGP key and install it
    execCmd([args.sudo, args.curl, "--silent",
        "--output", "/usr/share/keyrings/syncthing-archive-keyring.gpg",
        "https://syncthing.net/release-key.gpg"])

    # Add the syncthing repository to known repositories
    execCmd([args.sudo, args.tee, "/etc/apt/sources.list.d/syncthing.list"],
        inputText="deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable",
        qIgnoreOutput=True)

    # Update the repository lists
    execCmd([args.sudo, args.apt, "update"])

    # Install syncthing
    execCmd([args.sudo, args.apt, "install", "syncthing"])

    # Enable the syncthing for this user
    execCmd([args.sudo, args.systemctl, "enable", f"syncthing@{args.user}.service"])

    # Start the syncthing for this user
    execCmd([args.sudo, args.systemctl, "start", f"syncthing@{args.user}.service"])

    deviceID = myDeviceID(args)

    hostname = socket.gethostname()
    fn = f"deviceID.{hostname}"
    print("Writing device ID to", fn)
    with open(fn, "w") as fp: fp.write(deviceID + "\n")

    return deviceID

def getFolders(args:ArgumentParser) -> set:
    known = set()
    s = subprocess.run((args.syncthing, "cli", "config", "folders", "list"),
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if s.returncode:
        print("Error getting folders")
        print(s)
        sys.exit(1)

    for name in s.stdout.split(b"\n"):
        name = str(name, "utf-8").strip()
        if name: known.add(name)

    return known

def mkFolder(name:str, typeName:str, args:ArgumentParser) -> None:
    cmd = [args.syncthing, "cli", "config", "folders", "add",
            "--id", name,
            "--label", name,
            "--path", os.path.abspath(os.path.join(os.path.expanduser(args.folderRoot), name)),
            "--type", typeName,
            "--order", "random",
            "--deprecated-min-disk-free-pct", "10",
            ]
    s = subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if s.returncode:
        print("Error making", name)
        print(s)
        sys.exit(1)

def makeFolders(args:ArgumentParser) -> None:
    knownFolders = getFolders(args)

    for name in args.folderShip:
        if name in knownFolders:
            print("Skipping shore side ship folder", name)
        else:
            print("Making shore side ship folder", name)
            mkFolder(name, "receiveonly" if args.shore else "sendonly", args)
    for name in args.folderShore:
        if name in knownFolders:
            print("Skipping shore side shore folder", name)
        else:
            print("Making shore side shore folder", name)
            mkFolder(name, "sendonly" if args.shore else "receiveonly", args)
    
def updatePeer(myID:str, peerName:str, args:ArgumentParser) -> None:
    fn = f"deviceID.{peer}"
    if not os.path.isfile(fn):
        print(f"Device ID file for {peer} not found, {fn}")
        return False
    with open(fn, "r") as fp: peerID = fp.read().strip()
    cmd = [args.syncthing, "cli", "config", "devices", "add",
            "--device-id", peerID,
            "--name", peer,
            ]
    if args.compression: cmd.extend(["--compression", args.compression])
    if args.kbpsSend > 0: cmd.extend(["--max-send-kbps", str(args.kbpsSend)])
    if args.kbpsRecv > 0: cmd.extend(["--max-recv-kbps", str(args.kbpsRecv)])
    if args.kibsRequest > 0: cmd.extend(["--max-request-kib", str(args.kibsRequest)])
    print(" ".join(cmd))
    execCmd(cmd)

parser = ArgumentParser()
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--ship", action="store_true", help="This is a ship side server")
grp.add_argument("--shore", action="store_true", help="This is a shore side server")

grp = parser.add_argument_group(description="Program flow options")
grp.add_argument("--noinstall", action="store_true", help="Don't do installation step")
grp.add_argument("--nofolder", action="store_true", help="Don't do folder step")
grp.add_argument("--nodevice", action="store_true", help="Don't do device step")

grp = parser.add_argument_group(description="Folders to sync related options")
grp.add_argument("--folderRoot", type=str, required=True, help="Root to place sync folders in")
grp.add_argument("--folderShip", type=str, action="append", help="Ship's subdirectory(s) to sync")
grp.add_argument("--folderShore", type=str, action="append", help="Shore's subdirectory(s) to sync")

grp = parser.add_argument_group(description="Syncthing configuration options")
grp.add_argument("--user", type=str, help="Username to run syncthing as")
grp.add_argument("--peer", type=str, action="append", help="Peers to sync with")
grp.add_argument("--kbpsSend", type=int, default=0, help="Maximum send rate, kilobytes/sec")
grp.add_argument("--kbpsRecv", type=int, default=0, help="Maximum receive rate, kilobytes/sec")
grp.add_argument("--kibsRequest", type=int, default=0, help="Maximum request pending, kilobytes")
grp.add_argument("--compression", type=str, default="metadata",
        choices=("metadata", "always", "never"), help="Type of data to compress")
grp = parser.add_argument_group(description="Command full paths")
grp.add_argument("--sudo", type=str, default="/usr/bin/sudo", help="Full path to sudo")
grp.add_argument("--curl", type=str, default="/usr/bin/curl", help="Full path to curl")
grp.add_argument("--echo", type=str, default="/usr/bin/echo", help="Full path to echo")
grp.add_argument("--tee", type=str, default="/usr/bin/tee", help="Full path to tee")
grp.add_argument("--apt", type=str, default="/usr/bin/apt", help="Full path to apt")
grp.add_argument("--systemctl", type=str, default="/usr/bin/systemctl",
        help="Full path to systemctl")
grp.add_argument("--syncthing", type=str, default="/usr/bin/syncthing",
        help="Full path to syncthing")
args = parser.parse_args()

if args.user is None: args.user = os.getlogin()
if args.folderShip is None: args.folderShip = ["Ship"]
if args.folderShore is None: args.folderShore = ["Shore"]

deviceID = installSyncthing(args)

if not args.nofolder: # Set up the folders
    makeFolders(args)

if not args.nodevice and args.peer:
    for peer in args.peer:
        if not updatePeer(deviceID, peer, args):
            sys.exit(1)
