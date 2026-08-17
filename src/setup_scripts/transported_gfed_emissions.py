"""
Python script to compute sums of wind alignment-weighted neighbouring fire
emissions for African receptor grid cells (2000-2019 monthly). Source grid
cells are not restricted to Africa, so transported emissions from nearby
non-African cells can contribute to African receptors. Saves annual output CSV
files (each annual file containing all months 0-11).

Emissions are calculated for several 'bands' of surrounding grids (sources):
20-50km, 50-100km, 100-200km, 200-350km, 350-500km, 500-750km, 750-1000km,
1000-1500km, 1500-2000, 2000-3000km, 3000-5000km.

Also option to sum transported emissions by region/country, so can decompose 
into pollution components originating from each source region*

Date created: 30/10/2025
"""

import os
os.environ['PROJ_DATA'] = '/home/users/cho00/miniconda3/envs/pm/share/proj' # set path to proj.db
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
from tobler.area_weighted import area_join
from scipy.spatial import KDTree
from tqdm import tqdm
# import dask
# import dask.delayed
# from dask.diagnostics import ProgressBar

DATA_PATH       = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
OUT_PATH        = os.path.join(DATA_PATH, 
                               "fire_pm_dep_paper_data",                    # dir for data for paper
                            #    "transported_GFED_emissions_incl_global")    # transported emissions binned by source region, include global (non-Africa) sources
                               "transported_GFED_emissions_incl_global_2000_2023")  # update include GFED time series for 2000-2023

INPUT_DATA_DIR  = os.path.join(DATA_PATH, 
                               "fire_pm_dep_paper_data",
                            #    "regridded_climate_data")
                               "regridded_climate_data_2000_2023")
NAT_BOUNDS_PATH = os.path.join(DATA_PATH, "nat_boundaries/WB_countries_Admin0_10m")


# Source contribution groups. Use "region", "country", another source_gdf column,
# an array/Series of labels, or None to skip grouped source contributions.
SOURCE_GROUPS = "region"

# Transported emissions bands (km)
# THRESHOLDS = [50, 100, 200, 350, 500, 750, 1000, 1500, 2000, 3000, 5000]
THRESHOLDS = [50, 100, 200, 350, 500, 750, 1000, 1500, 2000]

# Lower bounds for each band (20km  for the first one [half a grid cell diagonal])
LOWER_BOUNDS = np.insert(THRESHOLDS[:-1], 0, 20)


def find_distanceband_sources(
    receptor_coords, source_coords, thresholds, lower_bounds, receptor_source_indices=None
):
    """
    For each receptor, find source-receptor pairs within each distance band.

    Parameters:
        receptor_coords (np.ndarray): Array of shape (n_receptors, 2) in projected units (meters).
        source_coords (np.ndarray): Array of shape (n_sources, 2) in projected units (meters).
        thresholds (list or np.ndarray): Upper bounds of distance bands in meters.
        lower_bounds (list or np.ndarray): Lower bounds for each distance band in meters.
        receptor_source_indices (np.ndarray, optional): For each receptor row, the matching
            source-row index. Used to exclude self-pairs when receptors are a subset of sources.

    Returns:
        dict: {band_upperbound_km: (receptor_indices, source_indices)} for each distance band.
    """
    # Create KDTree to find each coord's neighbours up to max dist
    tree = KDTree(source_coords)
    max_dist = thresholds[-1]

    # Ragged list: one source-index list per receptor, up to the largest band
    sources_list = tree.query_ball_point(receptor_coords, r=max_dist)

    if len(sources_list) == 0:
        return {int(upper / 1e3): (np.array([], dtype=int), np.array([], dtype=int))
                for upper in thresholds}
   
    # Flatten to get full (i, j) pairs -- each entry corresponds to an i-j pair, index by receptor i
    i_indices = np.repeat(
        # repeat each receptor index i for the number of sources j it has
        np.arange(len(sources_list)),
        [len(srcs) for srcs in sources_list]
    )
    j_indices = np.concatenate(sources_list).astype(int) # stack all the lists of sources (j's)

    # Exclude the receptor cell itself when receptors are drawn from the source grid
    if receptor_source_indices is not None:
        valid = j_indices != receptor_source_indices[i_indices]
        i_indices = i_indices[valid]
        j_indices = j_indices[valid]

    # Compute receptor-source distances vectorised
    disp_vecs = source_coords[j_indices] - receptor_coords[i_indices]
    dists = np.linalg.norm(disp_vecs, axis=1)

    # Dict to store receptor-source pairs for each band
    band_pairs = {}

    # Loop through radius 'bands' and bin receptor-source pairs in bands based on distance
    for lower, upper in tqdm(zip(lower_bounds, thresholds), total=len(thresholds)):
        in_band = (dists > lower) & (dists <= upper)
        band_pairs[int(upper / 1e3)] = (i_indices[in_band], j_indices[in_band])

    return band_pairs   # {band_uppperbound: (receptor_indices, source_indices)}


