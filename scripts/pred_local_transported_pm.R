# Use fitted INLA BYM2 model to make in-sample predictions of fire_PM25
# - Load fitted model (RDS file includes posterior of linear predictor)
# - Extract posterior predicted fire_PM25 for years 2000-2017 (monthly)
# - Estimate local & transported attributable fractions and attributable PM
# - Aggregate to annual averages per grid (for deprivation associations later)
# Usage:
#   Rscript pred_local_transported_pm.R configs/inla_pred_local_transported_cfg.yaml    #nolint
# Date created: 22/12/2025

# --- Setup & libraries --------------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(dtplyr)
    library(INLA)
    library(yaml)
})

# --- Source helper functions --------------------------------------------------
root    <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
source(file.path(root, "src/transported_pm_inla/data_prep.R"))
source(file.path(root, "src/transported_pm_inla/adj_matrix.R"))
source(file.path(root, "src/transported_pm_inla/model_summary.R"))
source(file.path(root, "src/transported_pm_inla/attributable_pm.R"))

# --- Parse yaml arg -----------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript pred_local_transported_pm.R configs/inla_pred_local_transported_cfg.yaml", #nolint
         call. = FALSE)
}
config_file  <- args[1]

# --- Load config, set environment, set paths ----------------------------------
cfg     <- yaml::read_yaml(file.path(root, config_file))

# Environment & paths
Sys.setenv(PROJ_DATA = cfg$environment$proj_data)

emis_data_dir       <- cfg$project$emis_data_dir    # emissions data (monthly)
se_data_filepath    <- cfg$project$se_data_filepath
model_filepath      <- cfg$project$model_filepath
out_data_filepath   <- cfg$project$out_data_filepath
if (!dir.exists(dirname(out_data_filepath))) {
    dir.create(dirname(out_data_filepath), recursive = TRUE)
}

# --- Load PM & GFED emissions (monthly) data and wrangle ----------------------
yrs  <- cfg$data$years
logging("Loading data for years:", yrs$start, "-", yrs$end)

emis_data <- load_data_and_wrangle(emis_data_dir, 
                              years_sel = yrs$start : yrs$end )

# --- Load INLA model ----------------------------------------------------------
logging("Loading INLA model...")

model <- readRDS(model_filepath)

# --- Load PM & socioeconomic data  --------------------------------------------
logging("Loading socioeocnomic data...")
df <- readr::read_csv(se_data_filepath, show_col_types = FALSE)

# --- Extract posterior mean predicted fire_PM25 -------------------------------
post_mean_fitted_values <- model$summary.fitted.values$mean

# Join back to emis data
result_data <- bind_cols(
    emis_data,
    as_tibble_col(post_mean_fitted_values, column_name = "pred_fire_PM25")
)

# --- Attributable PM2.5 from band-specific emissions --------------------------
logging("Estimating monthly attributable local/transported PM2.5...")

# Regression coefficients for emissions bands, transformed to orig scale
emis_coef       <- get_transformed_emis_coefs(model, emis_data)

attr_pm_frac    <- attr_pm_frac_by_band(emis_coef, emis_data)
result_data     <- bind_cols(result_data, attr_pm_frac)

# --- Aggregate by year --------------------------------------------------------
logging("Aggregating by year...")

result_data_annual <- lazy_dt(result_data) %>% 
    group_by(lon, lat, year) %>% 
    summarise(
        across(starts_with(c("attr_fire_PM25_", "bc_attr_fire_PM25_")),
               ~ mean(.x, na.rm = TRUE)
               ),
        .groups = "drop"
    ) %>% 
    as_tibble()

# Re-compute annual attributable fractions using the aggregated annual 
# model-attributable PM (not the bias-corrected estimates)
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

# --- Group into within/beyond 100km -------------------------------------------
result_data_annual <- result_data_annual %>%
    mutate( # CHRIS NOTE / TODO: this is ugly and messes up regex matching later -- maybe just local_fire_PM25 and transported_fire_PM25?
        # Model-attributable fire PM
        attr_fire_PM25_emis_0_100km = rowSums(across(matches(
            "^attr_fire_PM25_emis_(0_20|20_100)km$"
            ))),

        attr_fire_PM25_emis_100_2000km = rowSums(across(matches(
            "^attr_fire_PM25_emis_(100_200|200_350|350_500|500_750|750_1000|1000_1500|1500_2000)km$"    #nolint
            ))),

        # Bias-corrected attr PM
        bc_attr_fire_PM25_emis_0_100km = rowSums(across(matches(
            "^bc_attr_fire_PM25_emis_(0_20|20_100)km$"
            ))),

        bc_attr_fire_PM25_emis_100_2000km = rowSums(across(matches(
            "^bc_attr_fire_PM25_emis_(100_200|200_350|350_500|500_750|750_1000|1000_1500|1500_2000)km$" #nolint
            ))),

        # Attr frac by local/transported
        frac_fire_PM25_emis_0_100km = rowSums(across(matches(
            "^frac_fire_PM25_emis_(0_20|20_100)km$"
            ))),

        frac_fire_PM25_emis_100_2000km = rowSums(across(matches(
            "^frac_fire_PM25_emis_(100_200|200_350|350_500|500_750|750_1000|1000_1500|1500_2000)km$"    #nolint
            )))
  )

# --- Join back to socioeconomic data ------------------------------------------
df <- df %>% left_join(result_data_annual, by = c("lon", "lat", "year"))

# --- Write out ----------------------------------------------------------------
logging("Writing to CSV...")
write_csv(df, out_data_filepath)

logging("Done! Saved to CSV:", out_data_filepath)