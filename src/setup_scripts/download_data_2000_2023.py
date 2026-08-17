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
import shutil
import zipfile
from pathlib import Path

from tqdm import tqdm

###############################################################################
# Configuration
###############################################################################

PROJECT_ROOT    = Path.home() / "fire-pm-dep"
DATA_PATH       = Path(os.environ["SCRATCH_DIR"]) / "data" / "spatial"

YEARS       = range(2000, 2024)     # Hu et al. data range (2000-2023)
XU_YEARS    = range(2000, 2020)
IHME_YEARS  = range(2000, 2018)
GHS_YEARS   = range(2000, 2021, 5)  # 2000, 2005, 2010, 2015, 2020

GRDI_CREDS  = Path.home() / "grdi_credentials.txt"
GRDI_SCRIPT = PROJECT_ROOT / "src" / "setup_scripts" / "grdi_download.sh"

###############################################################################
# Dataset definitions
###############################################################################

# -----------------------------------------------------------------------------
# Hu et al. fire PM2.5 (2000-2023)
# -----------------------------------------------------------------------------
hu_annual = dict(
    zip(
        [
            DATA_PATH / "pm25_hu" / f"{year}gfedfirepm25.nc"
            for year in YEARS
        ],
        [
            f"https://zenodo.org/records/15493914/files/{year}gfedfirepm25.nc.tar.gz?download=1"
            for year in YEARS
        ],
    )
)

