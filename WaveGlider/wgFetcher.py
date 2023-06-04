#! /usr/bin/env python3
#
# Fetch SIO's wave glider data positions
#
# Mar-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from TPWUtils.loadAndExecuteSQL import loadAndExecuteSQL
from TPWUtils.Credentials import getCredentials
import logging
from argparse import ArgumentParser
from ftplib import FTP
import xarray as xr
import pandas as pd
import datetime
import psycopg
import json
from tempfile import TemporaryFile
import os
import re

class PositionFile:
    def __init__(self, args:ArgumentParser) -> None:
        self.size = 0
        self.__args = args
        self.__regexp = re.compile(
                b"(\d+-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),([+-]?\d+(|[.]\d*)),([+-]?\d+(|[.]\d*))")
        self.__db = psycopg.connect(f"dbname={args.db}")
        self.__cursor = self.__db.cursor()
        loadAndExecuteSQL(self.__db,
                          os.path.abspath(os.path.expanduser(args.schema)),
                          "glider")
        self.__sql = f"INSERT INTO {args.table}"
        self.__sql+= "(grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
        self.__sql+= " ON CONFLICT DO NOTHING;"
        self.__name = None
        self.__csvDir = os.path.abspath(os.path.expanduser(args.posSaveTo))
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
        grp.add_argument("--posSaveTo", type=str, default="~/Sync.ARCTERX/Shore/WG")

    def __del__(self):
        if self.__db: 
            if self.__cursor:
                self.__db.commit()
            self.__db.close()
            self.__db = None

    def name(self, name:str) -> None:
        self.__name = name

    def done(self) -> None:
        pass

    def commit(self) -> None:
        self.__db.commit();
        self.__curosr = None;

    def block(self, data:bytes) -> None:
        self.size += len(data)
        args = self.__args
        regexp = self.__regexp
        sql = self.__sql
        cur = self.__cursor
        values = [args.className, self.__name, None, None, None]

        for line in data.split(b"\n"):
            matches = regexp.fullmatch(line)
            if not matches:
                # logging.debug("Unmatched line: %s", line)
                continue
            try:
                values[2] = datetime.datetime.strptime(
                        str(matches[1], "UTF-8"),
                        "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                values[3] = float(str(matches[2], "UTF-8"))
                values[4] = float(str(matches[4], "UTF-8"))
                cur.execute(sql, values, prepare=True)
            except:
                logging.warning("Unable to parse %s", line)

    def toCSV(self) -> None:
        args = self.__args
        csvDir = self.__csvDir
        tbl = args.table
        sql = f"UPDATE {tbl} SET qCSV=TRUE WHERE CTID IN ("
        sql+= f"SELECT DISTINCT ON (grp,id) CTID FROM {tbl} ORDER BY grp,id,t DESC"
        sql+= ") AND qCSV=FALSE"
        sql+= " RETURNING grp,id,t,lat,lon;"
        cur = self.__cursor
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

class MWBfile:
    def __init__(self, args:ArgumentParser) -> None:
        self.size = 0
        self.__args = args
        self.__db = psycopg.connect(f"dbname={args.db}")
        self.__cursor = self.__db.cursor()
        loadAndExecuteSQL(self.__db,
                          os.path.abspath(os.path.expanduser(args.schema)),
                          "glider")
        self.__sql = f"INSERT INTO {args.table}"
        self.__sql+= "(grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
        self.__sql+= " ON CONFLICT DO NOTHING;"
        self.__name = None
        self.__ident = None
        self.__tfp = None
        self.__csvDir = os.path.abspath(os.path.expanduser(args.mwbSaveTo))

        for dirname in [self.__csvDir]:
            if not os.path.isdir(dirname):
                logging.info("Creating %s", dirname)
                os.makedirs(dirname, mode=0o755, exist_ok=True)

    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="MWB related options")
        grp.add_argument("--mwbSaveTo", type=str, default="~/Sync.ARCTERX/Shore/MWB")

    def __del__(self):
        self.__tfp = None
        if self.__db: 
            if self.__cursor: 
                self.__db.commit()
            self.__db.close()
            self.__db = None

    def name(self, name:str) -> None:
        matches = re.fullmatch(r"mwb(\d+)d\d+[.]nc", name)
        if not matches:
            logging.info("Rejecting %s", name)
            self.__tfp = None
            return

        self.__name = name
        self.__ident = matches[1]
        self.__ofn = os.path.join(self.__csvDir, name)
        self.__tfp = open(self.__ofn, "wb");

    def commit(self) -> None:
        self.__db.commit();
        self.__curosr = None;

    def done(self) -> None:
        if not self.__tfp: return
        args = self.__args
        self.__tfp.close()
        self.__tfp = None # Close the file

        sql = f"INSERT INTO {args.table} (grp,id,t,lat,lon) VALUES(%s,%s,%s,%s,%s)"
        sql+= " ON CONFLICT DO NOTHING;"

        with xr.open_dataset(self.__ofn) as ds:
            df = pd.DataFrame()
            df["grp"] = ["MWB"] * ds.time.size
            df["id"] = [self.__ident] * ds.time.size
            df["t"] = ds.time.data
            df["lat"] = ds.lat.data
            df["lon"] = ds.lon.data
            self.__cursor.executemany(sql, df.values.tolist())

    def block(self, data:bytes) -> None:
        self.size += len(data)
        if self.__tfp: self.__tfp.write(data)

    def toCSV(self) -> None:
        args = self.__args
        csvDir = self.__csvDir
        tbl = args.table
        sql = f"UPDATE {tbl} SET qCSV=TRUE WHERE CTID IN ("
        sql+= f"SELECT DISTINCT ON (grp,id) CTID FROM {tbl} ORDER BY grp,id,t DESC"
        sql+= ") AND qCSV=FALSE"
        sql+= " RETURNING grp,id,t,lat,lon;"
        cur = self.__cursor
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

