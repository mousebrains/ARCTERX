#! /usr/bin/env python3
#
# Fetch, if needed, the AVISO+ Mesoscale Eddy Product
# generate plots in the specified date range, if needed
# Glue images into a movie
#
# Feb-2020, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from TPWUtils.Credentials import getCredentials
from argparse import ArgumentParser
import xarray as xr
import numpy as np
from ftplib import FTP
import yaml
import re
import datetime
import os
import sys

class RetrieveFile:
    def __init__(self, fn:str, offset:int) -> None:
        self.__filename = fn
        self.__fp = None
        self.__size = 0 if offset is None else offset
        self.__sizeInit = self.__size

    def __del__(self):
        if self.__fp is not None:
            self.__fp.close()
            self.__fp = None
            logger.info("Fetched %s bytes for %s", self.__size - self.__sizeInit, self.__filename)

    def block(self, data:bytes) -> None:
        if self.__fp is None:
            if self.__size: # Appending
                self.__fp = open(self.__filename, "ab")
            else: # Not appending
                self.__fp = open(self.__filename, "wb")
        self.__fp.write(data)
        self.__size += len(data)

class FTPfetch:
    def __init__(self, info:dict, edate:datetime.date,  nBack:int, args:ArgumentParser) -> None:
        self.__args = args
        self.files = set()
        if args.nofetch: # Don't fetch new files, use existing ones
            self.__noFetch()
        else:
            self.__Fetch(info, edate, nBack) # Fetch the files if needed

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="FTP fetch related options")
        grp.add_argument("--nofetch", action="store_true", help="Don't fetch new files")
        grp.add_argument("--ftpSaveTo", type=str, default="data",
                help="Directory to save FTP files to")
        grp.add_argument("--credentials", type=str, default="~/.config/Copernicus/.copernicus",
                help="Name of file containinng the Copernicus credentials")

    def __noFetch(self) -> None:
        directory = self.__args.ftpSaveTo
        self.files = set()
        for fn in os.listdir(directory):
            if re.match(r".*[.]nc"):
                self.files.add(os.path.join(directory, fn))

    def __Fetch(self, info:dict, edate:datetime.date, nBack:int) -> None:
        args = self.__args
        (username, password) = getCredentials(args.credentials)

        times = {}
        for n in range(nBack):
            t = edate - datetime.timedelta(days=n)
            year = t.strftime("%Y")
            month = t.strftime("%m")
            if year not in times: times[year] = {}
            if month not in times[year]: times[year][month] = set()
            times[year][month].add(t.strftime("%Y%m%d"))

        for year in times:
            for month in times[year]:
                print(year, month, times[year][month])
                times[year][month] = r"_(" + "|".join(times[year][month]) + r")_.*[.]nc"

        with FTP(host=info["hostname"], user=username, passwd=password) as ftp:
            directory = info["directory"]
            ftp.cwd(directory)
            for item in ftp.nlst():
                logger.info("item %s", item)
                ftp.cwd(item)
                for year in ftp.nlst():
                    if year not in times: continue
                    ftp.cwd(year)
                    for month in ftp.nlst():
                        if month not in times[year]: continue
                        ftp.cwd(month)
                        for fn in ftp.nlst():
                            if not re.search(times[year][month], fn): continue
                            logger.info("Fetching %s", fn)
                            ofn = os.path.join(args.ftpSaveTo, os.path.basename(fn))
                            offset = os.stat(ofn).st_size if os.path.exists(ofn) else 0
                            obj = RetrieveFile(ofn, offset)
                            ftp.retrbinary(f"RETR {fn}", obj.block, blocksize=65536, rest=offset)
                            self.files.add(ofn)
                        ftp.cwd("..")
                    ftp.cwd("..")
                ftp.cwd("..")

if __name__ == "__main__":
    parser = ArgumentParser()
    Logger.addArgs(parser)
    FTPfetch.addArgs(parser)
    parser.add_argument("--fetchonly", action="store_true", help="Only do FTP fetch")
    grp = parser.add_argument_group(description="Output related options")
    grp.add_argument("--pruneTo", type=str, default="date.pruned",
            help="Output pruned data directory")
    grp = parser.add_argument_group(description="Date selection options")
    grp.add_argument("--ndays", type=int, default=3, help="Number of days to fetch data for")
    grp.add_argument("--edate", type=str, help="Ending date, YYYY-MM-DD")
    grp.add_argument("--yaml", type=str, default="Copernicus.yaml",
            help="YAML configuration filename")
    args = parser.parse_args()

    logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

    edate = datetime.date.today() if args.edate is None else datetime.date(args.edate)

    args.ftpSaveTo = os.path.abspath(os.path.expanduser(args.ftpSaveTo))
    args.pruneTo = os.path.abspath(os.path.expanduser(args.pruneTo))

    os.makedirs(args.ftpSaveTo, mode=0o755, exist_ok=True)
    os.makedirs(args.pruneTo, mode=0o755, exist_ok=True)

    with open(args.yaml, "r") as fp:
        info = yaml.safe_load(fp)

    a = FTPfetch(info, edate, args.ndays, args)

    if args.fetchonly:
        logger.info("Only fetching")
        sys.exit(0)

    for fn in a.files:
        logger.info("To Prune %s", fn)
