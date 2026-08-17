# fire-pm-dep
Analysis for paper: Heterogeneous patterns of deprivation and fire-related air pollution exposure in Africa.

Setup scripts (`src/setup_scripts/`):

1. `download_data.py`
2. `create_urban_pop_tifs.py`       # creates geotiff raster data of urban population share
3. `create_annual_pm_se_data.py`    # global annual datasets with fire PM and socioeconomic data
4. `prepare_africa_data.py`         # filter for Africa, create derived variables: child dependency pct, log GDP pc, percentages from prevalences etc.

5. `align_climate_data_monthly.py`  # independent of socioeconomic data (saves annual files, each with 12mos of data)
6. `transported_gfed_emissions.py`  # creates the wind-weighted distance band predictors (saves annual files, each with 12mos of data)

Model run scripts (`scripts/`):

7. `inla_fit.R`                     # fits INLA model (uses a function from `src/transported_pm_inla/data_prep.R` to load the annual files of monthly emissions/PM data)
8. `pred_local_transported_pm.R`    # uses fitted INLA model to predict loc/tp pollution (monthly), then aggregates to annual. Also joins onto annual socioeconomic data (prod by `prepare_africa_data.py`)
9. `bhm_fit.R`                      # fits deprivation-PM Bayesian hierarchical model -- can supply input data from script `4` or `8`, depending on model outcome (total, local, or transported PM)
10. `run_kfold_cv.R`                # runs k-fold cross validation of the INLA emissions-PM2.5 model.

Analysis scripts/notebooks:

11. `paper_results/`                # directory containing notebooks with all results in the paper: inline numeric results and figures/tables. Results are saved to dir `paper_results/figures` and `paper_results/tables`


**Chris note 17/08: maybe to generate CSV of INLA regression coefficients and country-specific deprivation coefficients from BHM**