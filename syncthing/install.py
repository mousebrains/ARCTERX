#! /usr/bin/env python3
#
# Install syncthing
#
# March-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import subprocess
import os

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

parser = ArgumentParser()
grp = parser.add_argument_group(description="Syncthing configuration options")
grp.add_argument("--user", type=str, help="Username to run syncthing as")
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

if args.user is None:
    args.user = os.getlogin()

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

# --device-id