class CopyFile:
    def __init__(self, fn:str) -> None:
        self.__filename = fn
        self.__fp = None
        self.size = 0

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        pass

    def __del__(self):
        if self.__fp is not None:
            self.__fp.close()
            self.__fp = None

    def done(self) -> None:
        pass

    def block(self, data:bytes) -> None:
        if not self.__fp:
            dirname = os.path.dirname(self.__filename)
            if not os.path.isdir(dirname):
                logging.info("Creating %s", dirname)
                os.makedirs(dirname, mode=0o755, exist_ok=True)
            self.__fp = open(self.__filename, mode="wb")
        self.__fp.write(data)
        self.size += len(data)

class FTPfetch:
    def __init__(self, args:ArgumentParser) -> None:
        # args.ftpSaveTo = os.path.abspath(os.path.expanduser(args.ftpSaveTo))
        # if not os.path.isdir(args.ftpSaveTo):
            # logging.info("Making %s", args.ftpSaveTo)
            # os.makedirs(args.ftpSaveTo, mode=0o755, exist_ok=True)

        (username, password) = getCredentials(
                os.path.abspath(os.path.expanduser(args.ftpCredentials)))

        with FTP(host=args.ftpHost, user=username, passwd=password) as ftp:
            ftp.set_pasv(True) # Turn on passive mode
            objPos = None
            objMWB = None
            for pattern in args.ftpDirectory:
                directory = os.path.dirname(pattern)
                expr = re.compile(os.path.basename(pattern))
                logging.debug("CWD to %s", directory)
                ftp.cwd(directory)
                for fn in ftp.nlst():
                    matches = expr.fullmatch(fn)
                    if not matches:
                        logging.info("Rejecting %s", fn)
                        continue
                    if "positions_last_24h" in fn:
                        matches = re.fullmatch(r"wg_SV3-(\d+)_(\w+)_positions_last_24h[.](txt|csv)", fn)
                        if not matches: continue
                        if objPos is None:
                            objPos = PositionFile(args)
                        obj = objPos
                        obj.name(matches[2])
                        sz0 = obj.size
                        offset = None
                    elif "_hfr_pw_6km_rtv_uwls_" in fn:
                        ofn = os.path.join(args.output, "HFR", fn)
                        if os.path.isfile(ofn): continue
                        obj = CopyFile(ofn)
                        sz0 = 0
                        offset = None
                    elif "_met_2023" in fn:
                        ofn = os.path.join(args.output, "CSSMET", fn)
                        # if os.path.isfile(ofn): continue
                        obj = CopyFile(ofn)
                        sz0 = 0
                        offset = None
                    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}[.]png", fn):
                        ofn = os.path.join(args.output, "XBand", fn)
                        if os.path.isfile(ofn): continue
                        obj = CopyFile(ofn)
                        sz0 = 0
                        offset = None
                    elif "mwb" in fn:
                        if "amsl.csv" in fn:
                            ofn = os.path.join(args.output, "MWB", fn)
                            obj = CopyFile(ofn)
                            sz0 = 0
                            offset = None
                        elif ".nc" in fn:
                            if not objMWB:
                                objMWB = MWBfile(args)
                            obj = objMWB
                            obj.name(fn)
                            sz0 = obj.size
                            offset = None
                        else:
                            logging.info("Unsupported file %s", fn)
                            continue
                    elif "metbuoy" in fn:
                        ofn = os.path.join(args.output, "WG", fn)
                        # if os.path.isfile(ofn): continue
                        obj = CopyFile(ofn)
                        sz0 = 0
                        offset = None
                    else:
                        logging.info("Unsupported file %s", fn)
                        continue
                    ftp.retrbinary(f"RETR {fn}", obj.block, blocksize=65536, rest=offset)
                    if offset is None:
                        logging.info("Fetched %s bytes from %s", obj.size - sz0, fn)
                    else:
                        logging.info("Fetched %s bytes from %s offset %s",
                                     obj.size - sz0, fn, offset)
                    obj.done()

            if objPos is not None:
                objPos.toCSV() # After all the records are fetched, update the CSV files if needed
                objPos.commit()
                objPos = None

            if objMWB is not None:
                objMWB.toCSV() # After all the records are fetched, update the CSV files if needed
                objMWB.commit()
                objMWB = None

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

if __name__ == "__main__":
    parser = ArgumentParser()
    Logger.addArgs(parser)
    FTPfetch.addArgs(parser)
    PositionFile.addArgs(parser)
    CopyFile.addArgs(parser)
    MWBfile.addArgs(parser)
    # RetrieveFile.addArgs(parser)
    grp = parser.add_argument_group(description="Output related options")
    grp.add_argument("--output", type=str, default="~/Sync.ARCTERX/Shore", help="Output directory")
    args = parser.parse_args()

    Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

    args.output = os.path.abspath(os.path.expanduser(args.output))

    if args.ftpDirectory is None:
        args.ftpDirectory = (
                "/CORDC/outgoing/arcterx/wg_SV3-.*_positions_last_24h[.]txt",
                "/CORDC/outgoing/arcterx/hfr/NetCDF/2.*[.]nc",
                "/CORDC/outgoing/arcterx/xband/2.*[.]png",
                "/CORDC/outgoing/arcterx/wg/.*",
                "/CORDC/outgoing/arcterx/wave/.*",
                "/CORDC/outgoing/arcterx/cssmet/.*",
                )

        # "/CORDC/outgoing/internal/arcterx/wavebuoy/mwb.*[.]nc",
    FTPfetch(args)
