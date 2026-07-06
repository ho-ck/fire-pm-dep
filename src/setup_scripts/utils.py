import numpy as np
import pandas as pd
import warnings
from tqdm import tqdm
from rasterstats import gen_zonal_stats, zonal_stats
from shapely.geometry import box
import geopandas as gpd
from rapidfuzz import fuzz, process

from rasterio.io import MemoryFile
from rasterio.enums import Resampling
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT


def zonal_stats_for_gdf(gdf, raster, new_colname, stats="sum", band=1, display_progress=False):
    """
    A wrapper for the `gen_zonal_stats` function from the `rasterstats` package that calculates 
    zonal statistics for geometries in a GeoDataFrame and returns a modified copy with the 
    results added as a new column.

    This function computes zonal statistics, such as "sum" or "mean", for each geometry in 
    the input GeoDataFrame by analyzing the overlap with a raster dataset. The computed 
    statistics are added to a new column in the GeoDataFrame.

    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        The input GeoDataFrame containing the geometries for which zonal statistics will be calculated.
    raster : str or numpy.ndarray
        Either the file path to the raster dataset or a NumPy array representing the raster 
        data to be used for calculating zonal statistics. If a NumPy array is provided, 
        it must be aligned with the geometries in the GeoDataFrame.
    new_colname : str
        The name of the new column to be added to the GeoDataFrame, where the computed zonal statistics 
        will be stored.
    stats : str, optional (default="sum")
        The type of zonal statistic to compute. Supported statistics depend on the 
        `rasterstats.gen_zonal_stats` function. Common options include "sum", "mean", "max", and "min".
    band : int, optional (default=1)
        The raster band to use for the calculations. Defaults to the first band. Ignored if `raster` 
        is a NumPy array.
    display_progress : bool, optional (default=False)
        If True, displays a progress bar using `tqdm` to indicate the processing status.

    Returns:
    --------
    geopandas.GeoDataFrame
        A copy of the input GeoDataFrame with an additional column containing the computed 
        zonal statistics for each geometry.

    Notes:
    ------
    - This function uses `gen_zonal_stats` from the `rasterstats` package to perform the calculations.
    - The function modifies a copy of the input GeoDataFrame to ensure the original data remains unchanged.
    - The `stats` parameter must be compatible with the options supported by `gen_zonal_stats`.
    - If a NumPy array is provided as the raster, ensure it is properly aligned with the geometries in the GeoDataFrame.

    References:
    -----------
    For more details, see the `rasterstats` documentation: 
    https://pythonhosted.org/rasterstats/
    """
    tmp_gdf = gdf.copy()
    
    # Generate zonal stats (tot. pop counts) for each geometry in the gdf (with progressbar)
    gen = gen_zonal_stats(vectors=tmp_gdf, raster=raster, stats=stats, band=band)
    if display_progress:
        zonal_stats_values = [n for n in tqdm(gen, total=tmp_gdf.shape[0])]
    else:
        zonal_stats_values = [n for n in gen]
    
    # Add stats col to tmp_gdf
    tmp_gdf.loc[:, new_colname] = [i[stats] for i in zonal_stats_values]
    
    return tmp_gdf

