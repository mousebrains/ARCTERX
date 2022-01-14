#! /usr/bin/env python3
#
# Designed to setup a new system
#
# Dec-2021, Pat Welch, pat@mousebrains.com

import argparse
import socket
import logging
import sys
import subprocess

def checkIP(ip:str) -> None:
    try:
        port = 22 # SSH port
        dt = 10 # Timeout after 2 seconds
        logging.info("Attempting to connect to %s:%s, timeout %s seconds", ip, port, dt)
        s = socket.create_connection((ip, port), timeout=dt) # Build a connection to 
        s.shutdown(socket.SHUT_RDWR) # nicely shut the connection down
        s.close() # Close the connection
    except:
        logging.exception("Unable to connect to %s", ip)
    sys.exit(1)

def ssh(username:str, hostname:str, password:str) -> bool:
    pass

parser = argparse.ArgumentParser()
parser.add_argument("--ip", type=str, metavar="10.0.4.5", required=True,
        help="IP Address of the new system to setup")
parser.add_argument("--hostname", type=str, metavar="rev0", required=True,
        help="hostname, without domain, of the new host")
parser.add_argument("--username", type=str, default="pat",
        help="username to configure")
grp = parser.add_mutually_exclusive_group()
grp.add_argument("--verbose", action="store_true", help="Enable INFO messages")
grp.add_argument("--debug", action="store_true", help="Enable INFO+DEBUG messages")
args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.INFO)
elif args.debug:
    logging.basicConfig(level=logging.DEBUG)

checkIP(args.ip) # If we get past here, the host is up


