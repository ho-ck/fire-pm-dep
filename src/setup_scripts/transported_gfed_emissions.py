"""
Python script to compute sums of wind alignment-weighted neighbouring fire
emissions for all receptor grid cells (Africa, 2000-2019 monthly). Saves annual
output CSV files (each annual file containing all months 0-11).

Note this is an updated version of `transported_gfed_emissions.py`. Here, 
emissions are calculated for several 'bands' of surrounding grids (sources):
0-50km, 50-100km, 100-200km, 200-350km, 250-500km, 500-750km, 750-1000km,
1000-1500km, 1500-2000, 2000-3000km, 3000-5000km.

*v3 update -- also sum transported emissions by region, so can decompose into 
components emissions originating from each source region*

Date created: 30/10/2025
"""

import os
os.environ['PROJ_DATA'] = '/home/users/cho00/miniconda3/envs/pm/share/proj' # set path to proj.db
import numpy as np
import pandas as pd
import geopandas as gpd
from tobler.area_weighted import area_join
from scipy.spatial import KDTree
from tqdm import tqdm
import dask
import dask.delayed
from dask.diagnostics import ProgressBar

DATA_PATH   = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
OUT_PATH    = os.path.join(DATA_PATH, 
                           "fire_pm_dep_paper_data",    # dir for data for paper
                           "transported_GFED_emissions_regional")  # transported emissions binned by source region
# OUT_PATH  = os.path.join(DATA_PATH, "transported_GFED_emissions_country")  # transported emissions binned by source country
INPUT_DATA_DIR  = os.path.join(DATA_PATH, 
                               "fire_pm_dep_paper_data",
                               "regridded_climate_data") # includes mass of GFED PM2.5 emissions (g PM2.5 per month) (instead of just mass flux). Also includes ERA5 precipitation
NAT_BOUNDS_PATH = os.path.join(DATA_PATH, "nat_boundaries/WB_countries_Admin0_10m")

# Update 17/11 -- source contributions by country (instead of UN subregion)
BIN_BY_COUNTRY = False

# Transported emissions bands (km)
thresholds = [50, 100, 200, 350, 500, 750, 1000, 1500, 2000, 3000, 5000]

# Lower bounds for each band (20km -- half a grid cell diagonal -- for the first one)
lower_bounds = np.insert(thresholds[:-1], 0, 20)


def distanceband_neighbours(coords, thresholds, lower_bounds):
    """
    Fully vectorised: Finds neighbour grid cells within specified distance bands for each point.

    Parameters:
        coords (np.ndarray): Array of shape (n_points, 2) in projected units (meters).
        thresholds (list or np.ndarray): Upper bounds of distance bands in meters.
        lower_bounds (list or np.ndarray): Lower bounds for each distance band in meters.

    Returns:
        dict: {band_upperbound_km: {point_index: [neighbour_indices]}} for each distance band.
    """
    # Create KDTree to find each coord's neighbours up to max dist
    tree = KDTree(coords)
    max_dist = thresholds[-1]

    # Get neighbour indices (ragged list) up to max threshold
    neighbours_list = tree.query_ball_point(coords, r=max_dist)

    # Flatten to get full (i, j) pairs -- each entry corresponds to an i-j pair, index by receptor i
    i_indices = np.repeat(np.arange(len(neighbours_list)), [len(nbs) for nbs in neighbours_list]) # repeat each receptor index i for the number of neighbours (sources) j it has
    j_indices = np.concatenate(neighbours_list) # stack all the lists of neighbours (j's)

    # Exclude self-pairs (KDTree finds self-pairs)
    valid = i_indices != j_indices
    i_indices = i_indices[valid]
    j_indices = j_indices[valid]

    # Compute distances vectorized
    disp_vecs = coords[j_indices] - coords[i_indices] # dx, dy
    dists = np.linalg.norm(disp_vecs, axis=1)

    # Dict to store neighbour dicts for each band
    bands_nb_dicts = {}

    # Loop through radius 'bands' and find neighbour dicts in band
    for lower, upper in tqdm(zip(lower_bounds, thresholds), total=len(thresholds)):
        in_band = (dists > lower) & (dists <= upper)
        band_i = i_indices[in_band]
        band_j = j_indices[in_band]

        # Group by i using a dict ( so will be {receptor_idx (i): [list of source_idxs (j's)]} )
        nb_dict = {i: [] for i in range(coords.shape[0])}
        for i, j in zip(band_i, band_j):
            nb_dict[i].append(j)

        bands_nb_dicts[int(upper / 1e3)] = nb_dict # keys in km

    return bands_nb_dicts  # {band_uppperbound: {receptor_idx: [source_idxs]}} 


