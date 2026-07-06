"""
Python script to align datasets: GFED4s, Global Fire Atlas, ERA5 montly 
reanalysis to common Xu PM2.5 grid (0.25°). Saves output CSV files with 
spatially aligned montly data for 2000-2019 (annual files). Uses rasterio
WarpedVRT with bilinear interpolation resampling.

Date created: 26/08/2025
"""

import os
os.environ['PROJ_DATA'] = '/home/users/cho00/miniconda3/envs/pm/share/proj' # set path to proj.db

import numpy as np
import pandas as pd
import h5py
import pyreadr
import rasterio
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from utils import resample_with_vrt, point_to_gridcell
import xarray as xr
from shapely.geometry import Point, box
from tqdm import tqdm

# Paths
DATA_PATH   = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
OUT_PATH    = os.path.join(DATA_PATH, 
                           "fire_pm_dep_paper_data",    # dir for data for paper
                           "regridded_climate_data")

GFED_DIR        = os.path.join(DATA_PATH, "GFED")
XU_MONTHLY_DIR  = os.path.join(DATA_PATH, "monthly_pm25_xu")
GFA_DIR         = os.path.join(DATA_PATH, "Global_Fire_Atlas") # Global Fire Atlas -- fire size and no. ignitions
ERA5_PATH       = os.path.join(DATA_PATH, "ERA5/ERA5_monthly_averaged_reanalysis.grib") # includes wind, temp, dewpoint, pressure
ERA5_PRECIP_PATH    = os.path.join(DATA_PATH, "ERA5/ERA5_monthly_averaged_reanalysis_precip.grib") # ERA5 precipitation file

# Spatial resolutions (degrees)
xu_res      = 0.25
gfed_res    = 0.25
era5_res    = 0.25

# UPDATE 16/10: using NN resampling for GFED emissions to preserve spikes and zero-values
GFED_RESAMPLING = Resampling.nearest

def calculate_GFED_montly_emissions(year, GFED_path):
    """
    Calculates monthly PM emissions from GFED4.1s for a given year.

    Reads dry matter (DM) emissions and source partitioning from GFED4.1s HDF5 files, 
    applies source-specific emission factors, and computes total PM emissions using 
    the 10th row of the emission factor table.

    Parameters:
        year (int): Year to process (e.g., 2005).
        GFED_path (str): Path to dir containing GFED4.1s data and emission factor file.

    Returns:
        dict: A dictionary mapping each month (0-11) to:
            - 'emissions': 2D NumPy array (720 x 1440) of PM emissions
            = 'mass_emis': 2D NumPy array (720 x 1440) of PM emissions mass (g PM2.5 per month)
            - 'lon': 2D NumPy array (720 x 1440) of longitude values (of grid)
            - 'lat': 2D NumPy array (720 x 1440) of latitude values

    Note:
        Adapted from https://www.geo.vu.nl/~gwerf/GFED/GFED4/ancill/code/get_GFED4s_CO_emissions.py
    """
    months       = '01','02','03','04','05','06','07','08','09','10','11','12'
    sources      = 'SAVA','BORF','TEMF','DEFO','PEAT','AGRI'
    directory    = GFED_path

    # Read in emission factors
    species = [] # names of the different gas and aerosol species
    EFs     = np.zeros((41, 6)) # 41 species, 6 sources

    k = 0
    f = open(directory+'/GFED4_Emission_Factors.txt')
    while 1:
        line = f.readline()
        if line == "":
            break
            
        if line[0] != '#':
            contents = line.split()
            species.append(contents[0])
            EFs[k,:] = contents[1:]
            k += 1
                    
    f.close()

    # we are interested in PM for this example (10th row):
    EF_PM = EFs[9,:]

    string = directory+'/GFED4.1s_'+str(year)+'.hdf5'
    f = h5py.File(string, 'r')
    
    # Areas of grid cells (constant throughout dataset)
    grid_cell_area = f['ancill/grid_cell_area'][:]
    GFED_monthly = {}
    
    for month in tqdm(range(12)):
        GFED_monthly[month] = {}
        GFED_monthly[month]['emissions'] = np.zeros((720, 1440))
        GFED_monthly[month]['mass_emis'] = np.zeros((720, 1440))
        GFED_monthly[month]['lon'] = f['lon'][:]
        GFED_monthly[month]['lat'] = f['lat'][:]
        # read in DM emissions
        string = '/emissions/'+months[month]+'/DM'
        DM_emissions = f[string][:]
        for source in range(6):
            # read in the fractional contribution of each source
            string = '/emissions/'+months[month]+'/partitioning/DM_'+sources[source]
            contribution = f[string][:]
            # calculate CO emissions as the product of DM emissions (kg DM per 
            # m2 per month), the fraction the specific source contributes to 
            # this (unitless), and the emission factor (g CO per kg DM burned)
            GFED_monthly[month]['emissions'] += DM_emissions * contribution * EF_PM[source]
            # Calculate mass of PM2.5 emissions (g PM.5 per month) by multiplying 
            # the above by the grid cell area (m^2)
            GFED_monthly[month]['mass_emis'] += DM_emissions * contribution * EF_PM[source] * grid_cell_area

    return GFED_monthly


