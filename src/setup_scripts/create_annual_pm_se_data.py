"""
Python script to create annual global geojsons (2000-19) of gridded PM2.5 
estimates and sociodemographic data. Sociodemographic data are aggregated from
raster datasets into the 0.25° PM2.5 grid cells using rasterstats 'zonal_stats'
function. Script configured to be run as an array job, parallelised across 
years -- each yearly PM2.5 RDS file loaded in a separate job, indexed by SLURM
ARRAY TASK ID.
Date created: 26/12/2024
"""

import os
import warnings
import time
import itertools
import dask.delayed
import pyreadr
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
import dask
import dask.delayed as delayed
from dask.diagnostics import ProgressBar
import dask_geopandas as dgpd
from tobler.area_weighted import area_join
from utils import zonal_stats_for_gdf, point_to_gridcell, format_runtime, pop_weighted_zonal_stats_for_gdf

PM_RESOLUTION = 0.25
CHUNK_SIZE = 5000

DATA_PATH   = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
# OUT_PATH  = f'{os.getenv("SCRATCH_DIR")}/data/spatial/annual_global_pm_se_data'
OUT_PATH    = f'{os.getenv("SCRATCH_DIR")}/data/spatial/annual_global_pm_se_data_2000_2023' #update 28/07/2026: use Hu et al. 2000-2023 data

ADM0_PATH   = f'{DATA_PATH}/nat_boundaries/WB_countries_Admin0_10m/WB_countries_Admin0_10m.shp'

# Define raster metadata: variable names, dataset paths, temporal extent of data, band offset, statistic to compute
soc_metadata = [
    {
        "name": "pop_count",
        "path": f"{DATA_PATH}/glob_pop_counts/",
        "temporal_extent": (2000, 2023),            # Temporal range (start year, end year)
        'band_offset': 2000,                        # Band 1 corresponds to 1990, band 2 to 1991, etc.
        'stat_type': 'sum',                         # Zonal statistic to compute (sum, mean, etc.)
        'fname_str': 'ppp_XXXX_1km_Aggregated.tif'  # Naming convention of files in dir
    },
    {
        "name": "pop_count_urban",
        "path": f"{DATA_PATH}/urban_pop_counts/",
        "temporal_extent": (2000, 2023),
        'band_offset': 2000,
        'stat_type': 'sum',
        'fname_str': 'urban_pop_count_XXXX.tif'
    },
    {
        "name": "GDP_tot",
        "path": f"{DATA_PATH}/kummu_ses/rast_gdpTot_1990_2022_5arcmin.tif",
        "temporal_extent": (1990, 2022),
        'band_offset': 1990,
        'stat_type': 'sum'
    },
    {
        "name": "GDP_pc",
        "path": f"{DATA_PATH}/admin2/GDP/rast_adm2_gdp_perCapita_1990_2022.tif",
        "temporal_extent": (1990, 2022),
        'band_offset': 1990,
        'stat_type': 'mean'
    },
    {
        "name": "edu_f_mean_years",
        "path": f"{DATA_PATH}/education/ihme_lmic_edu_2000_2017_mean_15_49_female_mean.tif",
        "temporal_extent": (2000, 2017),
        'band_offset': 2000,
        'stat_type': 'mean'
    },
    {
        "name": "edu_m_mean_years",
        "path": f"{DATA_PATH}/education/ihme_lmic_edu_2000_2017_mean_15_49_male_mean.tif",
        "temporal_extent": (2000, 2017),
        'band_offset': 2000,
        'stat_type': 'mean'
    },
    {
        "name": "stunting_prev_u5",
        "path": f"{DATA_PATH}/stunting/",
        "temporal_extent": (2000, 2017),
        'band_offset': 2000,
        'stat_type': 'mean',
        'fname_str': 'ihme_lmic_cgf_2000_2017_stunting_prev_mean_XXXX.tif'
    },
    {
        "name": "imp_san_access_pct",
        "path": f"{DATA_PATH}/wash/",
        "temporal_extent": (2000, 2017),
        'band_offset': 2000,
        'stat_type': 'mean',
        'fname_str': 'ihme_lmic_wash_2000_2017_s_imp_percent_mean_XXXX.tif'
    }
]

# # Add metadata dicts for age-sex structures
# age_bands = [0, 1, 5] + list(range(10, 81, 5))
# age_sex_metadata = [(
#     {
#         "name": f"pop_count_f_{age_band}", 
#         "path": f"{DATA_PATH}/age_sex_struct/",
#         "temporal_extent": (2000, 2023),
#         "stat_type": "sum",
#         "fname_str": f"global_f_{age_band}_XXXX_1km.tif"
#     },
#     {
#         "name": f"pop_count_m_{age_band}", 
#         "path": f"{DATA_PATH}/age_sex_struct/",
#         "temporal_extent": (2000, 2023),
#         "stat_type": "sum",
#         "fname_str": f"global_m_{age_band}_XXXX_1km.tif"
#     }
# ) for age_band in age_bands]
# age_sex_metadata = list(itertools.chain(*age_sex_metadata)) # flatten tuples