def pop_weighted_zonal_stats_for_gdf(
    gdf, pop_data_warped, pop_data_warped_vrt, se_data, new_colname):
    """
    gdf: geodataframe to append the population-weighted SE indicator column to (can be a chunk)
    pop_data_warped: population count data that aligns with the SE data raster
    pop_data_warped_vrt: WarpedVRT object of the warped population count data (needed for transform, nodata attributes)
    se_data: numpy array of the socioeconomic raster data
    new_colname: new column name for the population-weighted socioeconomic data
    """
    # Numerator: zonal stats aggregation (summation) of the product of population count and SE data
    pop_x_se_data_agg = np.array([
        i['sum'] for i in gen_zonal_stats(vectors=gdf, raster=pop_data_warped*se_data, 
        nodata=pop_data_warped_vrt.nodata, stats='sum', affine=pop_data_warped_vrt.transform)
    ])
    pop_x_se_data_agg = np.array([i if i is not None else np.nan for i in pop_x_se_data_agg]) # replace None (rasterstats default output for nodata) with np.nan to allow elementwise division (returning np.nan)

    # Denominator: zonal stats summation of (warped) population count -- note warped data for consistency w/ numerator
    pop_data_warped_agg = np.array([
        i['sum'] for i in gen_zonal_stats(vectors=gdf, raster=pop_data_warped, 
        nodata=pop_data_warped_vrt.nodata, stats='sum', affine=pop_data_warped_vrt.transform)
    ])
    pop_data_warped_agg = np.array([i if i is not None else np.nan for i in pop_data_warped_agg])

    # Compute population-weighted averages
    pw_avg = pop_x_se_data_agg / pop_data_warped_agg
    
    # Append column with the population-weighted SE indicator
    gdf[new_colname] = pw_avg
    return gdf


def point_to_gridcell(point, res=0.25):
    """Function to convert point geometries to square polygons."""
    lon, lat = point.x, point.y
    return box(
        lon - res / 2, lat - res / 2,
        lon + res / 2, lat + res / 2)

def format_runtime(elapsed_seconds):
    """Formats the runtime into hours, minutes, and seconds."""
    hours, remainder = divmod(elapsed_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {seconds:.2f}s"

def resample_with_vrt(
    data_array, 
    src_transform, 
    out_transform, 
    out_width, 
    out_height,
    resampling_func=Resampling.bilinear,
    src_nodata=None,
    out_nodata=None,
    src_crs='EPSG:4326', 
    out_crs='EPSG:4326'):
    """
    Resamples a 2D data array using rasterio's WarpedVRT to match an output grid with specified transforms and 
    dimensions.
    
    Parameters:
        data_array (np.ndarray): Input 2D array to be resampled.
        src_transform (Affine): Affine transform of the input data.
        out_transform (Affine): Desired affine transform for output.
        out_width (int): Width of the resampled output.
        out_height (int): Height of the resampled output.
        resampling_func (Resampling): Resampling method from rasterio.enums.Resampling.
        src_nodata (float or int, optional): Nodata value of input.
        out_nodata (float or int, optional): Optional output nodata value. If not provided, defaults to src_nodata.
        src_crs (str or CRS): Coordinate reference system of the input data.
        out_crs (str or CRS): Desired output coordinate reference system.
    
    Returns:
        np.ndarray: Resampled 2D array.
    """
    src_crs = CRS.from_user_input(src_crs)
    out_crs = CRS.from_user_input(out_crs)

    if src_nodata is None:
        print("⚠️ Warning: src_nodata is not set. If your data contains fill values, "
              "they will be treated as valid during resampling.")
    if out_nodata is None:
        out_nodata = src_nodata
        
    # Create in-memory raster dataset from the input array & transform
    with MemoryFile() as memfile:
        with memfile.open(
            driver='GTiff',
            height=data_array.shape[0],
            width=data_array.shape[1],
            count=1,
            dtype=data_array.dtype,
            crs=src_crs,
            transform=src_transform,
            nodata=src_nodata
        ) as dataset:
            dataset.write(data_array, 1)

            # Define WarpedVRT w/ output CRS, transform, dimensions, and resampling method
            vrt_options = {
                'crs': out_crs,
                'transform': out_transform,
                'width': out_width,
                'height': out_height,
                'resampling': resampling_func,
                'src_nodata': src_nodata,
                'nodata': out_nodata
            }

            # Resample and reproject using WarpedVRT
            with WarpedVRT(dataset, **vrt_options) as vrt:
                resampled_array = vrt.read(1)  # Read single-band resampled output
                return resampled_array


if __name__ == "__main__":
    pass
