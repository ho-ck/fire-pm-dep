"""
Download external datasets used in the manuscript

    "Deprivation and fire-related air pollution exposure in Africa"

Run this script after ephemeral storage has been cleared or when 
setting up the project on a new system.

Created: 2024-11-28
Last updated: 2026-07-06
"""

import argparse
import os
import subprocess
import zipfile
from pathlib import Path

from tqdm import tqdm

###############################################################################
# Configuration
###############################################################################

PROJECT_ROOT = Path.home() / "fire-pm-dep"
DATA_PATH = Path(os.environ["SCRATCH_DIR"]) / "data" / "spatial"

YEARS = range(2000, 2020)
IHME_YEARS = range(2000, 2018)

GRDI_CREDENTIALS = Path.home() / "grdi_credentials.txt"
GRDI_SCRIPT = PROJECT_ROOT / "src" / "setup_scripts" / "grdi_download.sh"

###############################################################################
# Dataset definitions
###############################################################################

xu_annual = dict(
    zip(
        [
            DATA_PATH / "pm25_xu" / f"annual_avg{year}.rds"
            for year in YEARS
        ],
        [
            "https://osf.io/download/ryjc8/", "https://osf.io/download/vzx5e/",
            "https://osf.io/download/8jg54/", "https://osf.io/download/zwg8p/",
            "https://osf.io/download/e839r/", "https://osf.io/download/jd9k8/",
            "https://osf.io/download/7frzs/", "https://osf.io/download/3nvk9/",
            "https://osf.io/download/yhwfz/", "https://osf.io/download/ap9cm/",
            "https://osf.io/download/dcn6h/", "https://osf.io/download/mwbhc/",
            "https://osf.io/download/sh7gz/", "https://osf.io/download/a35c6/",
            "https://osf.io/download/s6gyr/", "https://osf.io/download/cau5q/",
            "https://osf.io/download/rhx5d/", "https://osf.io/download/c5txv/",
            "https://osf.io/download/dzehg/", "https://osf.io/download/p3htr/",
        ],
    )
)

xu_monthly = dict(
    zip(
        [DATA_PATH / "monthly_pm25_xu" / "pm25_xu_monthly.zip"],
        ["https://files.au-1.osf.io/v1/resources/thgvf/providers/osfstorage/6512e2af333aef00f8d70510/?zip="],
    )
)

adm0 = dict(
    zip(
        [DATA_PATH / "nat_boundaries" / "WB_countries_Admin0_10m.zip"],
        ["https://datacatalogfiles.worldbank.org/ddh-published/0038272/DR0046659/wb_countries_admin0_10m.zip"],
    )
)

western_sahara = dict( # shapefile not in the WB adm0 boundaries above^^
    zip(
        [DATA_PATH / "nat_boundaries" / "western_sahara" / "western_sahara_gadm.zip"],
        ["https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_ESH_shp.zip"],
    )
)

worldpop = dict(
    zip(
        [
            DATA_PATH / "glob_pop_counts" / f"ppp_{year}_1km_Aggregated.tif"
            for year in YEARS
        ],
        [
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020/{year}/0_Mosaicked/ppp_{year}_1km_Aggregated.tif"
            for year in YEARS
        ],
    )
)


worldpop_age_sex = dict(
    zip(
        [
            DATA_PATH / "age_sex_struct" / f"global_{sex}_{age}_{year}_1km.tif"
            for year in YEARS
            for sex in ['m', 'f']
            for age in [0, 1] + list(range(5, 81, 5))
        ],
        [
            f"https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020/{year}/0_Mosaicked/global_mosaic_1km/global_{sex}_{age}_{year}_1km.tif"
            for year in YEARS
            for sex in ['m', 'f']
            for age in [0, 1] + list(range(5, 81, 5))
        ],
    )
)


kummu = dict(
    zip(
        [DATA_PATH / "kummu_ses" / "rast_gdpTot_1990_2022_5arcmin.tif"],
        ["https://zenodo.org/records/13943886/files/rast_gdpTot_1990_2022_5arcmin.tif?download=1"]
    )
)