# Add metadata dicts for age-sex structures
_AGE_BANDS_OLD = [0, 1, 5] + list(range(10, 81, 5)) # up to 80 (Age bands available in both old (≤2020) and new (2021+) series)
_AGE_BANDS_NEW_ONLY = [85, 90]                      # Additional age bands only available in new WorldPop 'Global2' data

age_sex_metadata = []
for age_band in _AGE_BANDS_OLD:
    for sex in ['f', 'm']:
        age_sex_metadata.append({
            "name": f"pop_count_{sex}_{age_band}",
            "path": f"{DATA_PATH}/age_sex_struct/",
            "temporal_extent": (2000, 2023),
            "stat_type": "sum",
            "fname_str": f"global_{sex}_{age_band}_XXXX_1km.tif"
        })
for age_band in _AGE_BANDS_NEW_ONLY:
    for sex in ['f', 'm']:
        age_sex_metadata.append({
            "name": f"pop_count_{sex}_{age_band}",
            "path": f"{DATA_PATH}/age_sex_struct/",
            "temporal_extent": (2021, 2023),  # only exists for 2021+
            "stat_type": "sum",
            "fname_str": f"global_{sex}_{age_band}_XXXX_1km.tif"
        })

# Add to full metadata list
soc_metadata = soc_metadata + age_sex_metadata

def process_metadata_pw_avg(year_gdf, year, meta, chunk_size):
    """
    Population-weighted means of the socioeconomic (SE) indicators. For rasters
    where the aggregation is 'sum' (e.g., pop counts etc.), the function evaluates
    regular (not population-weighted) aggregation.
    """
    print(f"Sampling zonal stats for raster data: {meta['name']} , year: {year}...", flush=True)
    if meta['temporal_extent'][0] <= year <= meta['temporal_extent'][1]:
        # If path is a TIFF, read and open select band
        if os.path.isfile(meta['path']):
            band = year - meta['band_offset'] + 1
            path = meta['path']

        # If path is a dir, open the select (single-band) TIFF file using naming convention
        else:
            fname = meta['fname_str'].replace('XXXX', str(year))
            path = os.path.join(meta['path'], fname)
            band = 1

        # Split GDF into chunks
        chunks = [year_gdf.iloc[i:i+chunk_size] for i in range(0, len(year_gdf), chunk_size)]

        # Regular zonal stats aggregation for summations
        if (meta['stat_type'] != 'mean'):
            # Compute zonal stats in parallel (across single node)
            delayed_results = [
                dask.delayed(zonal_stats_for_gdf)(
                    gdf=chunk, raster=path, band=band,
                    new_colname=meta['name'], stats=meta['stat_type']
                ) for chunk in chunks
            ]

        else: # Population-weighted averages
            # WorldPop metadata dict
            wpop_meta = next(i for i in soc_metadata if i['name']=='pop_count')

            # Read population raster for year
            wpop_src = rasterio.open( os.path.join( wpop_meta['path'], wpop_meta['fname_str'].replace('XXXX', str(year)) ) )
            
            # Load SE indicator -- note path constructed above
            se_src = rasterio.open( path )
            
            # Align wpop raster to SE raster
            t=time.time()
            print(f"Warping population count to match {meta['name']} raster...", flush=True)
            with WarpedVRT(
                wpop_src, crs=se_src.crs, transform=se_src.transform, 
                height=se_src.height, width=se_src.width, resampling=Resampling.sum, # summation resampling of pop count to lower res
                nodata=np.nan # set nodata as np.nan
            ) as vrt:
                wpop_data_warp = vrt.read(1) # wpop rasters are single band for each year
                print(f"Warping complete. Time taken to warp: {time.time()-t}", flush=True)
                
                # Read SE data (note `band` constructed above) and replace nodata with nan (vrt.nodata)
                se_data = se_src.read(band)
                se_data = np.where(se_data==se_src.nodata, vrt.nodata, se_data)
                
                # Compute population-weighted averages                
                delayed_results = [
                    dask.delayed(pop_weighted_zonal_stats_for_gdf)(
                        gdf=chunk, pop_data_warped=wpop_data_warp, pop_data_warped_vrt=vrt,
                        se_data=se_data, new_colname=meta['name']
                    ) for chunk in chunks
                ]
        
        # Compute results
        # with ProgressBar():
        #     results = dask.compute(*delayed_results)
        results = dask.compute(*delayed_results)
        year_gdf = pd.concat(results)
        return year_gdf

    # Fill NaNs if outside temporal extent
    year_gdf[meta['name']] = np.nan
    return year_gdf


