#! /usr/bin/env python3
#
# Read AIS records from a database, 
# then spit them out to either a UDP port or a PseudoTTY serial device
#
# - sqlite3
# - psycopg3
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils import Logger
import logging
import time
import socket
import pty # PsuedoTTY
import os
import sqlite3
try: # See if this system has psycopg installed
    import psycopg
    qPSQL = True
except:
    qPSQL = False

def process(cur, args:ArgumentParser, sql, sock:socket.socket, master, addr:tuple) -> None:
    tPrev = None
    tSent = None
    cnt = 0
    for row in cur.execute(sql):
        (t, data) = row
        if tPrev:
            dt = (t - tPrev) / args.rate - (time.time() - tSent) # How long to sleep
            if dt > 0: # Sleep for a bit
                logging.debug("Sleeping for %s seconds between messages", dt)
                time.sleep(dt)
        logging.debug("Sending %s", data)
        if sock:
            sock.sendto(data, addr)
        else: # psuedotty
            os.write(master, data)
        tSent = time.time()
        tPrev = t

# Construct command line arguments
parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_argument_group(description="Replay related options")
grp.add_argument("--rate", type=float, default=1,
        help="Replay speed up factor compared to what is in the database")
grp.add_argument("--table", type=str, default="Raw", help="Database table name to read data from")
grp.add_argument("--count", type=int, help="Number of records to replay")
grp.add_argument("--skip", type=int, help="Number of rows to skip")
grp.add_argument("--delay", type=float,
        help="Number of seconds to delay before sending the first record")
grp.add_argument("--repeat", type=int, default=1, help="Repeat rows sent this many times")
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--port", type=int, help="UDP port number to send datagrams to")
grp.add_argument("--serial", action="store_true", help="Send messages via a pseudoTTY device")
grp = parser.add_argument_group(description="UDP related options")
grp.add_argument("--address", type=str, default="127.0.0.1",
        help="IP address to send UDP datagrams to")
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--sqlite3", type=str, help="SQLite3 database filename")
if qPSQL:
    grp.add_argument("--postgresql", type=str, help="PostgreSQL database name")
args = parser.parse_args()

# Initialize the root level logger
Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s") 
logging.info("Args %s", args)

if not qPSQL:
    logging.debug("psycopg3 was not found")

if args.serial: # Send via a PsuedoTTY device
    sock = None
    addr = None
    (master, slave) = pty.openpty() # Create a psuedoTTY device pair
    logging.info("Serial device name %s", os.ttyname(slave))
    print("Sending to serial device", os.ttyname(slave))
    if not args.delay or (args.delay < 1): args.delay = 10 # Wait 10 seconds
else: # send via UDP datagrams
    master = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Internet/UDP
    addr = (args.address, args.port)

if args.delay is not None and args.delay > 0:
    logging.info("Sleeping for %s seconds", args.delay)
    time.sleep(args.delay)

if args.sqlite3 and args.skip and not args.count:
    parser.error("For --sqlite3 you must specify --count when you specify --skip")

sql = f"SELECT t,msg FROM {args.table} ORDER BY t"
if args.count: sql+= f" LIMIT {args.count}"
if args.skip:  sql+= f" OFFSET {args.skip}"
sql+= ";"

logging.info("SQL %s", sql)

# Open a database connection and then send rows as needed

for repeat in range(min(args.repeat, 1)):
    with sqlite3.connect(args.sqlite3) \
            if args.sqlite3 else \
            psycopg3.connect(args.postgresql) \
            as db:
        process(db.cursor(), args, sql, sock, master, addr)