education = dict(
    zip(
        [
            DATA_PATH / "education" / f"ihme_lmic_edu_2000_2017_mean_15_49_{sex}_mean.tif"
            for sex in ["male", "female"] 
        ],
        [
            f"https://cloud.ihme.washington.edu/s/CTnfWYaZxc7ZENc/download?path=%2FData%20%5BGeoTIFF%5D&files=IHME_LMIC_EDU_2000_2017_MEAN_15_49_{sex}_MEAN_Y2019M12D24.TIF"
            for sex in ['MALE', 'FEMALE']
        ]
    )
)

stunting = dict(
    zip(
        [
            DATA_PATH / "stunting" / f"ihme_lmic_cgf_2000_2017_stunting_prev_mean_{year}.tif"
            for year in IHME_YEARS
        ],
        [
            f"https://cloud.ihme.washington.edu/s/Q5CGeazb4iNsDQA/download?path=%2FStunting%20Prevalence%20%5BGeoTIFF%5D&files=IHME_LMIC_CGF_2000_2017_STUNTING_PREV_MEAN_{year}_Y2020M01D08.TIF"
            for year in IHME_YEARS
        ]

    )
)

wash = dict(
    zip(
        [
            DATA_PATH / "wash" / f"ihme_lmic_wash_2000_2017_s_imp_percent_mean_{year}.tif"
            for year in IHME_YEARS
        ],
        [
            f"https://cloud.ihme.washington.edu/s/bkH2X2tFQMejMxy/download?path=%2FS_IMP%20-%20Access%20to%20any%20improved%20sanitation%20facility%20%5BGeoTIFF%5D%2FPercent&files=IHME_LMIC_WASH_2000_2017_S_IMP_PERCENT_MEAN_{year}_Y2020M06D02.TIF"
            for year in IHME_YEARS
        ]
    )
)

# Note 06/07/2026: GRDI not working for now, maybe try this repo instead
# https://www.datalumos.org/datalumos/project/240845/version/V2/view;jsessionid=4BB63C35EBC83640441FBF8BB67FED0D?path=/datalumos/240845/fcr:versions/V2/povmap-grdi-v1-geotiff.zip&type=file
grdi = dict(
    zip(
        [ DATA_PATH / "grdi" / "povmap-grdi-v1-geotiff.zip"],
        ["https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-geotiff.zip?_ga=2.201868497.1189683742.1734345564-1819600478.1723039009"]
    )
)

ghs = dict(
    zip(
        [
            DATA_PATH / "GHSL" / f"GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
            for year in list(range(2000, 2021, 5))
        ],
        [
            f"https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
            for year in list(range(2000, 2021, 5))
        ]
    )
)

gfed = dict(
    zip(
        [
            DATA_PATH / "GFED" / f"GFED4.1s_{year}.hdf5"
            for year in YEARS
        ],
        [
            f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}.hdf5"
            for year in range(2000, 2017)
        ]
        + [
            f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}_beta.hdf5"
            for year in range(2017, 2020)
        ]
    )
)

era5_meteo = dict( # wind, temperature, dewpoint temp, pressure
    zip(
        [ DATA_PATH / "ERA5" / "ERA5_monthly_averaged_reanalysis.grib" ],
        ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-3/2026-07-06/74ddb1ea6a6070093a137cb0c7c83e69.grib"]
    )
)

era5_precipitation = dict( # precipitation
    zip(
        [ DATA_PATH / "ERA5" / "ERA5_monthly_averaged_reanalysis_precip.grib" ],
        ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-3/2026-07-06/e5e704ac573ea2e35ecb667b40b8e9e1.grib"]
    )
)

kummu_admin2 = dict(
    zip(
        [
            DATA_PATH / "admin2" / "GDP" / "polyg_adm2_gdp_perCapita_1990_2022.gpkg",
            DATA_PATH / "admin2" / "GDP" / "rast_adm2_gdp_perCapita_1990_2022.tif"
        ],
        [
            "https://zenodo.org/records/13943886/files/polyg_adm2_gdp_perCapita_1990_2022.gpkg?download=1",
            "https://zenodo.org/records/13943886/files/rast_adm2_gdp_perCapita_1990_2022.tif?download=1"
        ]
    )
)

###############################################################################
# Registry of all datasets
###############################################################################

