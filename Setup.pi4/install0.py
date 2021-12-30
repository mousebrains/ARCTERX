#! /usr/bin/env python3
#
# Designed to setup a new system
#
# Dec-2021, Pat Welch, pat@mousebrains.com

import argparse
import socket

def checkIP(ip:str) -> None:
    port = 22 # SSH port
    print("Building a socket")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Connecting to", ip, "port", port)
    s.connect((ip, port)) # Build a connection to 
    print("Shutting down")
    s.shutdown() # Close the connection
    print("Closing")
    s.close() # Close the connection
    print("Exiting")

parser = argparse.ArgumentParser()
parser.add_argument("--ip", type=str, meta="10.0.4.5", require=True,
        help="IP Address of the new system to setup")
parser.add_argument("--hostname", type=str, meta="rev0", require=True,
        help="hostname, without domain, of the new host")
parser.add_argument("--username", type=str, default="pat",
        help="username to configure")
args = parser.parse_args()

checkIP(args.ip)