def concat_xu_montly_pm25(year, xu_montly_path):
    """
    Loads and concatenates monthly PM2.5 data files for a given year from Xu et al.

    Parameters:
        year (int): The year of the data to load.
        xu_montly_path (str): Path to the directory containing the monthly .rds files.

    Returns:
        dict: A dictionary where keys are month indices (0–11) and values are DataFrames 
              containing PM2.5 data with added 'month' and 'year' columns.
    """
    xu_pm25_monthly = {}
    for month in tqdm(range(12)):
        df = pyreadr.read_r(os.path.join(
            xu_montly_path,
            f"Monthly_average{year}{str(month+1).zfill(2)}.rds" # convert month 0 (Jan) to '01' etc.
        ))[None] # get the df
        df['month'] = month
        df['year'] = year
        xu_pm25_monthly[month] = df

    return xu_pm25_monthly


def process_month(month, year, xu_pm25_dict, GFED_dict, gfa_ignitions_src, gfa_size_src, era5_ds, era5_precip_ds):
    """
    Spatially aligns GFED, GFA, ERA5 for a given month and year to the Xu PM2.5 grid, using WarpedVRT resampling with 
    bilinear interpolation.

    Parameters:
        month (int): Month index (0–11) to process.
        year (int): Year of the data to process (e.g., 2003).
        xu_pm25_dict (dict): Dictionary of monthly Xu PM2.5 DataFrames for a given year, keyed by month index.
        GFED_dict (dict): Dictionary of GFED emission DataFrames for a given year, keyed by month index.
        gfa_ignitions_src (rasterio.DatasetReader): Global Fire Atlas ignitions raster with 12 monthly bands (1-12).
        gfa_size_src (rasterio.DatasetReader): Global Fire Atlas average fire size raster with 12 monthly bands (1-12).
        era5_ds (xarray.Dataset): ERA5 dataset with monthly wind data ('u10', 'v10') from 2000–2019, indexed by datetime.

    Returns:
        pd.DataFrame: Xu PM2.5 grid for the given month with spatially aligned fire and wind data,
                      including geometry column (WKT grid cells).
    """

    ### --- 1. Define target grid (Xu) ---
    df_xu   = xu_pm25_dict[month]
    lons_xu = np.sort(df_xu['lon'].unique())
    lats_xu = np.sort(df_xu['lat'].unique())[::-1]
    width_xu    = len(lons_xu) # no. of grid cells
    height_xu   = len(lats_xu)
    transform_xu    = from_origin(
        lons_xu.min() - xu_res/2, lats_xu.max() + xu_res/2, xu_res, xu_res
    )

    # Create full grid of Xu grid cells
    lon_grid_xu, lat_grid_xu = np.meshgrid(lons_xu, lats_xu)

    ### --- 2. Align GFED to Xu ---
    # Define GFED (source) transform
    transform_gfed = from_origin(
        west    = GFED_dict[month]['lon'].min() - gfed_res/2,
        north   = GFED_dict[month]['lat'].max() + gfed_res/2,
        xsize   = gfed_res, ysize=gfed_res
    )
    
    # Resample GFED emissions (flux) to match Xu grid
    gfed_resampled  = resample_with_vrt(
        data_array      = GFED_dict[month]['emissions'],
        src_transform   = transform_gfed,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = GFED_RESAMPLING, #Resampling.bilinear,
        src_nodata      = None,   # GFED has no missing/fill values
    )

    # Resample GFED emissions (mass) to match Xu
    gfed_mass_emis_resampled = resample_with_vrt(
        data_array      = GFED_dict[month]['mass_emis'],
        src_transform   = transform_gfed,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = GFED_RESAMPLING, #Resampling.bilinear,
        src_nodata      = None,   # GFED has no missing/fill values
    )

    # Convert back to dataframe and join onto Xu
    df_gfed_aligned = pd.DataFrame({
        'lon': lon_grid_xu.ravel(),
        'lat': lat_grid_xu.ravel(),
        'gfed_PM25': gfed_resampled.ravel(),
        'gfed_PM25_mass_emis': gfed_mass_emis_resampled.ravel(),
        'month': month,
        'year': year,
    })
    df_xu = df_xu.merge(df_gfed_aligned, on=['lon', 'lat', 'month', 'year'])

    # --- 3. Align Global Fire Atlas to Xu ---
    if gfa_ignitions_src is not None and gfa_size_src is not None: # datasets will be None for years outside of 2003-2016 (inclusive)
        # Resample ignitions
        gfa_ignitions_resampled = resample_with_vrt(
            data_array      = gfa_ignitions_src.read(month+1), # monthly bands are 1-indexed
            src_transform   = gfa_ignitions_src.transform,
            src_nodata      = gfa_ignitions_src.nodata,
            out_transform   = transform_xu,
            out_width       = width_xu,
            out_height      = height_xu,
            resampling_func = Resampling.bilinear,
            out_nodata      = np.nan
        )

        # Resample fire size
        gfa_size_resampled = resample_with_vrt(
            data_array      = gfa_size_src.read(month+1),
            src_transform   = gfa_size_src.transform,
            src_nodata      = gfa_size_src.nodata,
            out_transform   = transform_xu,
            out_width       = width_xu,
            out_height      = height_xu,
            resampling_func = Resampling.bilinear,
            out_nodata      = np.nan
        )

        # Convert back to dataframe and join onto Xu
        df_gfa_aligned = pd.DataFrame({
            'lon': lon_grid_xu.ravel(),
            'lat': lat_grid_xu.ravel(),
            'gfa_n_ignitions': gfa_ignitions_resampled.ravel(),
            'gfa_avg_fire_size': gfa_size_resampled.ravel(),
            'month': month,
            'year': year,
        })
    else:
        # Fill with NaNs if no GFA data
        df_gfa_aligned = pd.DataFrame({
            'lon': lon_grid_xu.ravel(),
            'lat': lat_grid_xu.ravel(),
            'gfa_n_ignitions': np.nan,
            'gfa_avg_fire_size': np.nan,
            'month': month,
            'year': year,
        })
    df_xu = df_xu.merge(df_gfa_aligned, on=['lon', 'lat', 'month', 'year'])

    # --- 4. Align ERA5 winds to Xu ---
    # Select year and month (day is always 01 for monthly-averaged ERA5)
    time_sel        = np.datetime64(f"{year}-{str(month+1).zfill(2)}-01") # convert month '0' to '01' etc.
    era5_sel        = era5_ds.sel(time=time_sel)
    era5_precip_sel = era5_precip_ds.sel(time=time_sel, method="nearest") # precip index is last day of prev month instead of first day of current month

    # Extract lon, lat, u10, v10 arrays
    lon_era5    = era5_sel.longitude.values  # 1D array
    lat_era5    = era5_sel.latitude.values   # 1D array
    u10         = era5_sel.u10.values        # 2D array lat x lon
    v10         = era5_sel.v10.values        # 2D array lat x lon
    d2m         = era5_sel.d2m.values        # 2m dewpoint temp
    t2m         = era5_sel.t2m.values        # 2m temp
    sp          = era5_sel.sp.values         # surface pressure
    tp          = era5_precip_sel.tp.values  # total precipitation

    # Define ERA5 (source) transform
    transform_era5 = from_origin(
        west    = lon_era5.min() - era5_res / 2,
        north   = lat_era5.max() + era5_res / 2,
        xsize   = era5_res,
        ysize   = era5_res
    )

    # Resample to match Xu grid
    u10_resampled = resample_with_vrt(
        data_array      = u10,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,   # ERA5 has no missing/fill values
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         = 'EPSG:4326'
    )

    v10_resampled = resample_with_vrt(
        data_array      = v10,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         = 'EPSG:4326'
    )

    d2m_resampled = resample_with_vrt(
        data_array      = d2m,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         = 'EPSG:4326'
    )

    t2m_resampled = resample_with_vrt(
        data_array      = t2m,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         = 'EPSG:4326'
    )

    sp_resampled = resample_with_vrt(
        data_array      = sp,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         ='EPSG:4326'
    )

    tp_resampled = resample_with_vrt(
        data_array      = tp,
        src_transform   = transform_era5,
        out_transform   = transform_xu,
        out_width       = width_xu,
        out_height      = height_xu,
        resampling_func = Resampling.bilinear,
        src_nodata      = None,
        out_nodata      = np.nan,
        src_crs         = 'EPSG:4326',
        out_crs         = 'EPSG:4326'
    )

    # Convert back to dataframe and join onto Xu
    df_era5_aligned = pd.DataFrame({
        'lon':  lon_grid_xu.ravel(),
        'lat':  lat_grid_xu.ravel(),
        'u10':  u10_resampled.ravel(),
        'v10':  v10_resampled.ravel(),
        'd2m':  d2m_resampled.ravel(),
        't2m':  t2m_resampled.ravel(),
        'sp':   sp_resampled.ravel(),
        'tp':   tp_resampled.ravel(),
        'month':    month,
        'year': year,
    })
    df_xu = df_xu.merge(df_era5_aligned, on=['lon', 'lat', 'month', 'year'])

    ### --- 5. Create shapely geometries (for geopandas, sf later) ---
    # Create Point geometries
    df_xu['geometry'] = df_xu.apply(lambda row: Point(row['lon'], row['lat']), axis=1)

    # Convert to grid cells
    df_xu['geometry'] = df_xu['geometry'].apply(point_to_gridcell, res=0.25)

    # Convert grid cells to WKT
    df_xu['geometry'] = df_xu['geometry'].apply(lambda geom: geom.wkt)

    return df_xu