def sum_wind_weighted_emissions(
    receptor_coords, source_coords, u_wind, v_wind, gfed_emissions,
    band_pairs, source_groups=None, return_source_counts=False
):
    """
    Sum source emissions by distance band for each receptor, weighted by the
    cosine similarity between source wind direction and source-to-receptor
    displacement vector.

    Parameters:
        receptor_coords (np.ndarray): (n_receptors, 2) receptor centroids in projected CRS.
        source_coords (np.ndarray): (n_sources, 2) source centroids in projected CRS.
        u_wind (np.ndarray): Eastward wind component at each source grid cell.
        v_wind (np.ndarray): Northward wind component at each source grid cell.
        gfed_emissions (np.ndarray): Emissions at each source grid cell.
        band_pairs (dict): {band_upperbound_km: (receptor_indices, source_indices)}.
        source_groups (np.ndarray, optional): Group label for each source grid cell.
        return_source_counts (bool): If True, also return source counts per band.

    Returns:
        band_emissions : np.ndarray
            Shape (n_receptors, n_bands), total weighted emissions per band.
        band_source_counts : np.ndarray (optional)
            Shape (n_receptors, n_bands), number of source cells per band.
        group_emissions : np.ndarray
            Shape (n_receptors, n_bands, n_groups), weighted emissions per source group.
        group_list : list
            Sorted groups corresponding to the final axis of group_emissions.
    """
    n_receptors = receptor_coords.shape[0]
    n_bands = len(band_pairs)
    
    # Empty array (n_grids, n_bands) to store the sum of weighted emissions per band
    band_emissions = np.zeros((n_receptors, n_bands))
    
    # Empty array (n_grids, n_bands) to store the counts of emissions sources per band
    band_source_counts = (
        np.zeros((n_receptors, n_bands)) if return_source_counts else None
    )

    if source_groups is None:
        # No source-group decomposition requested; only compute total emissions by band
        group_list = []
        group_codes = None
        group_emissions = None
    else:
        # Convert labels like "Northern Africa" etc into stable integer codes
        source_groups = np.asarray(source_groups)
        group_list = sorted(np.unique(source_groups[~pd.isna(source_groups)]))
        group_to_code = {group: idx for idx, group in enumerate(group_list)}
        
        # One integer group code per source cell; missing groups get -1
        group_codes = np.array(
            [group_to_code.get(group, -1) for group in source_groups],
            dtype=int
        )
        group_emissions = np.zeros((n_receptors, n_bands, len(group_list)))

    # Loop through bands
    for band_idx, (upper, (flat_i, flat_j)) in enumerate(band_pairs.items()):
        if len(flat_j) == 0:
            # leave band_emissions as np.nan for receptor i with no sources j in band b
            continue

        # Displacement vectors (source -> receptor)
        # disp_vecs = receptor_coords[flat_i] - source_coords[flat_j]     # shape (n_pairs, 2)
        disp_vecs = np.subtract(receptor_coords[flat_i], source_coords[flat_j]) # shape (n_pairs, 2)
        
        # Wind vectors at sources
        wind_vecs = np.stack([u_wind[flat_j], v_wind[flat_j]], axis=1)  # shape (n_pairs, 2)

        # Dot products of the wind and displacement vectors (2-element vectors)
        dots = np.einsum('nm,nm->n', wind_vecs, disp_vecs)              # column of shape (n_pairs,)
        
        # Divide dots by norms of wind and disp vectors to get cosine similarity
        denom = np.linalg.norm(wind_vecs, axis=1) * np.linalg.norm(disp_vecs, axis=1)
        denom[denom == 0] = 1e-8    # avoid division by zero
        cos_sim = dots / denom      # shape (n_pairs,)

        # Weight emissions by cosine similarity (with lowerbound zero to 'switch off' negative weights [downwind emissions])
        weighted_emissions = gfed_emissions[flat_j] * np.maximum(0, cos_sim)
        
        # Sum weighted emissions by receptor index (i), across all sources for total band emissions
        band_emissions[:, band_idx] = np.bincount(
            flat_i, weights=weighted_emissions, minlength=n_receptors
        )

        if return_source_counts:
            band_source_counts[:, band_idx] = np.bincount(flat_i, minlength=n_receptors)

        # Sum emissions by region or country grouping if desired
        if group_codes is not None and len(group_list) > 0:
            source_group_codes = group_codes[flat_j]
            has_group = source_group_codes >= 0
            if np.any(has_group):
                combined_idx = (
                    flat_i[has_group] * len(group_list) + source_group_codes[has_group]
                )
                group_sums = np.bincount(
                    combined_idx,
                    weights=weighted_emissions[has_group],
                    minlength=n_receptors * len(group_list)
                )
                group_emissions[:, band_idx, :] = group_sums.reshape(
                    n_receptors, len(group_list)
                )

    return band_emissions, band_source_counts, group_emissions, group_list