# -----------------------------------------------------------------------------
# Xu et al. fire PM2.5 (2000-2019)
# -----------------------------------------------------------------------------
xu_annual = dict(
    zip(
        [
            DATA_PATH / "pm25_xu" / f"annual_avg{year}.rds"
            for year in XU_YEARS
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

# -----------------------------------------------------------------------------
# National boundaries
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# WorldPop
#   2000–2020 : Global_2000_2020 mosaic paths 'Global1'
#   2021–2023 : Global_2015_2030 extended mosaic paths 'Global2'
# -----------------------------------------------------------------------------
# Helper func to get url
def _worldpop_url(year: int) -> str:
    if year <= 2020:
        return (
            f"https://data.worldpop.org/GIS/Population/"
            f"Global_2000_2020/{year}/0_Mosaicked/"
            f"ppp_{year}_1km_Aggregated.tif"
        )
    else:
        # Updated 'Global2'
        return (
            f"https://data.worldpop.org/GIS/Population/"
            f"Global_2015_2030/R2025A/{year}/0_Mosaicked/v1/1km_ua/constrained/"
            f"global_pop_{year}_CN_1km_R2025A_UA_v1.tif"
        )

worldpop = dict(
    zip(
        [
            DATA_PATH / "glob_pop_counts" / f"ppp_{year}_1km_Aggregated.tif"
            for year in YEARS
        ],
        [_worldpop_url(year) for year in YEARS],
    )
)

# -----------------------------------------------------------------------------
# WorldPop age-sex structured (see above)
# -----------------------------------------------------------------------------
_AGE_GROUPS_OLD = [0, 1] + list(range(5, 81, 5))
_AGE_GROUPS_NEW = [0, 1] + list(range(5, 91, 5))  # goes up to 85 and 90 for newer data
_SEXES = ["m", "f"]

# Helper to get url
def _worldpop_age_sex_url(year: int, sex: str, age: int) -> str:
    if year <= 2020:
        return (
            f"https://data.worldpop.org/GIS/AgeSex_structures/"
            f"Global_2000_2020/{year}/0_Mosaicked/global_mosaic_1km/"
            f"global_{sex}_{age}_{year}_1km.tif"
        )
    else:
        return (
            f"https://data.worldpop.org/GIS/AgeSex_structures/"
            f"Global_2015_2030/R2025A/{year}/0_Mosaicked/v1/1km_ua/constrained/"
            f"global_{sex}_{age:02d}_{year}_CN_1km_R2025A_UA_v1.tif"    # note the padding on age, for '00', '01', '05' etc.
        )

# Helper to choose correct age groups to download
def _age_groups(year: int) -> list[int]:
    return _AGE_GROUPS_OLD if year <= 2020 else _AGE_GROUPS_NEW

worldpop_age_sex = dict(
    zip(
        [
            DATA_PATH / "age_sex_struct" / f"global_{sex}_{age}_{year}_1km.tif"
            for year in YEARS
            for sex in _SEXES
            for age in _age_groups(year)
        ],
        [
            _worldpop_age_sex_url(year, sex, age)
            for year in YEARS
            for sex in _SEXES
            for age in _age_groups(year)
        ],
    )
)

# -----------------------------------------------------------------------------
# Kummu GDP  (1990-2022)
# -----------------------------------------------------------------------------
# GDP tot.
kummu = dict(
    zip(
        [DATA_PATH / "kummu_ses" / "rast_gdpTot_1990_2022_5arcmin.tif"],
        ["https://zenodo.org/records/13943886/files/rast_gdpTot_1990_2022_5arcmin.tif?download=1"]
    )
)

# GDP per capita (admin2)
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

# -----------------------------------------------------------------------------
# IHME education, stunting, WASH  (2000-2017)
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# GRDI
# Note 06/07/2026: GRDI not working for now, maybe try this repo instead
# https://www.datalumos.org/datalumos/project/240845/version/V2/view;jsessionid=4BB63C35EBC83640441FBF8BB67FED0D?path=/datalumos/240845/fcr:versions/V2/povmap-grdi-v1-geotiff.zip&type=file
# -----------------------------------------------------------------------------
grdi = dict(
    zip(
        [ DATA_PATH / "grdi" / "povmap-grdi-v1-geotiff.zip"],
        ["https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-geotiff.zip?_ga=2.201868497.1189683742.1734345564-1819600478.1723039009"]
    )
)

# ---------------------------------------------------------------------------
# GHSL urbanicity  (2000, 2005, 2010, 2015, 2020)
# ---------------------------------------------------------------------------
ghs = dict(
    zip(
        [
            DATA_PATH / "GHSL" / f"GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
            for year in GHS_YEARS
        ],
        [
            f"https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E{year}_GLOBE_R2023A_54009_1000_V2_0.zip"
            for year in GHS_YEARS
        ]
    )
)

# -----------------------------------------------------------------------------
# GFED 4.1s  (2000-2016; 2017-2023 beta)
# -----------------------------------------------------------------------------
# Helper to get url
def _gfed_url(year: int) -> str:
    if year < 2017:
        return f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}.hdf5"
    else:
        return f"https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_{year}_beta.hdf5"

gfed = dict(
    zip(
        [
            DATA_PATH / "GFED" / f"GFED4.1s_{year}.hdf5"
            for year in YEARS
        ],
        [_gfed_url(year) for year in YEARS],
    )
)

# -----------------------------------------------------------------------------
# ERA5
# -----------------------------------------------------------------------------
era5_meteo = dict( # wind, temperature, dewpoint temp, pressure
    zip(
        [ DATA_PATH / "ERA5" / "ERA5_monthly_averaged_reanalysis.grib" ],
        # ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-3/2026-07-06/74ddb1ea6a6070093a137cb0c7c83e69.grib"]
        ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-2/2026-07-28/9b4307b60161dfa361df662920e6afd.grib"]
    )
)

era5_precipitation = dict( # precipitation
    zip(
        [ DATA_PATH / "ERA5" / "ERA5_monthly_averaged_reanalysis_precip.grib" ],
        # ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-3/2026-07-06/e5e704ac573ea2e35ecb667b40b8e9e1.grib"]
        ["https://object-store.os-api.cci2.ecmwf.int/cci2-prod-cache-1/2026-07-28/b2808bbda1c9dcc7b83319ca8f4accf9.grib"]
    )
)

###############################################################################
# Registry of all datasets
###############################################################################

DATASETS = {
    "hu_annual": hu_annual,
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

# Generic download function
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

# Specific download function for GRDI
def download_grdi(path: Path) -> None:
    """
    GRDI requires authenticated download.
    """

    if path.exists():
        print(f"Skipping {path.name}")
        return

    with open(GRDI_CREDS) as f:

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

# Specific download function for Hu et al.
# Hardcoded nested path inside each Hu et al. tar.gz — may need updating if 
# Zenodo record is revised:
_HU_TAR_INNER_PATH = Path("data/huyhang/sklearn2/2000_2023/firepm25no0")

def download_hu(path: Path, url: str) -> None:
    """
    Download a Hu et al. tar.gz, extract the .nc file, and clean up.
    Target `path` points to the final .nc file. If it exists, skip entirely.
    """
    if path.exists():
        print(f"Skipping {path.name}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    tar_path = path.with_suffix(".nc.tar.gz")  # temporary download location

    print(f"[DOWNLOAD] {tar_path.name}")
    subprocess.run(["curl", "-L", "--fail", "-o", str(tar_path), url], check=True)

    print(f"[EXTRACT] {tar_path.name}")
    subprocess.run(["tar", "-xzf", str(tar_path), "-C", str(path.parent)], check=True)

    # Move .nc out of the nested directory structure
    extracted = path.parent / _HU_TAR_INNER_PATH / path.name
    if not extracted.exists():
        raise FileNotFoundError(
            f"Expected extracted file not found: {extracted}\n"
            f"The tar.gz internal structure may have changed — check _HU_TAR_INNER_PATH."
        )

    extracted.rename(path)
    print(f"[MOVED] {path.name}")

    # Clean up tar.gz and extracted directory scaffold
    tar_path.unlink()
    shutil.rmtree(path.parent / "data", ignore_errors=True)
    print(f"[CLEANED] {tar_path.name}")


def download_dataset(name: str, downloads: dict[Path, str]) -> None:

    for path, url in tqdm(downloads.items()):

        if name == "grdi":
            download_grdi(path)
        elif name == "hu_annual":
            download_hu(path, url)
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
