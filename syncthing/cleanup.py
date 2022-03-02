#! /usr/bin/env python3
#
# Remove all remote devices and non-default folders from the local syncthing
#
# March-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
import shutil
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
        raise Exception(f"Unable to convert deviceID to a string {deviceID}")

def getList(cmd:tuple[str]=None, name:str=None) -> set:
    if cmd is None:
        if name is None: raise Exception("You must specify either cmd or name")
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
    return getList(name="devices")

def getFolders(args:ArgumentParser) -> set:
    return getList(name="folders")

parser = ArgumentParser()
parser.add_argument("--dryrun", action="store_true", help="Don't actually delete anything")
parser.add_argument("--remove", action="store_true", help="Remove data folders")
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
    if not args.dryrun:
        execCmd((args.syncthing, "cli", "config", "devices", device, "delete"))

for folder in getFolders(args):
    if folder in toKeep: continue
    paths = set() # Paths to be deleted, maybe
    if args.remove: # Going to delete the underlying data
        if shutil.rmtree.avoids_symlink_attacks:
            paths = getList(cmd=(args.syncthing, "cli", "config", "folders", folder, "path", "get"))
        else:
            print("Not removing since symlink attacks can not be avoided")

    print("Deleting", folder)
    if not args.dryrun:
        execCmd((args.syncthing, "cli", "config", "folders", folder, "delete"))

    for path in paths:
        print("Removing", path)
        if not args.dryrun: shutil.rmtree(path, ignore_errors=True)
