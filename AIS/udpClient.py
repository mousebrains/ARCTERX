#! /usr/bin/env python3
#
# A client to receive UDP datagrams and store them in a file
#
# Jan-2022, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import socket
from TPWUtils import Logger
import logging

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--port", type=int, required=True, help="UDP port to listen to")
parser.add_argument("--size", type=int, default=65535, help="UDP datagram size")
parser.add_argument("--output", type=str, help="File to write JSON datagrams to")
args = parser.parse_args()

Logger.mkLogger(args)

sz = args.size

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind(('', args.port)) # From anywhere to port
    logging.info("Bound to port %s", args.port)
    fp = open(args.output, "wb") if args.output else None
    try:
        while True:
            (data, senderAddr) = s.recvfrom(sz)
            logging.debug("%s -> %s", senderAddr, data)
            if fp:
                fp.write(data)
                fp.write(b"\n")
                fp.flush()
    except:
        logging.exception("Error while reading socket")
    finally:
        if fp: fp.close()