def sum_wind_weighted_emissions_by_region(
    coords, u_wind, v_wind, gfed_emissions, bands_nb_dicts, regions, return_source_counts=False
):
    """
    Sums emissions from neighbouring grid cells for each distance band and per source region,
    weighted by cosine similarity of wind direction and displacement vectors.

    Parameters:
        coords (np.ndarray): (n_points, 2) array of grid cell centroids in projected CRS (meters).
        u_wind (np.ndarray): Eastward wind component at each source grid cell (length n_points).
        v_wind (np.ndarray): Northward wind component at each source grid cell (length n_points).
        gfed_emissions (np.ndarray): Emissions at each source grid cell (length n_points).
        bands_nb_dicts (dict): Dict where each key is a distance band upper bound (in km),
            and each value is a dict mapping point indices to lists of neighbouring indices in that band.
        regions (np.ndarray): Array of region labels (length n_regions).
        return_source_counts : (bool) If True, also return counts of contributing sources per band.
        

    Returns:
        band_emissions : np.ndarray
            Array of shape (n_points, n_bands) with summed wind alignment-weighted emissions per band.
        band_source_counts : np.ndarray (optional)
            Array of shape (n_points, n_bands) of number of sources contributing to each receptor per band
        region_emissions : np.ndarray
            Array of shape (n_points, n_bands, n_regions) of summed wind alignment-weighted emissions per band per region
    """
    
    n_receptors = coords.shape[0]
    n_bands = len(bands_nb_dicts)
    region_list = sorted(np.unique(regions[~pd.isna(regions)]))
    n_regions = len(region_list)
    
    # Empty array (n_grids, n_bands) to store the sum of weighted emissions per band
    band_emissions = np.zeros((n_receptors, n_bands))

    # Empty array (n_grids, n_bands) to store the counts of emissions sources per band
    if return_source_counts:
        band_source_counts = np.zeros((n_receptors, n_bands))
    else:
        band_source_counts = None
    
    region_emissions = np.zeros((n_receptors, n_bands, n_regions))
    
    # Mapping of region name -> source idxs
    region_idx_dict = {r: np.where(regions == r)[0] for r in region_list}

    # Loop through bands
    for band_idx, (upper, nb_dict) in enumerate(bands_nb_dicts.items()):
        # Flatten i (receptor) and j (source) indices to get full (i, j pairs)
        flat_i = np.repeat(np.arange(n_receptors), [len(nbs) for nbs in nb_dict.values()])  # repeat each receptor index i for the number of neighbours (sources) j it has
        flat_j = np.concatenate(list(nb_dict.values())).astype(int)  # stack all the lists of neighbours (j's)

        if not flat_j.any():
            continue # leave band_emissions as np.nan for receptor i with no neighbouring sources in band b
        
        # Vectorised displacement vectors (source -> receptor)
        disp_vecs = coords[flat_i] - coords[flat_j]  # shape (n_pairs, 2)

        # Wind vectors at sources
        wind_vecs = np.stack([u_wind[flat_j], v_wind[flat_j]], axis=1)  # shape (n_pairs, 2)

        # Dot products of the wind and displacement vectors (2-element vectors)
        dots = np.einsum('nm,nm->n', wind_vecs, disp_vecs)  # returns column of shape (n_pairs,)
        
        # Divide dots by norms of wind and disp vectors to get cosine similarity
        norm_wind = np.linalg.norm(wind_vecs, axis=1)
        norm_disp = np.linalg.norm(disp_vecs, axis=1)

        # Avoid division by zero
        denom = norm_wind * norm_disp
        denom[denom == 0] = 1e-8

        # Get cosine similarity
        cos_sim = dots / denom  # cosine similarity, shape (n_pairs,)

        # Weight emissions by cosine similarity (with lowerbound zero to 'switch off' negative weights [downwind emissions])
        weighted_emissions = gfed_emissions[flat_j] * np.maximum(0, cos_sim)

        # Sum weighted emissions by receptor index (i), across all sources for total band emission
        sums_total = np.bincount(flat_i, weights=weighted_emissions, minlength=n_receptors)
        band_emissions[:, band_idx] = sums_total  # store in output array

        if return_source_counts:
            counts = np.bincount(flat_i, minlength=n_receptors) # shape (n_grids,)
            band_source_counts[:, band_idx] = counts

        # --- Sum emissions per region
        for r_idx, r_name in enumerate(region_list):  # Loop over each source region by index and name
            r_sources = region_idx_dict[r_name]  # Get indices of sources belonging to this region
            in_region = np.isin(flat_j, r_sources)  # Boolean array: True where source is in the current region
            if not np.any(in_region):  # Skip if no sources in this region for this band
                continue
            sums_r = np.bincount(flat_i[in_region], weights=weighted_emissions[in_region], minlength=n_receptors)  # Sum weighted emissions per receptor for this region
            region_emissions[:, band_idx, r_idx] = sums_r  # Store summed emissions for all receptors, current band, current region

    return (band_emissions, band_source_counts, region_emissions)


