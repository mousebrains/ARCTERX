#! /usr/bin/env python3
#
# Read datagrams from one port and forward them to another host/port
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import socket

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--listen", type=int, default=10034, help="UDP port to listen to")
parser.add_argument("--ipv4", type=str, default="100.124.34.2",
        help="IP address to send datagrams to")
parser.add_argument("--port", type=int, default=8982, help="UDP port to send datagrams to")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind(("", args.listen))
    while True:
        (data, senderAddr) = s.recvfrom(1024)
        index = data.find(b"!")
        if index < 0:
            index = data.find(b"$")
            if index < 0:
                logger.info("Dropping %s", data)
                continue
        try:
            logger.info("Received %s", str(data[index:], "UTF-8").strip())
            s.sendto(data[index:].strip(), (args.ipv4, args.port))
        except:
            logger.exception("Unable to send %s", data)
