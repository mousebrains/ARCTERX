#! /usr/bin/env python3
#
# Listen to a UDP port or serial device for datagrams, 
# then forward copies to various consumers.
# The current consumers include:
#  - Write each raw datagram to a database.
#  - Split each datagram into raw NEMA sentences.
#    For each raw NEMA sentence the following are options:
#    -- Write each raw NEMA sentence to a database.
#    -- Integrity check the raw NEMA sentence and split it into fields.
#       For each valid NEMA sentence the following are options:
#       --- Write each split validated NEMA sentence to a database.
#       --- Build AIS payloads for multipart messages and then decrypt them.
#           For each decrypted AIS message the following are options:
#           ---- Write the full AIS payload to a database
#           ---- Write the decrypted AIS message in JSON format to a database.
#           ---- Send the decrypted AIS message in JSON format to host UDP ports.
#
# Possible special packages you might need to install:
#
# - libais
# - pyserial
# - sqlite3
# - psycopg3
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils import Logger
from TPWUtils.Thread import Thread
from AIS.Reader import Reader
from AIS.Raw2DB import Raw2DB
from AIS.Decrypter import Decrypter
from AIS.AIS2DB import AIS2DB
from AIS.AIS2UDP import AIS2UDP
from AIS.AIS2CSV import AIS2CSV
from AIS.Accumulator import Accumulator
import logging

# Construct command line arguments
parser = ArgumentParser()
Logger.addArgs(parser)
Reader.addArgs(parser)
Raw2DB.addArgs(parser)
Decrypter.addArgs(parser)
AIS2DB.addArgs(parser)
AIS2UDP.addArgs(parser)
AIS2CSV.addArgs(parser)
Accumulator.addArgs(parser)
args = parser.parse_args()

Logger.mkLogger(args) # Initialize the root level logger
logging.info("Args %s", args)

try:
    rdr = Reader(args)
    decrypt = Decrypter(args)
    accumulator = Accumulator(args)

    for item in (
            (AIS2DB, decrypt), 
            (AIS2UDP, accumulator),
            (AIS2CSV, decrypt),
            (Raw2DB, rdr)):
        if not item[0].qUse(args): continue
        thrd = item[0](args)
        item[1].queue(thrd)
        thrd.start()

    if accumulator.qUse():
        decrypt.queue(accumulator)
        accumulator.start()
    else:
        accumulator = None # Free up resources
        
    if decrypt.qUse():
        rdr.queue(decrypt)
        decrypt.start()
    else:
        decrypt = None # Free up resources

    rdr.start() # Start the reader thread last

    Thread.waitForException() # This will only raise an exception from a thread
except:
    logging.exception("Unexpected exception while listening")
