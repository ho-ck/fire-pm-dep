# Fit emissions-smoke Bayesian (INLA) model
# - Load Xu PM & GFED emissions data
# - Construct adjacency matrix
# - Fit BYM2 INLA model and save output
# Usage:
#   Rscript fit_inla.R
# Date created: 11/12/2025

# --- Setup & libraries --------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(sf)
    library(spdep)
    library(INLA)
})

# --- Paths & environment ------------------------------------------------
root <- rprojroot::find_root(rprojroot::has_file(".gitignore")) # project root has a .gitignore # nolint

Sys.setenv(PROJ_DATA = "/home/users/cho00/miniconda3/envs/inla/share/proj")

data_path <- "/work/scratch-pw4/cho00/data/spatial"
model_save_dir   <- file.path(data_path, "transported_pm_model")

if (!dir.exists(model_save_dir)) {
    dir.create(model_save_dir, recursive = TRUE)
}

# Source helper functions
source(file.path(root, "src/transported_pm_model", "utils/utils_fit_inla.R" ))

# --- Load PM & GFED emissions (monthly) data and wrangle ----------------
data <- load_data_and_wrangle(
    file.path(data_path, "transported_GFED_emissions_regional"),
    years_sel = 2000:2017
)

# --- Build sf object & adjacency matrix ---------------------------------
sf_data <- data %>%
    mutate(geometry = sf::st_as_sfc(geometry)) %>%
    st_as_sf(crs = 4326)

sf_unique <- sf_data %>%
    group_by(grid_id) %>%
    slice(1)

nb <- poly2nb(sf_unique, row.names = sf_unique$grid_id, queen = TRUE)

adj_path <- file.path(model_save_dir, "afr.adj")
nb2INLA(file = adj_path, nb = nb)   # save adj matrix

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

saveRDS(model, file.path(model_save_dir, "inla_model.rds"))

print("Done!")
