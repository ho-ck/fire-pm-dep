# Use fitted INLA BYM2 model to make in-sample predictions of fire_PM25
# - Load fitted model (RDS file includes posterior of linear predictor)
# - Extract posterior predicted fire_PM25 for years 2000-2017 (monthly)
# - Estimate local & transported attributable fractions and attributable PM
# - Aggregate to annual averages per grid (for deprivation associations later)
# Usage:
#   Rscript pred_local_transported.R configs/pred_local_transported_pm_cfg.yaml
# Date created: 11/12/2025

# --- Setup & libraries --------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(dtplyr)
    library(INLA)
    library(yaml)
})

# --- Parse yaml arg -----------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript pred_local_transported_pm.R configs/fit_inla_cfg.yaml",
         call. = FALSE)
}
config_file  <- args[1]

# --- Load config and set environment ------------------------------------
root <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
cfg <- yaml::read_yaml(file.path(
    root, "src/transported_pm_model", config_file))

# Environment & paths
Sys.setenv(PROJ_DATA = cfg$environment$proj_data)

emis_data_dir       <- cfg$project$emis_data_dir    # emissions data (monthly)
se_data_filepath    <- cfg$project$se_data_filepath
model_filepath      <- cfg$project$model_filepath
out_data_filepath   <- cfg$project$out_data_filepath
if (!dir.exists(dirname(out_data_filepath))) {
    dir.create(dirname(out_data_filepath), recursive = TRUE)
}

# --- Source helper functions --------------------------------------------
source(file.path(root, "src/transported_pm_model", "utils/utils_fit_inla.R"))
source(file.path(root, "src/deprivation_pm_model", "utils/utils_fit_bhm.R"))    # PCA utils #nolint
source(file.path(root, "src/transported_pm_model", "utils/utils_inla_posterior.R")) #nolint
source(file.path(root, "src/transported_pm_model", "utils/utils_attr_pm.R"))

# --- Load PM & GFED emissions (monthly) data and wrangle ----------------
yrs  <- cfg$data$years
logging("Loading data for years:", yrs$start, "-", yrs$end)

emis_data <- load_data_and_wrangle(emis_data_dir, 
                              years_sel = yrs$start : yrs$end )

# --- Load INLA model ----------------------------------------------------
logging("Loading INLA model...")

model <- readRDS(model_filepath)

# --- Load PM & socioeconomic data  --------------------------------------
logging("Loading socioeocnomic data...")
df <- readr::read_csv(se_data_filepath, show_col_types = FALSE)

# --- Extract posterior mean fire_PM25 -----------------------------------
post_mean_fitted_values <- model$summary.fitted.values$mean

# Join back to emis data
result_data <- bind_cols(
    emis_data,
    as_tibble_col(post_mean_fitted_values, column_name = "pred_fire_PM25")
)

# --- Attributable PM2.5 from band-specific emissions --------------------
logging("Estimating attributable local/transported PM2.5...")

# Regression coefficients for emissions bands, transformed to orig scale
emis_coef <- get_transformed_emis_coefs(model, emis_data)

attr_pm_frac    <- attr_pm_frac_by_band(emis_coef, emis_data)
result_data     <- bind_cols(result_data, attr_pm_frac)

# --- Aggregate by year --------------------------------------------------
logging("Aggregating by year...")

result_data_annual <- lazy_dt(result_data) %>% 
    group_by(lon, lat, year) %>% 
    summarise(
        across(starts_with("attr_fire_PM25_"), ~ mean(.x, na.rm = TRUE)),
        .groups = "drop"
    ) %>% 
    as_tibble()

# Re-compute fractions using the aggregated annual attributable PM
# (i.e., don't average the *fractions*)
result_data_annual <- result_data_annual %>%
    # Compute total PM across bands
    mutate(total_attr_fire_PM25 = rowSums(
        across(starts_with("attr_fire_PM25_emis")),
        na.rm = TRUE
    )) %>%
    mutate(across(starts_with("attr_fire_PM25_emis"), 
                  ~ .x / total_attr_fire_PM25,
                  .names = "frac_{sub('^attr_', '', .col)}")) %>%
    select(-total_attr_fire_PM25)  # drop helper col

# --- Group into within/beyond 100km -------------------------------------
result_data_annual <- result_data_annual %>% 
    mutate( # CHRIS NOTE / TODO: this is ugly and messes up regex matching later -- maybe just local_fire_PM25 and transported_fire_PM25?
        attr_fire_PM25_emis_0_100km = 
            attr_fire_PM25_emis_0_20km + attr_fire_PM25_emis_20_100km,
        attr_fire_PM25_emis_100_2000km = 
            attr_fire_PM25_emis_100_200km + attr_fire_PM25_emis_200_350km + 
            attr_fire_PM25_emis_350_500km + attr_fire_PM25_emis_500_750km +
            attr_fire_PM25_emis_750_1000km + attr_fire_PM25_emis_1000_1500km +
            attr_fire_PM25_emis_1500_2000km,
        frac_fire_PM25_emis_0_100km = 
            frac_fire_PM25_emis_0_20km + frac_fire_PM25_emis_20_100km,
        frac_fire_PM25_emis_100_2000km = 
            frac_fire_PM25_emis_100_200km + frac_fire_PM25_emis_200_350km + 
            frac_fire_PM25_emis_350_500km + frac_fire_PM25_emis_500_750km +
            frac_fire_PM25_emis_750_1000km + frac_fire_PM25_emis_1000_1500km +
            frac_fire_PM25_emis_1500_2000km
    )

# --- Join back to socioeconomic data ------------------------------------
df <- df %>% left_join(result_data_annual, by = c("lon", "lat", "year"))

# --- Write out ----------------------------------------------------------
logging("Writing to CSV...")
write_csv(df, out_data_filepath)

logging("Done!")