def make_band_dataframe(values, prefix, thresholds, lower_bounds):
    """Convert receptor x aggregated band values (emissions/counts) to a DataFrame with distance-band column names."""
    return pd.DataFrame(
        values,
        columns=[
            f"{prefix}_{lower_bounds[b]}_{thresholds[b]}km"
            for b in range(len(thresholds))
        ]
    )

def make_group_band_dataframe(values, groups, thresholds, lower_bounds):
    """Convert receptor x band x source-group values to wide band-group columns."""
    if values is None or len(groups) == 0:
        return pd.DataFrame(index=range(values.shape[0] if values is not None else 0))

    colnames = [
        f"emis_{lower_bounds[b]}_{thresholds[b]}km_{groups[group_idx]}" # Column names for each band–region (or country) combination
        for b in range(len(thresholds))
        for group_idx in range(len(groups)) # cols are band0_region0, band0_region1, band0_region2, ..., band1_region0, band1_region1, band1_region2, ... etc. (i.e., unnest region index fastest)
    ]
    return pd.DataFrame(values.reshape(values.shape[0], -1), columns=colnames)  # Reshape from (N, B, R) to (N, B×R) -- unnests the last index (region) fastest


def resolve_source_groups(source_gdf, source_groups):
    """
    Return one source-group label per source row.

    source_groups can be a column name, an array/Series aligned to source_gdf rows,
    or None to skip grouped source decomposition.
    """
    if source_groups is None:
        return None
    if isinstance(source_groups, str):
        if source_groups not in source_gdf.columns:
            raise ValueError(f"source_groups column not found: {source_groups}")
        return np.array(source_gdf[source_groups])
    source_groups = np.asarray(source_groups)
    if len(source_groups) != len(source_gdf):
        raise ValueError(
            "source_groups must be None, a source_gdf column name, or one label per source row"
        )
    return source_groups


def process_month(
    chunk, thresholds, lower_bounds, # note thresholds/lowerbounds must be in km!
    source_groups="region"
):
    # Convert global monthly source pool to GeoDataFrame. Do not filter sources to Africa:
    # transported emissions from neighbouring continents can affect African receptors
    source_gdf = gpd.GeoDataFrame(
        chunk.copy(), geometry=gpd.GeoSeries.from_wkt(chunk['geometry']),
        crs='EPSG:4326'
    )

    # Remove cells where lat is +- 90 (leads to Inf when reprojecting)
    source_gdf = source_gdf[
        (source_gdf["lat"] > -90)
        & (source_gdf["lat"] < 90)
    ].reset_index(drop=True)

    # Only include receptor grid cells for Africa
    receptor_mask = source_gdf['continent'] == 'Africa'
    receptor_gdf = source_gdf[receptor_mask].reset_index(drop=True)

    # Project lon/lat grid centres directly (from points); do not use polygon centroids
    # because cells crossing the antimeridian produce invalid centroids in EPSG:3857
    # Transform grid-cell centre coordinates to EPSG:3857 (projected coords in metres)
    WGS84_TO_WEBMERC = Transformer.from_crs(
        "EPSG:4326",
        "EPSG:3857",
        always_xy=True
    )

    source_x, source_y = WGS84_TO_WEBMERC.transform(
        source_gdf["lon"].to_numpy(),
        source_gdf["lat"].to_numpy()
    )
    source_coords = np.column_stack((source_x, source_y))

    receptor_x, receptor_y = WGS84_TO_WEBMERC.transform(
        receptor_gdf["lon"].to_numpy(),
        receptor_gdf["lat"].to_numpy()
    )
    receptor_coords = np.column_stack((receptor_x, receptor_y))
    
    # Indices of receptors (indexing source_gdf), such that they can be excluded as sources
    receptor_source_indices = np.flatnonzero(receptor_mask.to_numpy())

    # Convert thresholds/lowerbounds to metres
    thresholds_m = np.array(thresholds) * 1e3
    lower_bounds_m = np.array(lower_bounds) * 1e3

    # 1. Find source-receptor pairs for each distance band
    band_pairs = find_distanceband_sources(
        receptor_coords, source_coords, thresholds_m, lower_bounds_m,
        receptor_source_indices=receptor_source_indices
    )

    # 2. Aggregate total emissions by band, then optionally decompose those same
    #    weighted source-receptor pairs by source group (e.g., region)
    source_group_labels = resolve_source_groups(source_gdf, source_groups)
    band_emissions, band_source_counts, group_emissions, group_list = (
        sum_wind_weighted_emissions(
            receptor_coords,
            source_coords,
            u_wind=np.array(source_gdf['u10']),
            v_wind=np.array(source_gdf['v10']),
            gfed_emissions=np.array(source_gdf['gfed_PM25_mass_emis']),
            band_pairs=band_pairs,
            source_groups=source_group_labels,
            return_source_counts=True
        )
    )

    # Convert to tabular data
    emissions_df = make_band_dataframe(band_emissions, "emis", thresholds, lower_bounds)
    source_counts_df = make_band_dataframe(
        band_source_counts, "N_sources", thresholds, lower_bounds
    )
    group_emissions_df = make_group_band_dataframe(
        group_emissions, group_list, thresholds, lower_bounds
    )

    # Horizontal concat emissions cols onto gdf (original CRS)
    # Returns gdf with monthly transported emissions for each band
    return pd.concat(
        [receptor_gdf, emissions_df, source_counts_df, group_emissions_df],
        axis=1
    )