def sum_wind_weighted_emissions_by_country(
    coords, u_wind, v_wind, gfed_emissions, bands_nb_dicts, countries, return_source_counts=False
):
    """
    Sums emissions from neighbouring grid cells for each distance band and per source country,
    weighted by cosine similarity of wind direction and displacement vectors.

    Parameters:
        coords (np.ndarray): (n_points, 2) array of grid cell centroids in projected CRS (meters).
        u_wind (np.ndarray): Eastward wind component at each source grid cell (length n_points).
        v_wind (np.ndarray): Northward wind component at each source grid cell (length n_points).
        gfed_emissions (np.ndarray): Emissions at each source grid cell (length n_points).
        bands_nb_dicts (dict): Dict where each key is a distance band upper bound (in km),
            and each value is a dict mapping point indices to lists of neighbouring indices in that band.
        country (np.ndarray): Array of countr labels (length n_countries).
        return_source_counts : (bool) If True, also return counts of contributing sources per band.
        

    Returns:
        band_emissions : np.ndarray
            Array of shape (n_points, n_bands) with summed wind alignment-weighted emissions per band.
        band_source_counts : np.ndarray (optional)
            Array of shape (n_points, n_bands) of number of sources contributing to each receptor per band
        region_emissions : np.ndarray
            Array of shape (n_points, n_bands, n_countries) of summed wind alignment-weighted emissions per band per country
    """
    
    n_receptors = coords.shape[0]
    n_bands = len(bands_nb_dicts)
    country_list = sorted(np.unique(countries[~pd.isna(countries)]))
    n_countries = len(country_list)
    
    # Empty array (n_grids, n_bands) to store the sum of weighted emissions per band
    band_emissions = np.zeros((n_receptors, n_bands))

    # Empty array (n_grids, n_bands) to store the counts of emissions sources per band
    if return_source_counts:
        band_source_counts = np.zeros((n_receptors, n_bands))
    else:
        band_source_counts = None
    
    country_emissions = np.zeros((n_receptors, n_bands, n_countries))
    
    # Mapping of country name -> source idxs
    country_idx_dict = {r: np.where(countries == r)[0] for r in country_list}

    # Loop through bands
    for band_idx, (upper, nb_dict) in enumerate(bands_nb_dicts.items()):
        # Flatten i (receptor) and j (source) indices to get full (i, j pairs)
        flat_i = np.repeat(np.arange(n_receptors), [len(nbs) for nbs in nb_dict.values()])  # repeat each receptor index i for the number of neighbours (sources) j it has
        flat_j = np.concatenate(list(nb_dict.values())).astype(int)  # stack all the lists of neighbours (j's)

        if not flat_j.any():
            continue # leave band_emissions as np.nan for receptor i with no neighbouring sources in band b
        
        # Vectorised displacement vectors (source -> receptor)
        disp_vecs = coords[flat_i] - coords[flat_j]  # shape (n_pairs, 2)

        # Wind vectors at sources
        wind_vecs = np.stack([u_wind[flat_j], v_wind[flat_j]], axis=1)  # shape (n_pairs, 2)

        # Dot products of the wind and displacement vectors (2-element vectors)
        dots = np.einsum('nm,nm->n', wind_vecs, disp_vecs)  # returns column of shape (n_pairs,)
        
        # Divide dots by norms of wind and disp vectors to get cosine similarity
        norm_wind = np.linalg.norm(wind_vecs, axis=1)
        norm_disp = np.linalg.norm(disp_vecs, axis=1)

        # Avoid division by zero
        denom = norm_wind * norm_disp
        denom[denom == 0] = 1e-8

        # Get cosine similarity
        cos_sim = dots / denom  # cosine similarity, shape (n_pairs,)

        # Weight emissions by cosine similarity (with lowerbound zero to 'switch off' negative weights [downwind emissions])
        weighted_emissions = gfed_emissions[flat_j] * np.maximum(0, cos_sim)

        # Sum weighted emissions by receptor index (i), across all sources for total band emission
        sums_total = np.bincount(flat_i, weights=weighted_emissions, minlength=n_receptors)
        band_emissions[:, band_idx] = sums_total  # store in output array

        if return_source_counts:
            counts = np.bincount(flat_i, minlength=n_receptors) # shape (n_grids,)
            band_source_counts[:, band_idx] = counts

        # --- Sum emissions per country
        for c_idx, c_name in enumerate(country_list):  # Loop over each source country by index and name
            c_sources = country_idx_dict[c_name]  # Get indices of sources belonging to this country
            in_country = np.isin(flat_j, c_sources)  # Boolean array: True where source is in the current country
            if not np.any(in_country):  # Skip if no sources in this country for this band
                continue
            sums_c = np.bincount(flat_i[in_country], weights=weighted_emissions[in_country], minlength=n_receptors)  # Sum weighted emissions per receptor for this country
            country_emissions[:, band_idx, c_idx] = sums_c  # Store summed emissions for all receptors, current band, current country

    return (band_emissions, band_source_counts, country_emissions)


