#!/usr/bin/env python3
#
# Generate a fack ship track CSV file
#
# April-2023, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
import numpy as np
import time
import os.path

parser = ArgumentParser()
parser.add_argument("--dt", type=float, default=10, help="Time between fixes")
parser.add_argument("--lat0", type=float, default=9, help="Starting latitude")
parser.add_argument("--lat1", type=float, default=10, help="Ending latitude")
parser.add_argument("--lon0", type=float, default=125, help="Starting longitude")
parser.add_argument("--lon1", type=float, default=124, help="Ending longitude")
parser.add_argument("--distdLat", type=float, default=110604.555839,
                    help="meters/degree of latitude")
parser.add_argument("--distdLon", type=float, default=109802.785235,
                    help="meters/degree of longitude")
parser.add_argument("--speed", type=float, default=2, help="SOG in knots")
parser.add_argument("--csv", type=str, default="~/ship.csv", help="Where to write data to")
args = parser.parse_args()

csv = os.path.abspath(os.path.expanduser(args.csv))
if not os.path.isfile(csv):
    with open(csv, "w") as fp:
        fp.write("t,latitude,longitude,SOG,COG\n");


spd = args.speed * 1.94384 # knots -> m/s

dy = (args.lat1 - args.lat0) * args.distdLat
dx = (args.lon1 - args.lon0) * args.distdLon
heading = np.degrees(np.arctan2(dy, dx))
dist = np.sqrt(dy * dy + dx * dx);
totTime = dist / spd;
dxdt = dx / totTime / args.distdLon * args.dt
dydt = dy / totTime / args.distdLat * args.dt

x = args.lon0
y = args.lat0

now = time.time()

latSouth = min(args.lat0, args.lat1)
latNorth = max(args.lat0, args.lat1)
lonEast = min(args.lon0, args.lon1)
lonWest = max(args.lon0, args.lon1)

while True:
    if (x < lonEast) or (x > lonWest) or (y < latSouth) or (y > latNorth):
        print("Flipping")
        dxdt = -dxdt
        dydt = -dydt
        heading = np.mod(heading + 180, 360);
    x += dxdt
    y += dydt
    with open(csv, "a") as fp:
        fp.write(f"{now:.1f},{y:.6f},{x:.6f},{spd:.2f},{heading:.1f}\n")
    tNext = now + args.dt
    dt = tNext - time.time()
    now = tNext
    time.sleep(max(dt, 0.01))
