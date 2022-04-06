#! /usr/bin/env python3
#

import xarray as xr
import pandas as pd

with xr.open_dataset("tpw.nc") as ds:
    df = pd.DataFrame()
    df["t"] = ds.end_time
    df["lat"] = ds.end_latitude
    df["lon"] = ds.end_longitude
    df.to_csv("tpw.csv", index=False)