# Function to process each year (to be parallelised across array jobs)
def process_year(year, data_path, soc_metadata, chunk_size, pm25_res, adm0_path):
    t0 = time.time()

    # Read in national boundaries
    adm0_gdf = gpd.read_file(adm0_path)
    print('Loaded admin 0 gdf!')
    print(f"Elapsed: {format_runtime(time.time() - t0)}", flush=True)
    # Define new colnames
    adm0_gdf['continent'] = adm0_gdf['CONTINENT'].copy()
    adm0_gdf['region'] = adm0_gdf['SUBREGION'].copy()
    adm0_gdf['country'] = adm0_gdf['WB_NAME'].copy()

    # Read in PM2.5 data for select year
    pm_df = pd.read_csv(os.path.join(data_path, f"pm25_hu_annual/fire_pm25_hu_annual_{year}.csv"))
    pm_df['year'] = year
    pm_df = pm_df.rename(columns={"pm25": "fire_PM25_hu"})  # label as Hu data column
    if year <= 2019:
        # Get Xu estimates for the years it exists
        pm_xu = pyreadr.read_r( os.path.join(data_path, f'pm25_xu/annual_avg{year}.rds') )[None]
        pm_df = pd.merge(pm_xu, pm_df, on=["lon", "lat"])
    
    # Convert to geodataframe
    pm_gdf = gpd.GeoDataFrame(
        pm_df, geometry=gpd.points_from_xy(pm_df['lon'], pm_df['lat']),
        crs=adm0_gdf.crs)
    print('PM2.5 GeoDataFrame created!')
    print(f"Elapsed: {format_runtime(time.time() - t0)}", flush=True)

    # Convert PM2.5 point geometries to polygons
    pm_ddf = dgpd.from_geopandas(pm_gdf, npartitions=5)
    pm_ddf['geometry'] = pm_ddf['geometry'].map_partitions(
        lambda df: df.apply(point_to_gridcell, res=pm25_res),
        meta=pd.Series(dtype='object')
    )
    pm_gdf = pm_ddf.compute()
    print('Point geometries converted to polygons!', flush=True)
    print(f"Elapsed: {format_runtime(time.time() - t0)}", flush=True)

    # Join PM2.5 data onto national boundaries
    adm0_vars = ['ISO_A3', 'country', 'region', 'continent', 'INCOME_GRP', 'ECONOMY', 'GDP_MD_EST']
    pm_chunks = [pm_gdf.iloc[i:i + chunk_size] for i in range(0, len(pm_gdf), chunk_size)]
    # Use dask.delayed to apply the area_join function to each chunk
    tasks = [delayed(area_join)(adm0_gdf, pm_chunk, adm0_vars) for pm_chunk in pm_chunks]
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Geometry is in a geographic CRS. Results from 'area' are likely incorrect.")
        results = dask.compute(*tasks)
    # Concat all chunks
    gdf = pd.concat(results)
    # Drop NA's -- grid cells not within a national boundary
    gdf = gdf[~gdf['country'].isna()]

    ### Loop through metadata dicts, compute zonal stats for each raster dataset  
    for meta in soc_metadata:
        gdf = process_metadata_pw_avg(gdf, year, meta, chunk_size)
        print(f"Zonal stats for {meta['name']} complete! Elapsed: {format_runtime(time.time() - t0)}\n", flush=True)
    print(f'Year: {year} zonal stats complete!', flush=True)
    print(f"Elapsed: {format_runtime(time.time() - t0)}", flush=True)

    return gdf

# Main logic -- uses SLURM_ARRAY_TASK_ID to process select year
def main():
    # Create the output dir if it doesn't exist
    if not os.path.exists(OUT_PATH):
        os.makedirs(OUT_PATH, exist_ok=True)
    
    # Get the task ID from the SLURM array task ID environment variable
    task_id = int(os.getenv("SLURM_ARRAY_TASK_ID"))

    # The years correspond to task IDs (0-19 corresponds to 2000-2019)
    year = 2000 + task_id

    # Check for file existence
    if os.path.exists( 
        os.path.join(OUT_PATH, f"gdf_pm_soc_{year}.geojson") ):
        print(f"File for {year} already exists. Finishing...")
        return 0

    # Analyse select year of data
    gdf_year = process_year(
        year, DATA_PATH, soc_metadata, CHUNK_SIZE, PM_RESOLUTION, ADM0_PATH)
    
    # Write full gdf to file
    gdf_year.to_file( os.path.join(OUT_PATH, f"gdf_pm_soc_{year}.geojson") )

    # Also write to CSV file
    pd.DataFrame(gdf_year).to_csv( os.path.join(OUT_PATH, f"gdf_pm_soc_{year}.csv"), index=False )

    print(f"Data processing for year: {year} complete!",
          f"Written to file: { os.path.join(OUT_PATH, f'gdf_pm_soc_{year}.geojson') }")

    return 0

if __name__ == "__main__":
    main()
