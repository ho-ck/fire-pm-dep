# Fit emissions-smoke Bayesian (INLA) model
# - Load Xu PM & GFED emissions data
# - Construct adjacency matrix
# - Fit BYM2 INLA model and save output
# Usage:
#   Rscript fit_inla.R configs/fit_inla_cfg.yaml
# Date created: 11/12/2025

# --- Setup & libraries --------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(sf)
    library(spdep)
    library(INLA)
    library(yaml)
})

# --- Parse yaml arg -----------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript fit_inla.R configs/fit_inla_cfg.yaml",
         call. = FALSE)
}
config_file  <- args[1]

# --- Load config and set environment ------------------------------------
root <- rprojroot::find_root(rprojroot::has_file(".gitignore")) # project root has a .gitignore # nolint
cfg <- yaml::read_yaml(file.path(
    root, "src/transported_pm_model", config_file))

# Environment & paths
Sys.setenv(PROJ_DATA = cfg$environment$proj_data)

data_dir        <- cfg$project$data_dir
model_save_dir  <- cfg$project$model_save_dir
if (!dir.exists(model_save_dir)) {
    dir.create(model_save_dir, recursive = TRUE)
}

# Source helper functions
source(file.path(root, "src/transported_pm_model", "utils/utils_fit_inla.R"))
source(file.path(root, "src/transported_pm_model", "utils/utils_adj_matrix.R"))

# --- Load PM & GFED emissions (monthly) data and wrangle ----------------
yrs  <- cfg$data$years
logging("Loading data for years:", yrs$start, "-", yrs$end)

data <- load_data_and_wrangle(data_dir, 
                              years_sel = yrs$start : yrs$end )

# --- Build adjacency matrix if doesn't already exist --------------------
adj_path <- cfg$data$adj_path

if (!file.exists(adj_path)) {
    logging("Adjacency matrix file not found. Creating:", adj_path)

    nb <- create_nb_list(data, crs = 4326)
    nb2INLA(file = adj_path, nb = nb)   # save adj matrix

    logging("Saved adjacency matrix to", adj_path)
} else {
    logging("Adjacency matrix already exists at:", adj_path, "\nSkipping...")
}


# --- Standardise predictors ---------------------------------------------
data_scaled <- data %>%
    mutate(
        across(matches("^emis.*km$"), ~ scale(.x)),
        across(c("u10", "v10", "d2m", "t2m", "sp", "tp"), ~ scale(.x))
    )

# --- Priors -------------------------------------------------------------
hyper_bym2 <- list(
    prec = list(prior = "pc.prec", param = c(5/0.31, 0.01)),
    phi  = list(prior = "pc", param = c(0.5, 2/3))
)

hyper_sigma <- list(
    hyper = list(
        prec = list(prior = "pc.prec", param = c(10, 0.01))
    )
)

# --- Fit INLA model -----------------------------------------------------
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
    family = "gaussian",
    data = data_scaled,
    control.fixed  = list(mean = 0, prec = 1e-4),
    control.family = hyper_sigma,
    control.compute = list(config = TRUE),
    control.inla = list(strategy = "gaussian"),
    verbose = TRUE
)

logging("Model fitting complete. Saving RDS...")

saveRDS(model, file.path(model_save_dir, "inla_model.rds"))

logging("Saved model to:", file.path(model_save_dir, "inla_model.rds"))
logging("Done!")
