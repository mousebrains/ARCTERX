#! /usr/bin/env python3
#
# Do rsync for when syncthing breaks down
#
# May-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
from TPWUtils import Logger
import logging
import time
import subprocess

class RSync(Thread):
    def __init__(self, name:str, args:ArgumentParser, dt:float, src:str, tgt:str):
        Thread.__init__(self, name, args)
        self.__dt = dt
        self.__src = src
        self.__tgt = tgt

    def runIt(self):
        args = self.args
        dt = self.__dt
        src = self.__src
        tgt = self.__tgt

        tNext = time.time() + dt

        cmd = [args.rsync,
               f"--bwlimit={args.bwlimit}",
               f"--temp-dir={args.tempDir}",
               "--compress",
               "--archive",
               ]
        if args.verbose: cmd.append("--verbose")
        cmd.append(src)
        cmd.append(tgt)
        logging.info("Starting %s", cmd)
        while True:
            a = subprocess.run(cmd, 
                               shell=False, 
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
            if a.returncode:
                try:
                    msg = str(a.stdout, "utf-8")
                except:
                    msg = a.stdout
                logging.error("Executing %s\n%s", cmd, msg)
            elif a.stdout:
                try:
                    msg = str(a.stdout, "utf-8")
                except:
                    msg = a.stdout
                logging.info("STDOUT %s\n%s", cmd, msg)

            now = time.time()
            delta = max(0.1, tNext - now)
            tNext = now + dt
            logging.info("Sleeping for %s", delta)
            time.sleep(delta)

parser = ArgumentParser()
Logger.addArgs(parser)
grp = parser.add_argument_group(description="RSync related options")
grp.add_argument("--rsync", type=str, default="/usr/bin/rsync", help="rsync command")
grp.add_argument("--bwlimit", type=int, default=200, help="KiB/sec")
grp.add_argument("--tempDir", type=str, default="/home/pat/cache", help="Rsync temp dir")
grp = parser.add_argument_group(description="Pushing to shore")
grp.add_argument("--dtPush", type=float, default=300, help="Delay between push attempts")
grp.add_argument("--srcPush", type=str, default="/home/pat/Sync.ARCTERX/Ship",
                 help="rsync src for pushing to shore")
grp.add_argument("--tgtPush", type=str, default="arcterx:Sync.ARCTERX",
                 help="rsync target for pushing to shore")
grp = parser.add_argument_group(description="Pulling from shore")
grp.add_argument("--dtPull", type=float, default=300, help="Delay between pull attempts")
grp.add_argument("--srcPull", type=str, default="arcterx:Sync.ARCTERX/Shore",
                 help="rsync src for pulling from shore")
grp.add_argument("--tgtPull", type=str, default="/home/pat/Sync.ARCTERX",
                 help="rsync target for pulling from shore")
args = parser.parse_args()

Logger.mkLogger(args)

push = RSync("PUSH", args, args.dtPush, args.srcPush, args.tgtPush)
pull = RSync("PULL", args, args.dtPull, args.srcPull, args.tgtPull)

try:
    push.start()
    pull.start()

    Thread.waitForException()
except:
    logging.exception("GotMe")