DATASETS = {
    "xu_annual": xu_annual,
    "xu_monthly": xu_monthly,
    "adm0": adm0,
    "western_sahara": western_sahara,
    "worldpop": worldpop,
    "worldpop_age_sex": worldpop_age_sex,
    "kummu": kummu,
    "education": education,
    "stunting": stunting,
    "wash": wash,
    "grdi": grdi,
    "ghs": ghs,
    "gfed": gfed,
    "era5_meteo": era5_meteo,
    "era5_precipitation": era5_precipitation,
    "kummu_admin2": kummu_admin2,
}

###############################################################################
# Download functions
###############################################################################

def download_file(path: Path, url: str) -> None:
    """
    Download a single file if it does not already exist.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        print(f"Skipping {path.name}")
        return

    subprocess.run(
        [
            "curl",
            "-L",
            "-o",
            str(path),
            url,
        ],
        check=True,
    )

    if path.suffix == ".zip":
        print(f"Extracting {path.name}")

        with zipfile.ZipFile(path) as z:
            z.extractall(path.parent)


def download_grdi(path: Path) -> None:
    """
    GRDI requires authenticated download.
    """

    if path.exists():
        print(f"Skipping {path.name}")
        return

    with open(GRDI_CREDENTIALS) as f:

        username = f.readline().split("=")[1].strip()
        password = f.readline().split("=")[1].strip()

    subprocess.run(
        [
            str(GRDI_SCRIPT),
            username,
            password,
            str(path.parent),
        ],
        check=True,
    )

    with zipfile.ZipFile(path) as z:
        z.extractall(path.parent)


def download_dataset(name: str, downloads: dict[Path, str]) -> None:

    for path, url in tqdm(downloads.items()):

        if name == "grdi":
            download_grdi(path)
        else:
            download_file(path, url)


###############################################################################
# Main
###############################################################################

def main():

    parser = argparse.ArgumentParser(
        description="Download external datasets."
    )

    parser.add_argument(
        "--dataset",
        default="all",
        choices=["all"] + list(DATASETS.keys()),
        help="Dataset to download."
    )

    args = parser.parse_args()

    if args.dataset == "all":
        datasets = DATASETS.items()

    else:
        datasets = [(args.dataset, DATASETS[args.dataset])]

    for name, dataset in datasets:
        print("\n" + "=" * 80)
        print(name)
        print("=" * 80)

        download_dataset(name, dataset)

    print("\nDone!")


if __name__ == "__main__":
    main()



# import cdsapi

# dataset = "reanalysis-era5-single-levels-monthly-means"
# request = {
#     "product_type": ["monthly_averaged_reanalysis"],
#     "variable": [
#         "10m_u_component_of_wind",
#         "10m_v_component_of_wind",
#         "2m_dewpoint_temperature",
#         "2m_temperature",
#         "surface_pressure"
#     ],
#     "year": [
#         "2000", "2001", "2002",
#         "2003", "2004", "2005",
#         "2006", "2007", "2008",
#         "2009", "2010", "2011",
#         "2012", "2013", "2014",
#         "2015", "2016", "2017",
#         "2018", "2019", "2020",
#         "2021", "2022", "2023"
#     ],
#     "month": [
#         "01", "02", "03",
#         "04", "05", "06",
#         "07", "08", "09",
#         "10", "11", "12"
#     ],
#     "time": ["00:00"],
#     "data_format": "grib",
#     "download_format": "unarchived"
# }

# client = cdsapi.Client()
# client.retrieve(dataset, request).download()


# dataset = "reanalysis-era5-single-levels-monthly-means"
# request = {
#     "product_type": ["monthly_averaged_reanalysis"],
#     "variable": ["total_precipitation"],
#     "year": [
#         "2000", "2001", "2002",
#         "2003", "2004", "2005",
#         "2006", "2007", "2008",
#         "2009", "2010", "2011",
#         "2012", "2013", "2014",
#         "2015", "2016", "2017",
#         "2018", "2019", "2020",
#         "2021", "2022", "2023"
#     ],
#     "month": [
#         "01", "02", "03",
#         "04", "05", "06",
#         "07", "08", "09",
#         "10", "11", "12"
#     ],
#     "time": ["00:00"],
#     "data_format": "grib",
#     "download_format": "unarchived"
# }

# client = cdsapi.Client()
# client.retrieve(dataset, request).download()





# import os
# import subprocess
# from tqdm import tqdm
# import datetime

# DATA_PATH = f'{os.getenv("SCRATCH_DIR")}/data/spatial'
# # /work/scratch-pw5/cho00/data/spatial/fire_pm_dep_paper_data/rawdata

# ### Xu PM2.5 annual data
# xu_annual_urls = [ # 2000-2019 download links
#     "https://osf.io/download/ryjc8/", "https://osf.io/download/vzx5e/",
#     "https://osf.io/download/8jg54/", "https://osf.io/download/zwg8p/",
#     "https://osf.io/download/e839r/", "https://osf.io/download/jd9k8/",
#     "https://osf.io/download/7frzs/", "https://osf.io/download/3nvk9/",
#     "https://osf.io/download/yhwfz/", "https://osf.io/download/ap9cm/",
#     "https://osf.io/download/dcn6h/", "https://osf.io/download/mwbhc/",
#     "https://osf.io/download/sh7gz/", "https://osf.io/download/a35c6/",
#     "https://osf.io/download/s6gyr/", "https://osf.io/download/cau5q/",
#     "https://osf.io/download/rhx5d/", "https://osf.io/download/c5txv/",
#     "https://osf.io/download/dzehg/", "https://osf.io/download/p3htr/",
# ]
# xu_annual_paths = [f"{DATA_PATH}/pm25_xu/annual_avg20{i:02d}.rds" for i in range(20)]
# xu_annual_download_dict = dict(zip(xu_annual_paths, xu_annual_urls))

# ### Xu PM2.5 monthly data
# xu_monthly_urls = ["https://files.au-1.osf.io/v1/resources/thgvf/providers/osfstorage/6512e2af333aef00f8d70510/?zip="]
# xu_monthly_paths = [f"{DATA_PATH}/monthly_pm25_xu/pm25_xu_monthly.zip"]
# xu_monthly_download_dict = dict(zip(xu_monthly_paths, xu_monthly_urls))

# # ### Xu PM2.5 daily data
# # xu_daily_urls = ["https://figshare.com/ndownloader/articles/24196926?private_link=41301293c7e10a6c39ec"]
# # xu_daily_paths = [f"{DATA_PATH}/daily_pm25_xu/pm25_daily.zip"]
# # xu_daily_download_dict = dict(zip(xu_daily_paths, xu_daily_urls))

# ### National boundaries (admin 0)
# adm_0_urls = ["https://datacatalogfiles.worldbank.org/ddh-published/0038272/DR0046659/wb_countries_admin0_10m.zip"]
# adm_0_paths = [f"{DATA_PATH}/nat_boundaries/WB_countries_Admin0_10m.zip"]
# adm_0_download_dict = dict(zip(adm_0_paths, adm_0_urls))

# ### Western Sahara shapefile (not in World Bank file)
# western_sahara_urls = ["https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_ESH_shp.zip"]
# western_sahara_paths = [f"{DATA_PATH}/nat_boundaries/western_sahara/western_sahara_gadm.zip"]
# western_sahara_download_dict = dict(zip(western_sahara_paths, western_sahara_urls))

# ### WorldPop population counts
# wpop_urls = [ # 2000-2019 download links
#     f"https://data.worldpop.org/GIS/Population/Global_2000_2020/20{i:02d}/0_Mosaicked/ppp_20{i:02d}_1km_Aggregated.tif"
#     for i in range(20)
# ]
# wpop_paths = [f"{DATA_PATH}/glob_pop_counts/ppp_20{i:02d}_1km_Aggregated.tif" for i in range(20)]
# wpop_download_dict = dict(zip(wpop_paths, wpop_urls))

# ### WorldPop age and sex structures
# wpop_as_urls = [ f"https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020/{year}/0_Mosaicked/global_mosaic_1km/global_{sex}_{age}_{year}_1km.tif"
#     for year in range(2000, 2020)
#     for sex in ['m', 'f']
#     for age in [0, 1] + list(range(5, 81, 5))
# ]
# wpop_as_paths = [
#     f"{DATA_PATH}/age_sex_struct/global_{sex}_{age}_{year}_1km.tif"
#     for year in range(2000, 2020)
#     for sex in ['m', 'f']
#     for age in [0, 1] + list(range(5, 81, 5))
# ]
# wpop_as_download_dict = dict(zip(wpop_as_paths, wpop_as_urls))

# ### Kummu SES
# kummu_urls = ["https://zenodo.org/records/13943886/files/rast_gdpTot_1990_2022_5arcmin.tif?download=1"]
# kummu_paths = [f"{DATA_PATH}/kummu_ses/rast_gdpTot_1990_2022_5arcmin.tif"]
# kummu_download_dict = dict(zip(kummu_paths, kummu_urls))

# ### IHME mean years of schooling, male & female
# edu_urls = [
#     f"https://cloud.ihme.washington.edu/s/CTnfWYaZxc7ZENc/download?path=%2FData%20%5BGeoTIFF%5D&files=IHME_LMIC_EDU_2000_2017_MEAN_15_49_{sex}_MEAN_Y2019M12D24.TIF"
#     for sex in ['MALE', 'FEMALE']
# ]
# edu_paths = [
#     f"{DATA_PATH}/education/ihme_lmic_edu_2000_2017_mean_15_49_{sex}_mean.tif"
#     for sex in ["male", "female"] 
# ]
# edu_download_dict = dict(zip(edu_paths, edu_urls))

# ### IHME stunting prevalence -- low height for age
# stunt_urls = [
#     f"https://cloud.ihme.washington.edu/s/Q5CGeazb4iNsDQA/download?path=%2FStunting%20Prevalence%20%5BGeoTIFF%5D&files=IHME_LMIC_CGF_2000_2017_STUNTING_PREV_MEAN_{year}_Y2020M01D08.TIF"
#     for year in range(2000, 2018)
# ]
# stunt_paths = [
#     f"{DATA_PATH}/stunting/ihme_lmic_cgf_2000_2017_stunting_prev_mean_{year}.tif"
#     for year in range(2000, 2018)
# ]
# stunt_download_dict = dict(zip(stunt_paths, stunt_urls))

# ### IHME WaSH -- pct access to any improved sanitation facility
# wash_urls = [
#     f"https://cloud.ihme.washington.edu/s/bkH2X2tFQMejMxy/download?path=%2FS_IMP%20-%20Access%20to%20any%20improved%20sanitation%20facility%20%5BGeoTIFF%5D%2FPercent&files=IHME_LMIC_WASH_2000_2017_S_IMP_PERCENT_MEAN_{year}_Y2020M06D02.TIF"
#     for year in range(2000, 2018)
# ]
# wash_paths = [
#     f"{DATA_PATH}/wash/ihme_lmic_wash_2000_2017_s_imp_percent_mean_{year}.tif"
#     for year in range(2000, 2018)
# ]
# wash_download_dict = dict(zip(wash_paths, wash_urls))
    
# ### Gridded RDI
# grdi_urls = ["https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-geotiff.zip?_ga=2.201868497.1189683742.1734345564-1819600478.1723039009"]
# grdi_paths = [f"{DATA_PATH}/grdi/povmap-grdi-v1-geotiff.zip"]
# grdi_download_dict = dict(zip(grdi_paths, grdi_urls))
# grdi_credentials_file = "/home/users/cho00/grdi_credentials.txt" # for downloading file

# ### GHS-SMOD urban classification
# ghs_urls = [
#     f"https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
#     for year in list(range(2000, 2021, 5))
# ]
# ghs_paths = [
#     f"{DATA_PATH}/GHSL/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
#     for year in list(range(2000, 2021, 5))
# ]
# ghs_download_dict = dict(zip(ghs_paths, ghs_urls))

# ### GFED4.1s
# gfed_urls = [f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}.hdf5" for year in range(2000, 2017)] + \
#             [f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}_beta.hdf5" for year in range(2017, 2020)]
# gfed_paths = [f"{DATA_PATH}/GFED/GFED4.1s_{year}.hdf5" for year in range(2000, 2020)]
# gfed_download_dict = dict(zip(gfed_paths, gfed_urls))

# ### ERA5 Monthly -- wind, temperature, dewpoint temp, pressure
# era5_temp_urls = ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-2/2025-10-03/1a81059f0ef0aa49cbf6f303da13ebfb.grib"]
# era5_temp_paths = [os.path.join(DATA_PATH, "ERA5/ERA5_monthly_averaged_reanalysis.grib")]
# era5_temp_download_dict = dict(zip(era5_temp_paths, era5_temp_urls))

# ### ERA monthly precipitation (total precipitation, tp)
# era5_tp_urls = ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-1/2025-10-20/4f563e68b4ceddb2a4bd3c843de89622.grib"]
# era5_tp_paths = [os.path.join(DATA_PATH, "ERA5/ERA5_monthly_averaged_reanalysis_precip.grib")]
# era5_tp_download_dict = dict(zip(era5_tp_paths, era5_tp_urls))

# ###### Admin 2 Data:

# ### Kummu GDP Admin 2
# kummu_adm2_urls = [
#     "https://zenodo.org/records/13943886/files/polyg_adm2_gdp_perCapita_1990_2022.gpkg?download=1",
#     "https://zenodo.org/records/13943886/files/rast_adm2_gdp_perCapita_1990_2022.tif?download=1"
# ]
# kummu_adm2_paths = [
#     f"{DATA_PATH}/admin2/GDP/polyg_adm2_gdp_perCapita_1990_2022.gpkg",
#     f"{DATA_PATH}/admin2/GDP/rast_adm2_gdp_perCapita_1990_2022.tif"
# ]
# kummu_adm2_download_dict = dict(zip(kummu_adm2_paths, kummu_adm2_urls))


# ### Chris note 15/01/2025: updated wget_files() function
# def wget_files(download_dict, cookies=None):
#     """
#     Downloads files based on a dictionary of paths and URLs.

