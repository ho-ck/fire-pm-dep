"""
Prepare annnual data for deprivation-PM2.5 analysis -- filter for Africa, create
derived variables: child dependency pct, log GDP pc, percentages from
prevalences etc

Date created: 04/04/2025
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_PATH   = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
INPUT_PATH  = os.path.join(DATA_PATH,
                        #    "annual_global_pm_se_data",  # dir for annual gdfs
                           "annual_global_pm_se_data_2000_2023",  # 2000-2023 Hu et al. data
                           )
OUT_PATH    = os.path.join(DATA_PATH, 
                           "fire_pm_dep_paper_data",    # dir for data for paper
                           "proc_data",                 # processed data
                        #    "df_af_annual.csv")
                           "df_af_annual_2000_2023.csv") # 2000-2023 Hu et al. data

YEARS = range(2000, 2024)

# Function to classify urbanicity
def classify_urbanicity(df, urban_pct_col="urban_pop_pct", intermediate=True):
    assert urban_pct_col in list(df.columns)
    bins = [-np.inf, 50, 80, np.inf] if intermediate else [-np.inf, 50, np.inf]
    labels = ['rural', 'intermediate', 'urban'] if intermediate else ['rural', 'urban']
    urban_cat = pd.cut(
        df[urban_pct_col], bins=bins, labels=labels, right=True
    ).astype(object).where(df[urban_pct_col].notna())
    return urban_cat

if __name__ == "__main__":

    if not os.path.exists(os.path.dirname(OUT_PATH)):
        os.makedirs(os.path.dirname(OUT_PATH))

    # Read in all annual gdfs and concat
    annual_gdfs = [
        pd.read_csv( os.path.join(INPUT_PATH, f"gdf_pm_soc_{i}.csv") )
        for i in YEARS
    ]
    df = pd.concat(annual_gdfs)

    # # Read yearly dataset
    # df = pd.read_csv( 
    #     os.path.join(DATA_PATH, 'full_geojsons_GDP_pc/gdf_all_years_00_19.csv') 
    # )

    # # Load daily data
    # pm25_daily = pd.read_csv(
    #     os.path.join(DATA_PATH, 'daily_pm25_xu/lfs_pm25_exposure_days.csv') 
    # )

    # # Drop grid_id from daily data and join onto df
    # df = df.merge(
    #     pm25_daily.drop('grid_id', axis=1), 
    #     on=['year', 'lon', 'lat'],
    #     how='left'
    # )

    # Create child dependency percentage col -- population of ages 0-14 / ages 15-64
    working_age_cols = [f'pop_count_f_{i}' for i in range(15, 64, 5)] + \
                        [f'pop_count_m_{i}' for i in range(15, 64, 5)]
    # ^^WorldPop age columns are 'pop_count_{m|f}_{age}' -- age 15 is 15-19, 60 is 60-64 etc.
    child_age_cols = ['pop_count_f_0', 'pop_count_m_0', 'pop_count_f_1', 'pop_count_m_1',
                        'pop_count_f_5', 'pop_count_m_5', 'pop_count_f_10', 'pop_count_m_10']
    df['child_dep_pct'] = 100 * df[child_age_cols].sum(axis=1) / df[working_age_cols].sum(axis=1).replace(0, np.nan)

    # Create edu mean years col
    df['edu_mean_years'] = (df['edu_f_mean_years'] + df['edu_m_mean_years']) / 2
    
    # Create log GDP col
    df['log_GDP_tot'] = np.log(df['GDP_tot'])

    # Create log GDP per capita col
    df['log_GDP_pc'] = np.log(df['GDP_pc'])
    
    # Create percentage cols from prevalences
    # df['mort_rate_u5_pct'] = df['mort_rate_u5'] * 100
    df['stunting_pct_u5'] = df['stunting_prev_u5'] * 100
    
    # # Add a unique grid cell ID
    # df['grid_id'] = df.groupby(['lon', 'lat']).ngroup()

    # Create urban pop pct col
    df['urban_pop_pct'] = 100 * df['pop_count_urban'] / df['pop_count']
    
    # Create cols with & without intermediate
    df['eurostat_urban'] = classify_urbanicity(df, intermediate=True)
    df['urban_rural'] = classify_urbanicity(df, intermediate=False)

    # Create categorical dtype cols
    df['eurostat_urban_cat'] = pd.Categorical(
        df['eurostat_urban'], categories=['rural', 'intermediate', 'urban'], ordered=True)
    df['urban_rural_cat'] = pd.Categorical(df['urban_rural'], categories=['rural', 'urban'])

    # Filter for Africa only
    df = df[df['continent']=="Africa"]
    
    # # Create decade col
    # df['decade'] = np.where(df['year']>=2010, 1, 0)

    # Write to CSV
    df.to_csv(OUT_PATH, index=False)