def process_month(
    chunk, thresholds, lower_bounds, # note thresholds/LBs must be in km!
    bin_by_country=False # if False, bin by source regions not countries
):
    gdf = chunk.copy()

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(
        gdf, geometry=gpd.GeoSeries.from_wkt(gdf['geometry']),
        crs='EPSG:4326'
    )

    # Filter for Africa
    gdf = gdf[gdf['continent']=='Africa'].reset_index(drop=True)

    # Convert to projected coords (in metres)
    gdf_proj = gdf.to_crs(epsg=3857)

    # Grid cell coords (in projected CRS)
    coords = np.array([(geom.centroid.x, geom.centroid.y) for geom in gdf_proj.geometry])

    # Convert thresholds/lowerbounds to metres
    thresholds_m = np.array(thresholds) * 1e3
    lower_bounds_m = np.array(lower_bounds) * 1e3

    # Arrays of u and v 10m wind components
    u_wind = np.array(gdf_proj['u10'])
    v_wind = np.array(gdf_proj['v10'])

    # GFED emissions
    # gfed_emissions = np.array(gdf_proj['gfed_PM25'])
    gfed_emissions = np.array(gdf_proj['gfed_PM25_mass_emis'])  # NOTE 20/10: using emissions mass (g PM2.5 per month) instead of mass flux (mass per area)

    # Get neighbour dictionaries for each band
    bands_nb_dicts = distanceband_neighbours(coords, thresholds_m, lower_bounds_m)

    # Bin neighbouring emissions into upwind/downwind sources
    if bin_by_country:
        band_emissions, band_source_counts, country_emissions = sum_wind_weighted_emissions_by_country(
            coords, u_wind, v_wind, gfed_emissions, bands_nb_dicts,
            countries=np.array(gdf_proj['country']),
            return_source_counts=True
        )
    else: # source emissions by region
        band_emissions, band_source_counts, region_emissions = sum_wind_weighted_emissions_by_region(
            coords, u_wind, v_wind, gfed_emissions, bands_nb_dicts,
            regions=np.array(gdf_proj['region']),
            return_source_counts=True
        )

    # Convert binned neighbouring emissions back to tabular data
    emissions_df = pd.DataFrame(
        band_emissions[:, :],
        columns=[
            f"emis_{lower_bounds[b]}_{thresholds[b]}km"
            for b in range(len(thresholds))
        ]
    )

    # Convert binned emissions source counts back to tabular data
    source_counts_df = pd.DataFrame(
        band_source_counts[:, :],
        columns=[
            f"N_sources_{lower_bounds[b]}_{thresholds[b]}km"
            for b in range(len(thresholds))
        ]
    )

    if bin_by_country:
        # Convert country-binned emissions (receptor × band × country) back to tabular data
        country_list = sorted(gdf_proj['country'].dropna().unique())  # Get sorted list of unique country names (same order as in sum_wind_weighted_emissions_by_country())
        country_colnames = [
            f"emis_{lower_bounds[b]}_{thresholds[b]}km_{country_list[r]}"  # Column names for each band–country combination
            for b in range(len(thresholds))
            for r in range(len(country_list))  # cols are band0_country0, band0_country1, band0_country2, ..., band1_country0, band1_country1, band1_country2, ... etc. (i.e., unnest country index fastest)
        ]
        country_emissions_flat = country_emissions.reshape(coords.shape[0], -1)  # Reshape from (N, B, R) to (N, B×R) -- unnests the last index (country) fastest
        country_emissions_df = pd.DataFrame(country_emissions_flat, columns=country_colnames)  # Create DataFrame with descriptive column names

        # Horizontal append emissions cols onto gdf (original CRS)
        gdf = pd.concat(
            [gdf, emissions_df, source_counts_df, country_emissions_df],
            axis=1
        )

        return gdf  # gdf with monthly transported emissions for each band
    
    else:
        # Convert region-binned emissions (receptor × band × region) back to tabular data
        region_list = sorted(gdf_proj['region'].dropna().unique())  # Get sorted list of unique region names (same order as in sum_wind_weighted_emissions_by_region())
        region_colnames = [
            f"emis_{lower_bounds[b]}_{thresholds[b]}km_{region_list[r]}"  # Column names for each band–region combination
            for b in range(len(thresholds))
            for r in range(len(region_list))  # cols are band0_region0, band0_region1, band0_region2, ..., band1_region0, band1_region1, band1_region2, ... etc. (i.e., unnest region index fastest)
        ]
        region_emissions_flat = region_emissions.reshape(coords.shape[0], -1)  # Reshape from (N, B, R) to (N, B×R) -- unnests the last index (region) fastest
        region_emissions_df = pd.DataFrame(region_emissions_flat, columns=region_colnames)  # Create DataFrame with descriptive column names

        # Horizontal append emissions cols onto gdf (original CRS)
        gdf = pd.concat(
            [gdf, emissions_df, source_counts_df, region_emissions_df],
            axis=1
        )

        return gdf  # gdf with monthly transported emissions for each band

