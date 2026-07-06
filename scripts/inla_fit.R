# Fit emissions-smoke Bayesian (INLA) model
# - Load Xu PM & GFED emissions data
# - Construct adjacency matrix
# - Fit BYM2 INLA model and save output
# Usage:
#   Rscript inla_fit.R configs/inla_fit_cfg.yaml
# Date created: 11/12/2025

# --- Setup & libraries --------------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(sf)
    library(spdep)
    library(INLA)
    library(yaml)
})

# --- Source helper functions --------------------------------------------------
root    <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
source(file.path(root, "src/transported_pm_inla/data_prep.R"))
source(file.path(root, "src/transported_pm_inla/adj_matrix.R"))

# --- Parse yaml arg -----------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript inla_fit.R configs/inla_fit_cfg.yaml",
         call. = FALSE)
}
config_file  <- args[1]

# --- Load config, set environment, set paths ----------------------------------
cfg <- yaml::read_yaml(file.path(root, config_file))

# Environment & paths
Sys.setenv(PROJ_DATA = cfg$environment$proj_data)

data_dir        <- cfg$project$emis_data_dir    # emissions data (monthly)
model_filepath  <- cfg$project$model_filepath
if (!dir.exists(dirname(model_filepath))) {
    dir.create(dirname(model_filepath), recursive = TRUE)
}

# --- Load PM & GFED emissions (monthly) data and wrangle ----------------------
yrs  <- cfg$data$years
logging("Loading data for years:", yrs$start, "-", yrs$end)

data <- load_data_and_wrangle(data_dir, 
                              years_sel = yrs$start : yrs$end )

# --- Build adjacency matrix if doesn't already exist --------------------------
adj_path <- cfg$data$adj_path

if (!file.exists(adj_path)) {
    logging("Adjacency matrix file not found. Creating:", adj_path)

    nb <- create_nb_list(data, crs = 4326)
    nb2INLA(file = adj_path, nb = nb)   # save adj matrix

    logging("Saved adjacency matrix to", adj_path)
} else {
    logging("Adjacency matrix already exists at:", adj_path, "\nSkipping...")
}

# --- Standardise predictors ---------------------------------------------------
data_scaled <- data %>%
    mutate(
        across(matches("^emis.*km$"), ~ scale(.x)),
        across(c("u10", "v10", "d2m", "t2m", "sp", "tp"), ~ scale(.x))
    )

# --- Priors -------------------------------------------------------------------
hyper_bym2 <- list(
    # Marginal variance of the BYM2 spatial effect:
    # P(1 / sqrt(tau) > 50 / 0.31) = 0.01
    # -> implies an approximate marginal spatial SD of 50 with probability 0.01
    # -> penalises only implausibly large spatial effects
    prec = list(prior = "pc.prec", param = c(50 / 0.31, 0.01)),
    
    # Mixing parameter:
    # A priori, 50% probability that more than half of the spatial variance
    # is attributed to the structured spatial effect.
    phi  = list(prior = "pc", param = c(0.5, 0.5))
)

# Observation / residual variance:
# P(SD_residual > 50) = 0.01
hyper_sigma <- list(
    hyper = list(
        prec = list(prior = "pc.prec", param = c(50, 0.01))
    )
)

# --- Fit INLA model -----------------------------------------------------------
logging("Fitting INLA model...")

formula <- fire_PM25 ~
    emis_0_20km + emis_20_100km + emis_100_200km + emis_200_350km +
    emis_350_500km + emis_500_750km + emis_750_1000km +
    emis_1000_1500km + emis_1500_2000km +
    u10 + v10 + d2m + t2m + sp + tp +
    f(grid_id, model = "bym2", graph = adj_path, scale.model = TRUE,
      hyper = hyper_bym2)

model <- inla(
    formula,
    family          = "gaussian",
    data            = data_scaled,
    control.fixed   = list(mean = 0, prec = 1e-4),
    control.family  = hyper_sigma,
    control.compute = list(config = TRUE),
    control.inla    = list(strategy = "gaussian"),
    verbose         = TRUE
)

logging("Model fitting complete. Saving RDS...")

saveRDS(model, model_filepath)

logging("Saved model to:", model_filepath)
logging("Done!")
