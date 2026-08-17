# fire-pm-dep
Analysis for paper: Heterogeneous patterns of deprivation and fire-related air pollution exposure in Africa.



**Note 06/07/2026 -- to complete:**

Setup scripts (`src/setup_scripts/`):

1. `download_data.py`
2. `create_urban_pop_tifs.py`       # NOTE 06/07/2026: could be folded into the below
3. `create_annual_pm_se_data.py`    # global annual datasets with fire PM and socioeconomic data
4. `prepare_africa_data.py`         # filter for Africa, create derived variables: child dependency pct, log GDP pc, percentages from prevalences etc.

5. `align_climate_data_monthly.py`  # independent of socioeconomic data (saves annual files, each with 12mos of data)
6. `transported_gfed_emissions.py`  # creates the wind-weighted distance band predictors (saves annual files, each with 12mos of data)

Model run scripts (`scripts/`):
7. `inla_fit.R`                     # fits INLA model (uses a function from `src/transported_pm_inla/data_prep.R` to load the annual files of monthly emissions/PM data)
8. `pred_local_transported_pm.R`    # uses fitted INLA model to predict loc/tp pollution (monthly), then aggregates to annual. Also joins onto annual socioeconomic data (prod by `prepare_africa_data.py`)
9. `bhm_fit.R`                      # fits deprivation-PM Bayesian hierarchical model -- can supply input data from script `4` or `8`, depending on model outcome (total, local, or transported PM)

Analysis scripts/notebooks:
10. `sandboxes/2026-06-01_accra_figures.ipynb`      # makes all plots for paper... (NOTE 06/07/2026: could clean up / formalise into script rather than NB) -- also to update: make tables of country deprivation coefficients
11. `sandboxes/2026-02-09_inla_model_summary.ipynb` # summary of fitted INLA model (with forestplot) -- NOTE 06/07/2026: to update, make table of regression coefficients (on emissions scale)
