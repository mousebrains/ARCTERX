#! /usr/bin/env python3
#
# Grab Ko's model output graphics files,
# turn them into a movie,
# then write them into the synthing directory to be sent to ship.
#
# March-2022, Pat Welch, pat@mousebrains.com

from TPWUtils import Logger
from argparse import ArgumentParser
import requests
from hashlib import sha512
import urllib.parse
from tempfile import TemporaryDirectory
from PIL import Image
import subprocess
import re
import os
import sys

def logRequestProblem(url:str, r:requests.Request) -> int:
    logger.error("Unable to fetch '%s', %s", url, r.status_code)
    for hdr in sorted(r.headers):
        logger.info("Header[%s] = %s", hdr, r.headers[hdr])
    logger.infon("Content\n%s", r.content)
    return 1

def maybeWrite(fn:str, content:bytes) -> bool:
    ''' Only write if the contents have changed '''
    if os.path.isfile(fn):
        m0 = sha512(content)
        m1 = sha512()
        with open(fn, "rb") as fp:
            while True:
                a = fp.read(65536)
                if len(a) == 0: break
                m1.update(a)
        if m0.digest() == m1.digest():
            logger.debug("No need to update content %s", fn)
            return False

    directory = os.path.dirname(fn)
    if not os.path.isdir(directory):
        logger.debug("Creating %s", directory)
        os.makedirs(directory, mode=0o775, exist_ok=True)

    logger.info("Writing %s, %s", fn, len(content))
    with open(fn, "wb") as fp: fp.write(content)
    return True

def myFetch(url:str, qNoFetch:bool=False) -> bytes:
    if qNoFetch: return None
    with requests.get(url) as r:
        if r.status_code == 200:
            content = r.content
            logger.info("Fetched %s, %s", url, len(content))
            return content
        logRequestsProblem(url, r)
        return None

parser = ArgumentParser()
Logger.addArgs(parser)
parser.add_argument("--directory", type=str, default="~/Sync.ARCTERX/Shore/Ko",
        help="Where to save movies to")
parser.add_argument("--url", type=str, 
        default="https://www7320.nrlssc.navy.mil/NLIWI_WWW/EAS-SKII/EASNFS.html",
        help="URL to scrape from")
parser.add_argument("--skip", type=str, action="append", help="URLs to skip")
parser.add_argument("--keepOnly", type=str, action="append", help="URLs to keep but not parse")
parser.add_argument("--nofetch", action="store_true", help="Don't do secondary fetches")
grp = parser.add_argument_group(description="Movie related options")
grp.add_argument("--fps", type=int, default=2, help="Frames/second")
grp.add_argument("--crf", type=int, default=27, help="Quality lower is higher quality")
args = parser.parse_args()

logger = Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

args.directory = os.path.abspath(os.path.expanduser(args.directory))

if args.skip is None:
    args.skip = set([
        "EASNFS-tides.html",
        "images/lineblue.gif",
        ])
if args.keepOnly is None:
    args.keepOnly = set([
        "EASNFS-overview.html",
        "easnfs/date.gif",
        ])

content = None

with requests.get(args.url) as r:
    if r.status_code != 200:
        sys.exit(logRequestProblem(args.url, r))

    content = r.content

    # Write the file if different than what is on disk
    # maybeWrite(os.path.join(args.directory, os.path.basename(args.url)), content)

if not content:
    logger.warning("No content for %s", args.url)
    sys.exit(1)

# Find additional files that need to be scraped
toFetch = set() # Unique URLs to fetch
items = {} # groups of URLs with orderable time

for line in content.split(b"\n"):
    matches = re.search(b"<(img|a)\s+(src|href)\s*=\s*([\w/.-]+)(\s+|>)", line)
    if not matches: continue
    href = str(matches[3], "utf-8")
    if href in args.skip: continue
    if href in args.keepOnly:
        toFetch.add(href)
        continue
    matches = re.match(r"^(\d+)(|n)_(\w+).gif$", os.path.basename(href))
    if matches is None: continue
    hour = int(matches[1]) * (-1 if matches[2] == "n" else 1)
    key = matches[3]
    if key not in items:
        items[key] = {}
    items[key][hour] = href

for href in toFetch: # Only fetch and store these items
    content = myFetch(urllib.parse.urljoin(args.url, href), args.nofetch)
    maybeWrite(os.path.join(args.directory, href), content)

for key in items:
    with TemporaryDirectory() as tDir:
        cnt = 0
        for hour in sorted(items[key]):
            if hour < 0: continue # Ignore hindcast
            href = items[key][hour]
            gif = os.path.join(tDir, os.path.basename(href))
            png = os.path.join(tDir, f"{cnt:03d}.png")
            with open(gif, "wb") as fp:
                content = myFetch(urllib.parse.urljoin(args.url, href), args.nofetch)
                fp.write(content)
            with Image.open(gif) as im: im.save(png, optimize=True)
            cnt += 1
        mp4 = os.path.join(args.directory, f"{key}.mp4")
        cmd = ["ffmpeg",
                "-framerate", str(args.fps), # Frame rate in Hz
                "-pattern_type", "glob", # Glob file pattern
                "-i", os.path.join(tDir, "*.png"), # Input files
                "-vcodec", "libx264",
                "-crf", str(args.crf), # Quality, lower is better
                "-pix_fmt", "yuv420p", # Pixel color format
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", # Make sure both dimensions are even
                "-y", # answer yes to all questions, i.e. overwrite output
                mp4, # Output filename
            ]
        sp = subprocess.run(cmd, shell=False, check=False, capture_output=True)
        if sp.returncode == 0:
            logger.info("Creeated %s", mp4)
        else:
            logger.error("Unable to create %s, rc=%s", mp4, sp.returncode)
            logger.info("\n%s", s)