def main():
    # Create the output dir if it doesn't exist
    if not os.path.exists(OUT_PATH):
        os.makedirs(OUT_PATH, exist_ok=True)

    # Get the task ID from the SLURM array task ID environment variable -- CHRIS NOTE 26/08: I would have preferred to do this (parallel across years) but SLURM queue was too long to submit batch job (so just ran in interactive terminal).
    task_id = int(os.getenv("SLURM_ARRAY_TASK_ID"))

    # The years correspond to task IDs (0-19 corresponds to 2000-2019)
    year = 2000 + task_id

    ### --- Load data ---
    print("Loading data...", flush=True)
    
    # Monthly Xu, GFED, ERA5 CSV files (with gridcell WKT geometries)
    df = pd.read_csv(
        os.path.join(INPUT_DATA_DIR, f"monthly_xu_pm25_gfed_gfa_era5_{year}.csv")
    )

    # Load nat bounds and filter for Africa
    nat_bounds = gpd.read_file(NAT_BOUNDS_PATH).rename(
        columns={"CONTINENT": "continent", "WB_NAME": "country", "SUBREGION": "region"} # rename columns from shapefile
    )
    nat_bounds = nat_bounds[nat_bounds['continent']=='Africa']

    ### Join nat bounds onto df using area_join
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

    ### --- Compute surrounding wind weighted emissions by month ---
    tqdm.pandas()

    # Split df into monthly chunks
    chunks = [ df[df['month']==m] for m in range(0, 12) ]

    # Process data (compute monthly wind-weighted neighbour emissions) in parallel using Dask.delayed
    print("Computing transported emissions by month...", flush=True)
    results = [ 
        process_month(
            chunk, thresholds, lower_bounds, bin_by_country=BIN_BY_COUNTRY
        ) for chunk in tqdm(chunks, total=len(chunks))
    ]
    # delayed_results = [
    #     dask.delayed(process_month)(
    #         chunk, thresholds, lower_bounds, nat_bounds
    #     ) for chunk in chunks
    # ]

    # # Compute results
    # with ProgressBar():
    #     results = dask.compute(*delayed_results, scheduler="processes")
    
    # Concat monthly chunks to annual GeoDataFrame
    year_gdf = pd.concat(results).reset_index(drop=True)

    ### --- Convert to DataFrame and write CSV ---
    year_gdf = pd.DataFrame(year_gdf)
    year_gdf['geometry'] = year_gdf['geometry'].apply(lambda geom: geom.wkt)

    print("Writing to CSV...", flush=True)
    year_gdf.to_csv(os.path.join(OUT_PATH, f"monthly_transported_GFED_emissions_{year}.csv"))
    
    print(f"Processing for year: {year} complete! Written to file: monthly_transported_GFED_emissions_{year}.csv")


if __name__ == "__main__":
    print("Starting...", flush=True)
    main()
    print("Done!", flush=True)