#     Args:
#         download_dict (dict): A dictionary where keys are file paths and values are download URLs.
#         cookies (str, optional): Cookies to use for authenticated downloads. Default is None.
#     """
#     for path, url in tqdm(download_dict.items(), desc='Downloading files...'):
#         dirname = os.path.dirname(path)
#         if not os.path.isdir(dirname):
#             os.makedirs(dirname)

#         if "grdi" in path:  # Special handling for GRDI dataset
#             if not os.path.exists(path):
#                 # Get username and password for download
#                 with open(grdi_credentials_file, 'r') as f:
#                     lines = f.readlines()
#                     username = lines[0].strip().split('=')[1]
#                     password = lines[1].strip().split('=')[1]
#                 # Run download script
#                 subprocess.run(
#                     ["/home/users/cho00/fire-pm-dep/setup_scripts/grdi_download.sh",
#                      username, password, os.path.dirname(path)],
#                     capture_output=True, text=True)
#                 # Unzip
#                 subprocess.run(["unzip", path, "-d", os.path.dirname(path)], capture_output=True, text=True)
#                 print(f"-- {str(datetime.date.today())} -- Downloaded and extracted GRDI file: '{path}'")
#             else:
#                 print(f"-- {str(datetime.date.today())} -- File already exists: '{path}'")
#             continue