def main():
    # Create the output dir if it doesn't exist
    if not os.path.exists(OUT_PATH):
        os.makedirs(OUT_PATH, exist_ok=True)
    
    # Get the task ID from the SLURM array task ID environment variable -- CHRIS NOTE 26/08: I would have preferred to do this (parallel across years) but SLURM queue was too long to submit batch job (so just ran in interactive terminal).
    task_id = int(os.getenv("SLURM_ARRAY_TASK_ID"))

    # The years correspond to task IDs (0-19 corresponds to 2000-2019)
    year = 2000 + task_id

    ### --- Load ERA5 data (contains all years) ---
    print("Loading ERA5...", flush=True)
    era5 = xr.load_dataset(ERA5_PATH, engine="cfgrib")

    # Process ERA5 -- wrap lon coords from [0,360] to [-180,180] (https://docs.xarray.dev/en/stable/generated/xarray.Dataset.assign_coords.html#Examples)
    print("Converting ERA5 lon to [-180, 180]...", flush=True)
    era5 = era5.assign_coords(
        longitude=(((era5.longitude + 180) % 360) - 180)
    )
    # Now sort by longitude -- so that u10, v10 rasters have [-180, 90 in top left corner]
    era5 = era5.sortby('longitude')

    # Load ERA5 precip data (stored in a different file bc the months are indexed differently)
    # (e.g., last day of Dec insted of 1st of Jan -- index using 'nearest' method)
    era5_precip = xr.load_dataset(ERA5_PRECIP_PATH, engine="cfgrib")    
    era5_precip = era5_precip.assign_coords(
        longitude=(((era5_precip.longitude + 180) % 360) - 180)
    )
    era5_precip = era5_precip.sortby('longitude')

    # for year in range(2000, 2020):

    ### --- 0. Load monthly data for the year ---
    print("Loading Xu...", flush=True)
    xu_pm25_monthly = concat_xu_montly_pm25(year, XU_MONTHLY_DIR)
    print("Loading GFED...", flush=True)
    GFED_monthly = calculate_GFED_montly_emissions(year, GFED_DIR)
    
    print("Loading GFA...", flush=True)
    # Load GFA rasters only if year is within 2003-2016
    if 2003 <= year <= 2016:
        gfa_ignitions_src = rasterio.open(os.path.join(GFA_DIR, f"Global_fire_atlas_ignitions_monthly_{year}.tif"))
        gfa_size_src = rasterio.open(os.path.join(GFA_DIR, f"Global_fire_atlas_size_monthly_{year}.tif"))
    else:
        gfa_ignitions_src = None
        gfa_size_src = None

    ### --- 1. Loop through months and do regridding / resampling ---
    print("Doing monthly regridding...", flush=True)
    monthly_dfs = []
    for month in tqdm(range(0, 12)):

        df_month = process_month(
            month, year, xu_pm25_dict=xu_pm25_monthly, GFED_dict=GFED_monthly,
            gfa_ignitions_src=gfa_ignitions_src, gfa_size_src=gfa_size_src, era5_ds=era5,
            era5_precip_ds=era5_precip
        )

        monthly_dfs.append(df_month)

    ### --- 2. Concat all months for the year ---
    df_full_year = pd.concat(monthly_dfs)

    ### -- 3. Export to CSV ---
    print("Writing to CSV...")
    df_full_year.to_csv(os.path.join(OUT_PATH, f"monthly_xu_pm25_gfed_gfa_era5_{year}.csv"), index=False)
    print(f"Written to CSV. Data processing for year: {year} completed.")


if __name__ == "__main__":
    print("Starting...", flush=True)
    main()
    print("Done!", flush=True)
