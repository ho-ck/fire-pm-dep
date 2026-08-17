"""
Python script to create GeoTIFFs for population count living in an urban area.
Uses WorldPop population counts and GHS-SMOD gridded urban classification.
Date created: 22/01/2024
"""

import os
os.environ['PROJ_DATA'] = '/home/users/cho00/miniconda3/envs/pm/share/proj' # set path to proj.db
import numpy as np
import rasterio
from tqdm import tqdm
from pathlib import Path

from rasterio.io import MemoryFile
from rasterio.features import shapes
from rasterio.mask import mask
from rasterio.enums import Resampling
from rasterio.warp import reproject

DATA_PATH = Path(os.environ["SCRATCH_DIR"]) / "data" / "spatial"
GHSL_DIR = os.path.join(DATA_PATH, "GHSL")
WPOP_DIR = os.path.join(DATA_PATH, "glob_pop_counts")
OUT_DIR = os.path.join(DATA_PATH, "urban_pop_counts")

# Helper function to create an in-memory rasterio dataset from 2D array, transform and CRS
def create_dataset(data, crs, transform, nodata=None):
    memfile = MemoryFile()
    dataset = memfile.open(driver='GTiff', height=data.shape[0], width=data.shape[1], count=1, crs=crs, 
                           transform=transform, dtype=data.dtype, nodata=nodata)
    dataset.write(data, 1)
    return dataset

if __name__ == "__main__":
    print('Starting...')

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    for year in tqdm(range(2000, 2024)):

        # Name for output path
        out_path = os.path.join(OUT_DIR, f"urban_pop_count_{year}.tif")

        if os.path.isfile(out_path):
            print(f"Skipping {year} — output already exists")
            continue

        # Load WorldPop raster
        wpop_src = rasterio.open( os.path.join(WPOP_DIR, f"ppp_{year}_1km_Aggregated.tif") )
        wpop_data = wpop_src.read(1)
        print('WorldPop raster loaded!', flush=True)

        # Load GHS-SMOD raster (only updated every 5 years)
        ghs_src = rasterio.open( os.path.join(GHSL_DIR, f"GHS_SMOD_E{year-(year%5)}_GLOBE_R2023A_54009_1000_V2_0.tif") )
        print('GHS-SMOD raster loaded!', flush=True)

        ### Align GHS-SMOD raster with WorldPop

        # Reproject to WorldPop crs (EPSG:4326) and resolution (0.008333°)
        ghs_reproj, ghs_reproj_tf = reproject(
            source=rasterio.band(ghs_src, 1),
            dst_crs=wpop_src.crs,
            dst_resolution=wpop_src.res,
            src_nodata=ghs_src.nodata,
            dst_nodata=ghs_src.nodata,
            resampling=Resampling.nearest
        )
        print('GHS-SMOD reprojected to WorldPop!', flush=True)

        # Create dataset of reprojected data
        ghs_reproj_ds = create_dataset(
            data=ghs_reproj[0], crs=wpop_src.crs, transform=ghs_reproj_tf,
            nodata=ghs_src.nodata
        )

        # Get the extents of WorldPop raster as a polygon
        extents, _ = next( shapes(
            np.zeros((wpop_src.height, wpop_src.width)),
            transform=wpop_src.transform
        ) )

        # Do cropping
        ghs_crop, ghs_crop_tf = mask(ghs_reproj_ds, [extents], crop=True, nodata=ghs_reproj_ds.nodata)
        print('GHS-SMOD cropped to WorldPop extents!', flush=True)

        # Alignment is out by 1 column -- likely due to rounding error in transformations
        # Chris note 22/01: the final columns of both ghs_crop and wpop_data are all nodata.
        # Thus just drop the extra col in ghs_crop

        # Crop to wpop_data array shape
        ghs_crop = ghs_crop[0][:wpop_data.shape[0], :wpop_data.shape[1]]
        

        ### Convert aligned GHS-SMOD data to binary urban/rural
        # Values [30, 23, 22, 21] are urban, [13, 12, 11, 10] are rural

        # First convert nodata to np.nan
        ghs_urban =  np.where(ghs_crop == ghs_reproj_ds.nodata, np.nan, ghs_crop)
        
        # Convert to 1/0 binary urban/rural using classification above
        ghs_urban = np.where( np.isnan(ghs_urban), np.nan, np.where(ghs_urban>=21, 1, 0) )

        ### Multiply urban classification by population count
        # Convert WorldPop nodata to nan
        wpop_data = np.where( wpop_data==wpop_src.nodata, np.nan, wpop_data )

        # Multiply population count by urban classification
        wpop_urban = ghs_urban * wpop_data
        print('Urban population counts evaluated!', flush=True)

        # Save to output file
        with rasterio.open(
            out_path, 'w', driver='GTiff', count=1, dtype=wpop_src.meta['dtype'], 
            width=wpop_urban.shape[1], height=wpop_urban.shape[0], crs=wpop_src.crs,
            transform=wpop_src.transform, nodata=np.nan ) as dst:
            dst.write(wpop_urban, 1)
            print(f"Data for year {year} written to file: {out_path}", flush=True)

        