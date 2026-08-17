"""
Aggregate daily Hu et al. (2025) fire PM2.5 NetCDF files to annual and monthly
mean CSVs with lon/lat grid centroids.

Hu et al. (2025): https://essd.copernicus.org/articles/17/3741/2025/
Input:  {year}gfedfirepm25.nc  — daily, 0.25° global, 2000–2023
Output (annual):  fire_pm25_hu_annual_{year}.csv   — columns: lon, lat, pm25
Output (monthly): fire_pm25_hu_monthly_{year}_{month:02d}.csv

Designed to be run as a SLURM array job (one job per year).

Date created: 2026-07-28
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from tqdm import tqdm

###############################################################################
# Paths
###############################################################################

DATA_PATH = Path(os.environ["SCRATCH_DIR"]) / "data" / "spatial"
IN_DIR    = DATA_PATH / "pm25_hu"
ANN_DIR   = DATA_PATH / "pm25_hu_annual"
MON_DIR   = DATA_PATH / "pm25_hu_monthly"

###############################################################################
# Helpers
###############################################################################

def da_to_df(da: xr.DataArray) -> pd.DataFrame:
    """
    Convert a 2D (lat, lon) DataArray of mean PM2.5 values to a tidy DataFrame
    with columns [lon, lat, pm25]. NaN cells (ocean/nodata) are dropped.
    """
    df = (
        da.to_dataframe(name="pm25")
          .reset_index()[["lon", "lat", "pm25"]]
          .dropna(subset=["pm25"])
    )
    return df


###############################################################################
# Aggregation functions
###############################################################################

def aggregate_annual(year: int) -> None:
    out_path = ANN_DIR / f"fire_pm25_hu_annual_{year}.csv"

    if out_path.exists():
        print(f"[SKIP] {out_path.name}")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    nc_path = IN_DIR / f"{year}gfedfirepm25.nc"
    print(f"[LOAD] {nc_path.name}")

    ds = xr.open_dataset(nc_path)
    annual_mean = ds["PM25"].mean(dim="time")

    print(f"[AGGREGATE] Annual mean {year}")
    df = da_to_df(annual_mean)
    df.to_csv(out_path, index=False)
    print(f"[WRITE] {out_path.name}  ({len(df):,} rows)")

    ds.close()


def aggregate_monthly(year: int) -> None:
    MON_DIR.mkdir(parents=True, exist_ok=True)

    nc_path = IN_DIR / f"{year}gfedfirepm25.nc"
    print(f"[LOAD] {nc_path.name}")

    ds = xr.open_dataset(nc_path)
    ds["time"] = pd.to_datetime(ds["time"].values)
    monthly = ds["PM25"].groupby("time.month")

    for month, group in tqdm(monthly, desc=f"Monthly {year}"):
        out_path = MON_DIR / f"fire_pm25_hu_monthly_{year}_{month:02d}.csv"

        if out_path.exists():
            print(f"[SKIP] {out_path.name}")
            continue

        df = da_to_df(group.mean(dim="time"))
        df.to_csv(out_path, index=False)
        print(f"[WRITE] {out_path.name}  ({len(df):,} rows)")

    ds.close()


###############################################################################
# Main
###############################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate Hu et al. daily fire PM2.5 to annual/monthly CSVs."
    )
    parser.add_argument(
        "--mode",
        choices=["annual", "monthly", "both"],
        default="both",
        help="Aggregation period to compute (default: both).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help=(
            "Year to process. If not provided, reads SLURM_ARRAY_TASK_ID "
            "and computes year = 2000 + task_id."
        ),
    )
    args = parser.parse_args()

    if args.year is not None:
        year = args.year
    else:
        task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])
        year = 2000 + task_id

    print(f"Year: {year} | Mode: {args.mode}")

    if args.mode in ("annual", "both"):
        aggregate_annual(year)

    if args.mode in ("monthly", "both"):
        aggregate_monthly(year)

    print("Done!")


if __name__ == "__main__":
    main()