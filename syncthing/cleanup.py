#! /usr/bin/env python3
#
# Remove all remote devices and non-default folders from the local syncthing
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

def getList(name:str) -> set:
    cmd = (args.syncthing, "cli", "config", name, "list")
    items = set()
    s = subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if s.returncode:
        print("Error executing", cmd)
        print(s)
        sys.exit(1)

    for name in s.stdout.split(b"\n"):
        name = str(name, "utf-8").strip()
        if name: items.add(name)

    return items

def getDevices(args:ArgumentParser) -> set:
    return getList("devices")

def getFolders(args:ArgumentParser) -> set:
    return getList("folders")

parser = ArgumentParser()
parser.add_argument("--toKeep", type=str, action="append", help="Folders to not delete")
grp = parser.add_argument_group(description="Command full paths")
grp.add_argument("--syncthing", type=str, default="/usr/bin/syncthing",
        help="Full path to syncthing")
args = parser.parse_args()

toKeep = set(["default"] if args.toKeep is None else args.toKeep)

myID = myDeviceID(args)

for device in getDevices(args):
    if device == myID: continue # Ignore my own ID
    print("Deleting", device)
    execCmd((args.syncthing, "cli", "config", "devices", device, "delete"))

for folder in getFolders(args):
    if folder in toKeep: continue
    print("Deleting", folder)
    execCmd((args.syncthing, "cli", "config", "folders", folder, "delete"))
