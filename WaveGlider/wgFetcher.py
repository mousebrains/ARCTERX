#! /usr/bin/env python3
#
# Fetch SIO's wave glider data positions
#
# Mar-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from Credentials import getCredentials
import logging
from argparse import ArgumentParser
from ftplib import FTP
import datetime
import psycopg
import json
import os
import re

class PositionFile:
    def __init__(self, args:ArgumentParser) -> None:
        self.size = 0
        self.__args = args
        self.__regexp = re.compile(
                b"(\d+-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),([+-]?\d+(|[.]\d*)),([+-]?\d+(|[.]\d*))")
        self.__db = psycopg.connect(f"dbname={args.db}")
        self.__createTable()
        self.__sql = f"INSERT INTO {args.table}"
        self.__sql+= "(grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
        self.__sql+= " ON CONFLICT DO NOTHING;"
        self.__name = None
        self.__csvDir = os.path.abspath(os.path.expanduser(args.csvSaveTo))
        if not os.path.isdir(self.__csvDir):
            logging.info("Creating %s", self.__csvDir)
            os.makedirs(self.__csvDir, mode=0o755, exist_ok=True)

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Database related options")
        grp.add_argument("--db", type=str, default="arcterx", help="Database name to work with")
        grp.add_argument("--schema", type=str, default="glider.schema", help="Glider schema")
        grp.add_argument("--table", type=str, default="glider",
                         help="Database table to save data into")
        grp.add_argument("--className", type=str, default="WG", help="Device class")
        grp.add_argument("--csvSaveTo", type=str, default="~/Sync.ARCTERX/Shore/WG")

    def __del__(self):
        if self.__db: self.__db.close()

    def __createTable(self) -> None:
        args = self.__args
        db = self.__db
        cur = db.cursor()
        cur.execute("SELECT EXISTS(SELECT relname FROM pg_class WHERE relname='glider');")
        for row in cur:
            if row[0]: return # Already exists
        fn = os.path.abspath(os.path.expanduser(args.schema))
        with open(fn, "r") as fp: sql = fp.read()
        logging.debug("SCHEMA:\n", sql)
        cur.execute("BEGIN TRANSACTION;")
        cur.execute(sql)
        db.commit()

    def name(self, name:str) -> None:
        self.__name = name

    def block(self, data:bytes) -> None:
        self.size += len(data)
        args = self.__args
        regexp = self.__regexp
        sql = self.__sql
        db = self.__db
        cur = db.cursor()
        values = [args.className, self.__name, None, None, None]

        for line in data.split(b"\n"):
            matches = regexp.fullmatch(line)
            if not matches:
                # logging.debug("Unmatched line: %s", line)
                continue
            values[2] = datetime.datetime.strptime(
                    str(matches[1], "UTF-8"),
                    "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            values[3] = float(str(matches[2], "UTF-8"))
            values[4] = float(str(matches[4], "UTF-8"))
            cur.execute(sql, values, prepare=True)
        db.commit()

    def toCSV(self) -> None:
        args = self.__args
        csvDir = self.__csvDir
        tbl = args.table
        sql = f"UPDATE {tbl} SET qCSV=TRUE WHERE CTID IN ("
        sql+= f"SELECT DISTINCT ON (grp,id) CTID FROM {tbl} ORDER BY grp,id,t DESC"
        sql+= ") AND qCSV=FALSE"
        sql+= " RETURNING grp,id,t,lat,lon;"
        db = self.__db
        cur = db.cursor()
        cur.execute(sql)
        for row in cur:
            ofn = os.path.join(csvDir, row[0] + "_" +  row[1] + ".pos.csv")
            mode = "a" if os.path.isfile(ofn) else "w"
            with open(ofn, mode) as ofp:
                if mode == "w":
                    ofp.write("t,lat,lon\n")
                msg = str(round(row[2].timestamp())) + f",{row[3]:.6f},{row[4]:.6f}\n"
                ofp.write(msg)
            logging.info("Updated %s", ofn)
        db.commit()

class RetrieveFile:
    def __init__(self, fn:str) -> None:
        self.__filename = fn
        self.__fp = None
        self.size = 0
        self.offset = os.path.size(fn) if os.path.isfile(fn) else 0

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        parser.add_argument("--ftpSaveTo", type=str, default="~/Sync.ARCTERX/Shore/WG")

    def __del__(self):
        if self.__fp is not None:
            self.__fp.close()
            self.__fp = None

    def block(self, data:bytes) -> None:
        if self.__fp is None:
            mode = "a" if self.__offset else "w"
            self.__fp = open(self.__filename, mode + "b")
        self.__fp.write(data)
        self.size += len(data)

class FTPfetch:
    def __init__(self, args:ArgumentParser) -> None:
        # args.ftpSaveTo = os.path.abspath(os.path.expanduser(args.ftpSaveTo))
        # if not os.path.isdir(args.ftpSaveTo):
            # logging.info("Making %s", args.ftpSaveTo)
            # os.makedirs(args.ftpSaveTo, mode=0o755, exist_ok=True)

        regexp = re.compile(args.ftpRegEx)

        (username, password) = getCredentials(
                os.path.abspath(os.path.expanduser(args.ftpCredentials)))

        with FTP(host=args.ftpHost, user=username, passwd=password) as ftp:
            ftp.set_pasv(True) # Turn on passive mode
            objPos = None
            for directory in args.ftpDirectory:
                logging.debug("CWD to %s", directory)
                ftp.cwd(directory)
                for fn in ftp.nlst():
                    matches = regexp.fullmatch(fn)
                    if not matches:
                        logging.info("Rejecting %s", fn)
                        continue
                    if matches[3] == "positions_last_24h":
                        if objPos is None:
                            objPos = PositionFile(args)
                        objPos.name(matches[2])
                        obj = objPos
                        sz0 = objPos.size
                        offset = None
                    else:
                        logging.error("Unsupported file type, %s", fn)
                        continue
                    # fnOut = os.path.join(args.ftpSaveTo, fn)
                    # offset = 0
                    # if os.path.exists(fnOut) and not re.search(r"_last_24h", fnOut):
                        # info = os.stat(fnOut)
                        # offset = info.st_size
                    # obj = RetrieveFile(fnOut, offset)
                    ftp.retrbinary(f"RETR {fn}", obj.block, blocksize=65536, rest=offset)
                    if sz0 is None: # pos
                        logging.info("Fetched %s bytes from %s", objPos.size - sz0, fn, offset)
            if objPos is not None:
                objPos.toCSV() # After all the records are fetched, update the CSV files if needed

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="FTP fetch related options")
        grp.add_argument("--noprogress", action="store_true",
                help="Don't display download progress")
        grp.add_argument("--ftpDirectory", type=str, action="append",
                help="Directory prefix to change to")
        grp = parser.add_argument_group(description="Credentials related options")
        grp.add_argument("--ftpHost", type=str, metavar="foo.bar.com",
                default="cordcftp.ucsd.edu",
                help="Fully qualified hostname to connect to")
        grp.add_argument("--ftpCredentials", type=str, default="~/.config/SIO/.sio.credentials",
                help="Name of JSON file containinng the SIO credentials")
        grp.add_argument("--ftpRegEx", type=str,
                default=r"wg_SV3-(\d+)_(\w+)_(positions_last_24h)[.](txt|csv)$",
                help="Regular expression files must match to be fetched")

if __name__ == "__main__":
    parser = ArgumentParser()
    Logger.addArgs(parser)
    FTPfetch.addArgs(parser)
    PositionFile.addArgs(parser)
    RetrieveFile.addArgs(parser)
    grp = parser.add_argument_group(description="Output related options")
    grp.add_argument("--output", type=str, default="data", help="Output directory")
    args = parser.parse_args()

    Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

    if args.ftpDirectory is None:
        args.ftpDirectory = (
                "CORDC/outgoing/arcterx",
                # "CORDC/outgoing/arcterx/wgms",
                # "CORDC/outgoing/arcterx/sensor_data",
                )

    FTPfetch(args)