def main():
    # Create the output dir if it doesn't exist
    if not os.path.exists(OUT_PATH):
        os.makedirs(OUT_PATH, exist_ok=True)

    # Get the task ID from the SLURM array task ID environment variable 
    task_id = int(os.getenv("SLURM_ARRAY_TASK_ID"))

    # The years correspond to task IDs (0-19 corresponds to 2000-2019)
    year = 2000 + task_id

    # -----------------------------------------------------
    # Load data
    # -----------------------------------------------------
    print("Loading data...", flush=True)
    
    # Monthly Xu, GFED, ERA5 CSV files (with gridcell WKT geometries)
    df = pd.read_csv(
        os.path.join(INPUT_DATA_DIR, f"monthly_xu_pm25_gfed_era5_{year}.csv")
    )

    # Load nat bounds. Keep all countries so non-African source cells can be labelled
    # and included when they fall inside a receptor distance band
    nat_bounds = gpd.read_file(NAT_BOUNDS_PATH).rename(
        columns={"CONTINENT": "continent", "WB_NAME": "country", "SUBREGION": "region"} # rename columns from shapefile
    )

    # Join nat bounds onto df using area_join
    gdf_month_0 = gpd.GeoDataFrame( # create geodataframe from 1 month of data (do area_join for 1 month, then use regular joins by lon, lat for speed. because lon, lat are repeated for each month)
        df[df['month']==0], 
        geometry=gpd.GeoSeries.from_wkt(df[df['month']==0].geometry),
        crs=nat_bounds.crs
    )
    gdf_month_0 = gdf_month_0[['lon', 'lat', 'geometry']] # just keep lon, lat, geometry
    gdf_month_0 = area_join( # area_join country, region, continent, iso3 onto lon, lat
        source_df=nat_bounds,
        target_df=gdf_month_0,
        variables=['ISO_A3', 'country', 'region', 'continent']
    )
    df = df.merge(gdf_month_0[['lon', 'lat', 'ISO_A3', 'country', 'region', 'continent']]) # regular join country info onto df

    # -----------------------------------------------------
    # Compute surrounding wind weighted emissions by month
    # -----------------------------------------------------
    tqdm.pandas()

    # Split df into monthly chunks
    chunks = [ df[df['month']==m] for m in range(0, 12) ]

    # Process data (compute monthly wind-weighted neighbour emissions)
    print("Computing transported emissions by month...", flush=True)
    results = [ 
        process_month(
            chunk, THRESHOLDS, LOWER_BOUNDS, source_groups=SOURCE_GROUPS
        ) for chunk in tqdm(chunks, total=len(chunks))
    ]
    # delayed_results = [
    #     dask.delayed(process_month)(
    #         chunk, THRESHOLDS, LOWER_BOUNDS, nat_bounds
    #     ) for chunk in chunks
    # ]

    # # Compute results
    # with ProgressBar():
    #     results = dask.compute(*delayed_results, scheduler="processes")
    
    # Concat monthly chunks to annual GeoDataFrame
    year_gdf = pd.concat(results).reset_index(drop=True)

    # -----------------------------------------------------
    # Convert to dataframe and write CSV
    # -----------------------------------------------------
    year_gdf = pd.DataFrame(year_gdf)
    year_gdf['geometry'] = year_gdf['geometry'].apply(lambda geom: geom.wkt)

    print("Writing to CSV...", flush=True)
    year_gdf.to_csv(os.path.join(OUT_PATH, f"monthly_transported_GFED_emissions_{year}.csv"))
    
    print(f"Processing for year: {year} complete! Written to file: monthly_transported_GFED_emissions_{year}.csv")


if __name__ == "__main__":
    print("Starting...", flush=True)
    main()
    print("Done!", flush=True)

