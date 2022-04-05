#! /usr/bin/env python3
#
# Fetch SIO's wave glider data
#
# Mar-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
from ftplib import FTP
import json
import os
import re

class RetrieveFile:
    def __init__(self, fn:str, offset:int) -> None:
        self.__filename = fn
        self.__fp = None
        self.__offset = 0 if offset is None else offset
        self.size = 0

    def __del__(self):
        if self.__fp is not None:
            self.__fp.close()
            self.__fp = None

    def block(self, data:bytes) -> None:
        if self.__fp is None:
            if self.__offset: # Appending
                self.__fp = open(self.__filename, "ab")
            else: # Not appending
                self.__fp = open(self.__filename, "wb")
        self.__fp.write(data)
        self.size += len(data)

class FTPfetch:
    def __init__(self, directory:str, args:ArgumentParser) -> None:
        self.__directory = directory
        self.__args = args
        self.__files = set()
        self.__Fetch() # Fetch the files if needed

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="FTP fetch related options")
        grp.add_argument("--nofetch", action="store_true", help="Don't fetch new files")
        grp.add_argument("--noprogress", action="store_true",
                help="Don't display download progress")
        grp.add_argument("--ftpDirectory", type=str, action="append",
                help="Directory prefix to change to")
        grp.add_argument("--ftpSaveTo", type=str, default="~/Sync.ARCTERX/Shore/WaveGlider",
                help="Directory to save FTP files to")
        grp = parser.add_argument_group(description="Credentials related options")
        grp.add_argument("--ftpHost", type=str, metavar="foo.bar.com",
                default="cordcftp.ucsd.edu",
                help="Fully qualified hostname to connect to")
        grp.add_argument("--ftpCredentials", type=str, default="~/.config/SIO/.sio.credentials",
                help="Name of JSON file containinng the SIO credentials")
        grp.add_argument("--ftpRegEx", type=str,
                default=r"wg_\d+_(targetwp|positions|positions_last_24h|(wave|mets)_\d+-\d+)[.](txt|csv)$",
                help="Regular expression files must match to be fetched")

    def __getCredentials(self) -> tuple[str, str]:
        fn = os.path.abspath(os.path.expanduser(self.__args.ftpCredentials))
        try:
            with open(fn, "r") as fp:
                info = json.load(fp)
                if "username" in info and "password" in info:
                    return (info["username"], info["password"])
                logger.error("%s is not properly formated", fn)
        except Exception as e:
            logger.warning("Unable to open %s, %s", fn, str(e))

        logger.info("Going to build a fresh SIO credentials file, %s", fn)
        info = {
            "username": input("Enter usrname:"),
            "password": input("Enter password:"),
            }

        os.makedirs(os.path.dirname(fn), mode=0o700, exist_ok=True)

        with open(fn, "w") as fp:
            json.dump(info, fp, indent=4, sort_keys=True)
        return (info["username"], info["password"])

    def __Fetch(self) -> None:
        (username, password) = self.__getCredentials()
        args = self.__args

        args.ftpSaveTo = os.path.abspath(os.path.expanduser(args.ftpSaveTo))
        if not os.path.isdir(args.ftpSaveTo):
            logger.info("Making %s", args.ftpSaveTo)
            os.makedirs(args.ftpSaveTo, mode=0o755, exist_ok=True)

        with FTP(host=args.ftpHost, user=username, passwd=password) as ftp:
            ftp.set_pasv(True) # Turn on passive mode
            directory = self.__directory
            logger.debug("CWD to %s", directory)
            ftp.cwd(directory)
            for fn in ftp.nlst():
                if not re.fullmatch(args.ftpRegEx, fn): 
                    logger.info("Rejecting %s", fn)
                    continue
                offset = None
                fnOut = os.path.join(args.ftpSaveTo, fn)
                offset = 0
                if os.path.exists(fnOut) and not re.search(r"_last_24h", fnOut):
                    info = os.stat(fnOut)
                    offset = info.st_size

                obj = RetrieveFile(fnOut, offset)
                ftp.retrbinary(f"RETR {fn}", obj.block, blocksize=65536, rest=offset)
                logger.info("Fetched %s bytes from %s starting at %s", obj.size, fn, offset)


if __name__ == "__main__":
    parser = ArgumentParser()
    Logger.addArgs(parser)
    FTPfetch.addArgs(parser)
    grp = parser.add_argument_group(description="Output related options")
    grp.add_argument("--output", type=str, default="data", help="Output directory")
    args = parser.parse_args()

    logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s", logLevel="INFO")

    if args.ftpDirectory is None:
        args.ftpDirectory = (
                "pub/CORDC/outgoing/arcterx",
                "pub/CORDC/outgoing/arcterx/wgms",
                "pub/CORDC/outgoing/arcterx/sensor_data",
                )

    for name in args.ftpDirectory:
        a = FTPfetch(name, args)