#         # Base curl command
#         base_command = f"curl -L -o \"{path}\" \"{url}\""

#         # Add cookies if provided
#         if cookies:
#             base_command += f" -H \"cookie: {cookies}\""

#         # Handle file types
#         if path.endswith(".zip"):
#             command = f"""
#             if [ ! -f "{path}" ]; then
#                 {base_command} ;
#                 UNZIP_DISABLE_ZIPBOMB_DETECTION=TRUE unzip {path} -d "{os.path.dirname(path)}" ;
#             else
#                 echo "-- $(date) -- File already exists: '{path}'";
#             fi
#             """
#         else:
#             command = f"""
#             if [ ! -f "{path}" ]; then
#                 {base_command};
#             else
#                 echo "-- $(date) -- File already exists: '{path}'";
#             fi
#             """

#         try:
#             subprocess.run(command, shell=True, check=True)
#         except subprocess.CalledProcessError as e:
#             print(f"Error occurred while downloading or processing file: {path}\n{e}")


        
    
# if __name__ == "__main__":
#     # download files
#     wget_files(xu_annual_download_dict)
#     # wget_files(xu_daily_download_dict)
#     wget_files(xu_monthly_download_dict)
#     wget_files(adm_0_download_dict)
#     wget_files(western_sahara_download_dict)
#     wget_files(wpop_download_dict)
#     wget_files(wpop_as_download_dict)
#     wget_files(kummu_download_dict)
#     wget_files(edu_download_dict)
#     wget_files(stunt_download_dict)
#     wget_files(wash_download_dict)
#     wget_files(grdi_download_dict)
#     wget_files(ghs_download_dict)
#     wget_files(gfed_download_dict)
#     wget_files(era5_temp_download_dict)
#     wget_files(era5_tp_download_dict)
#     wget_files(kummu_adm2_download_dict)
    
#     print("Done!")