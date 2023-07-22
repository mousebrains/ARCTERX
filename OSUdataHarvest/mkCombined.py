#! /usr/bin/env python3
#
# Extract information for a glider and create a combined NetCDF file
# using SIO/IDG's template
#
# June-2023, Pat Welch, pat@mousebrains.com

import logging
import xarray as xr
import pandas as pd
import numpy as np
import os.path
import gsw
import datetime
from scipy.interpolate import interp1d

def mkDegrees(degmin:np.array) -> float:
    qNeg = degmin < 0
    degmin = np.abs(degmin)
    deg = np.floor(degmin / 100)
    minutes = np.mod(degmin, 100)
    deg = deg + minutes / 60
    deg[np.abs(deg) > 180] = None
    return deg


def mkCombo(gld:str, fnOutput:str, fnLog:str, fnFlt:str, fnSci:str) -> None:
    with xr.open_dataset(fnLog) as ds:
        ds = ds.sel(index=ds.index[ds.glider == gld])
        dfLog = pd.DataFrame()
        dfLog["timeu"] = ds.t.data.astype("datetime64[s]").astype(float)
        dfLog["latu"] = ds.lat
        dfLog["lonu"] = ds.lon
        dfLog["u"] = ds.m_water_vx
        dfLog["v"] = ds.m_water_vy
        dfLog = dfLog.dropna(axis=0, subset=dfLog.columns[1:], how="all")
        dfLog = dfLog[dfLog.timeu > 0]
        (t, ix) = np.unique(dfLog.timeu, return_index=True)
        dfLog = dfLog.iloc[ix]
        qLat = np.logical_not(np.isnan(dfLog.latu))
        latInterp = interp1d(dfLog.timeu[qLat], dfLog.latu[qLat],
                             bounds_error=False, fill_value="nan")
        qLon = np.logical_not(np.isnan(dfLog.lonu))
        lonInterp = interp1d(dfLog.timeu[qLon], dfLog.lonu[qLon],
                             bounds_error=False, fill_value="nan")
        qLat = np.logical_not(qLat)
        qLon = np.logical_not(qLon)
        dfLog.latu[qLat] = latInterp(dfLog.timeu[qLat])
        dfLog.lonu[qLon] = lonInterp(dfLog.timeu[qLon])
        dfLog = dfLog.dropna(axis=0, subset=("u", "v"), how="any")
        dfLog = dfLog.set_index("timeu")

    with xr.open_dataset(fnFlt) as ds:
        flt = pd.DataFrame()
        flt["time"] = ds.m_present_time
        flt["latGPS"] = mkDegrees(ds.m_gps_lat.data)
        flt["lonGPS"] = mkDegrees(ds.m_gps_lon.data)
        flt = flt.dropna(axis=0, subset=flt.columns, how="any")
        flt = flt[flt.time > 0]
        (t, ix) = np.unique(flt.time, return_index=True)
        flt = flt.iloc[ix]
        latInterp = interp1d(flt.time, flt.latGPS, bounds_error=False, fill_value="nan")
        lonInterp = interp1d(flt.time, flt.lonGPS, bounds_error=False, fill_value="nan")
        flt = flt.dropna(axis=0, subset=flt.columns, how="any")

    with xr.open_dataset(fnSci) as ds:
        sci = pd.DataFrame()
        sci["time"] = ds.sci_m_present_time
        sci["t"] = ds.sci_water_temp
        sci["C"] = ds.sci_water_cond * 10
        sci["P"] = ds.sci_water_pressure * 10
        sci = sci.dropna(axis=0, subset=sci.columns, how="any")
        sci = sci[sci.time > 0]
        sci = sci[sci.t > 0]
        sci = sci[sci.P > 0]
        sci["lat"] = latInterp(sci.time)
        sci["lon"] = lonInterp(sci.time)
        sci["depth"] = -gsw.conversions.z_from_p(sci.P.to_numpy(), sci.lat.to_numpy())
        sci["s"] = gsw.SP_from_C(sci.C.to_numpy(), sci.t.to_numpy(), sci.P.to_numpy())
        sa = gsw.SA_from_SP(sci.s.to_numpy(), sci.P.to_numpy(),
                            sci.lon.to_numpy(), sci.lat.to_numpy())
        sci["theta"] = gsw.conversions.pt0_from_t(sa, sci.t.to_numpy(), sci.P.to_numpy())
        ct = gsw.conversions.CT_from_pt(sa, sci.theta.to_numpy())
        sci["sigma"] = gsw.density.sigma0(sa, ct)
        sci["rho"] = gsw.density.rho_t_exact(sa, sci.t.to_numpy(), sci.P.to_numpy()) - 1000
        sci = sci.drop(columns=["C", "P"])
        sci = sci.dropna(axis=0, subset=sci.columns[1:], how="any")
        (t, ix) = np.unique(sci.time, return_index=True)
        sci = sci.iloc[ix]
        sci = sci.set_index("time")

    ds = xr.merge([dfLog.to_xarray(), sci.to_xarray()])

    platform = f"TWR Slocum {gld}"

    attrs = dict(
            time=dict(units = "seconds since 1970-01-01",
                      calendar = "proleptic_gregorian",
                      standard_name = "time",
                      long_name = "Time"),
            lat=dict(units = "degrees_north",
                     long_name = "latitude",
                     standard_name = "latitude",
                     ancillary_variables = "lon",
                     coordinate_reference_frame = "WGS84",
                     reference = "WGS84",
                     comment = "WGS84",
                     valid_min = -90.,
                     valid_max =  90.,
                     observation_type = "GPS",
                     platform = platform),
            lon=dict(units = "degrees_east",
                     long_name = "longitude",
                     standard_name = "longitude",
                     ancillary_variables = "lat",
                     coordinate_reference_frame = "WGS84",
                     reference = "WGS84",
                     comment = "WGS84",
                     valid_min = -180.,
                     valid_max =  180.,
                     observation_type = "GPS",
                     platform = platform),
            u = dict(units = "m s-1",
                     long_name = "m_water_vx",
                     standard_name = "eastward_sea_water_velocity",
                     valid_min = -10.,
                     valid_max =  10.,
                     comment="Depth averaged eastward current",
                     observation_type = "calculation",
                     platform=platform),
            v = dict(units = "m s-1",
                     long_name = "m_water_vy",
                     standard_name = "northward_sea_water_velocity",
                     valid_min = -10.,
                     valid_max =  10.,
                     comment="Depth averaged northward current",
                     observation_type = "calculation",
                     platform=platform),
            t = dict(units = "degree C",
                     long_name = "temperature",
                     standard_name = "sea_water_temperature"),
            depth = dict(units = "meters",
                         positive = "down",
                         long_name = "depth",
                         standard_name = "depth",
                         accuracy = 0.01,
                         precision = 0.001,
                         resolution = 0.001,
                         valid_max = 1000.,
                         valid_min = 0.,
                         reference_datum = "sea surface",
                         ancillary_variables = "s",
                         comment = "GPCTD",
                         instrument = "GPCTD",
                         observation_type = "in-situ",
                         platform = platform),
            s = dict(units = "1",
                     long_name = "salinity",
                     standard_name = "sea_water_practical_salinity"),
            theta = dict(units = "degree C",
                         long_name = "potentialTemperature",
                         standard_name = "sea_water_potential_temperature"),
            sigma = dict(units = "kg m-3",
                       long_name = "potentialDensity",
                       standard_name = "sea_water_potential_density"),
            rho = dict(units = "kg m-3",
                       long_name = "density",
                       standard_name = "sea_water_density"),
            )
    attrs["lonu"] = attrs["lon"]
    attrs["latu"] = attrs["lat"]

    ds.time.attrs.update(attrs["time"]);
    ds.timeu.attrs.update(attrs["time"]);
    for key in ds:
        if key in attrs:
            ds[key].attrs.update(attrs[key])

    now = datetime.datetime.now()

    ds.attrs.update(dict(
        title = f"{gld} for ARCTERX 2023-IOP",
        comment = "Salinity is not thermal mass corrected",
        history = f"Generated {now}",
        Conventions = "CF-1.8",
        date_created = f"{now}",
        date_issued = f"{now}",
        date_modified = f"{now}",
        institution = "Oregon State University Glider Laboratory",
        project = "ARCTERX 2023-IOP",
        ))

    encoding = dict(zlib=True, complevel=9)
    ds.t.encoding.update(encoding)
    for key in ds:
        ds[key].encoding.update(encoding)

    ds.to_netcdf(fnOutput)

if __name__ == "__main__":
    from argparse import ArgumentParser
    from TPWUtils import Logger

    parser = ArgumentParser()
    Logger.addArgs(parser)
    parser.add_argument("--prefix", type=str, default="osu", help="Insitution prefix")
    parser.add_argument("--glider", type=int, required=True, help="Glider to operate on")
    parser.add_argument("--output", type=str, required=True, help="Output NetCDF filename")
    parser.add_argument("--ncLog", type=str, default="log.nc", help="Input log NetCDF")
    parser.add_argument("--ncFlight", type=str, help="Input flight NetCDF")
    parser.add_argument("--ncScience", type=str, help="Input science NetCDF")
    args = parser.parse_args()

    Logger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

    if args.ncFlight is None:
        args.ncFlight = os.path.join(os.path.dirname(args.ncLog), f"flt{args.glider}.nc")

    if args.ncScience is None:
        args.ncScience = os.path.join(os.path.dirname(args.ncLog), f"sci{args.glider}.nc")

    mkCombo(f"{args.prefix}{args.glider}",
            args.output,
            args.ncLog,
            args.ncFlight,
            args.ncScience)
