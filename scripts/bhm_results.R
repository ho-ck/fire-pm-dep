# Post-processing for deprivation-PM2.5 Bayesian hierarchical models
# - Loads fitted brms models
# - Extracts posterior deprivation (PC1) slopes (global, country, U/R, pooled)
# - Computes population-weighted country-average effects
# - Joins to shapefiles and produces plots/maps (saves to output dir)
# Usage:
#   Rscript bhm_results.R configs/bhm_results_cfg.yaml
# Date created: 15/12/2025

# ==============================================================================
# 0. Setup & libraries ---------------------------------------------------------
# ==============================================================================
suppressPackageStartupMessages({
    library(tidyverse)
    library(brms)
    library(rstan)
    library(cmdstanr)
    library(yaml)
    library(sf)
    library(patchwork)
    library(ggpattern)
    library(grDevices)
})

# --- 0.1 Parse args -----------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript bhm_results.R <config.yml>",
         call. = FALSE)
}
config_file  <- args[1]

# --- 0.2 Load config & set environment ----------------------------------------
root <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
cfg <- yaml::read_yaml(file.path(root, config_file))

Sys.setenv(PROJ_DATA = cfg$environment$proj_data)
set_cmdstan_path(cfg$environment$cmdstan_path)

data_filepath  <- cfg$project$data_filepath
model_dir <- cfg$project$model_save_dir

# --- 0.3 Source post-processing helper functions ------------------------------
source(file.path(root, "src/deprivation_pm_bhm/data_prep.R"))
source(file.path(root, "src/deprivation_pm_bhm/model_setup.R"))
source(file.path(root, "src/deprivation_pm_bhm/model_summary.R"))
source(file.path(root, "src/deprivation_pm_bhm/postprocess.R"))
source(file.path(root, "src/deprivation_pm_bhm/plotting.R"))
source(file.path(root, "src/utils/utils.R"))    # logging, outdirs etc.

# --- 0.4 Model config ---------------------------------------------------------
model_cfg       <- cfg$model
model_name      <- model_cfg$name
model_formula   <- as.formula(paste(
    model_cfg$outcome, "~", model_cfg$formula_rhs
))

logging(
    "Post-processing model: ", model_name, " (", model_cfg$description, ").",
    "Outcome: ", model_cfg$outcome
)

# ---- 0.5 Output directory ----------------------------------------------------
out_dir <- results_dirname_builder(
    project_root = root,
    outputs_dir = "outputs/deprivation_pm_bhm",
    config_fname = config_file
)
if (!dir.exists(out_dir)) {
    dir.create(out_dir, recursive = TRUE)
}


# ==============================================================================
# 1. Main: load data, load model, post-processing ------------------------------
# ==============================================================================
logging("Loading data...")

# --- 1.1 Load nat bounds shapefile, data, and do PCA --------------------------
nat_bounds  <- sf::read_sf( cfg$project$nat_bounds_filepath ) %>%
    filter(CONTINENT == "Africa")

df  <- readr::read_csv( data_filepath )

# Do PCA (only for rows with complete SE data)
df_pca  <- compute_pca(df, cfg$data$se_indicators)$data

# Join PCs back onto df (helper funct)
df  <- prepare_analysis_data(df, df_pca)

# --- 1.2 Load model -----------------------------------------------------------
logging("Loading model...")

model_file <- build_modelfile(
    out_path    = model_dir,
    outcome     = model_cfg$outcome,
    model_name  = model_name,
    mcmc_cfg    = cfg$mcmc,
    priors_cfg  = cfg$priors
)
model   <- readRDS(model_file)

# Summary diagnostics, priors, Stan code
logging("Saving model diagnostics to output dir: ", out_dir)
save_brms_diagnostics(model, out_dir, save_trace = TRUE, save_stan = TRUE)

# --- 1.3 Posterior draws and marginal effects ---------------------------------
logging("Extracting and summarising posterior draws...")
draws   <- as_draws_df(model)

# PC1 effects in U & R (draws)
pc1_draws_ur <- extract_pc1_draws_ur(draws)      

# Posterior summary by country & U/R
slopes_ur <- summarise_draws(
    pc1_draws_ur, 
    pivot = TRUE, pivot_cols = c("rural", "urban"),
    names_to = "urban_rural_cat",
    group_vars = c("country", "urban_rural_cat", "term")
)

# Post-stratification: p-w avg of U & R PC1 draws
pc1_draws_pw_avg <- compute_pw_pc1_draws(pc1_draws_ur, df)

# Posterior summary of U/R pooled effects draws
slopes_pw_avg <- summarise_draws( 
    pc1_draws_pw_avg, 
    pivot = TRUE, pivot_cols = c("pooled"),
    names_to = "urban_rural_cat",
    group_vars = c("country", "urban_rural_cat", "term")
)

# Country-level random intercept and year slope (NULL if absent from model)
country_re_draws <- extract_country_re_draws(draws)
if (!is.null(country_re_draws)) {
    country_re <- summarise_draws(
        country_re_draws, group_vars = "country",
        estimands = c("Intercept", "year")
    )
} else { country_re <- NULL }

# Grid-level random intercept and year slope (NULL if absent from model)
grid_re_draws <- extract_grid_re_draws(draws)
if (!is.null(grid_re_draws)) {
    grid_re <- summarise_draws(
        grid_re_draws, group_vars = c("grid_id"), 
        estimands = c("Intercept", "year")
    )
} else { grid_re <- NULL }

# ==============================================================================
# 2. Plot results --------------------------------------------------------------
# ==============================================================================
logging("Plotting foresplot + maps panel...")

# --- 2.1 Join U/R PC1 slopes to country polygons (to map) ---------------------
sf_slopes_ur <- nat_bounds %>%
    select(WB_NAME, SUBREGION, geometry) %>%
    right_join( slopes_ur, by = c("WB_NAME" = "country") )

# --- 2.2 Forestplot + map panel -----------------------------------------------
forestplot_maps_patchwork <- build_forestplot_map_panel(
    slopes_ur, slopes_pw_avg, sf_slopes_ur
)

ggsave(
    filename = file.path(out_dir, "forestplot_maps_panel.png"),
    plot     = forestplot_maps_patchwork,
    width    = 18,
    height   = 14,
    dpi      = 450,
    device   = grDevices::png,
    bg       = "white"
)

# --- 2.3 Maps of country-level random intercept and year slope ----------------
if (!is.null(country_re)) {
    logging("Plotting country-level random intercept + year slope...")

    # Join country REs to nat_bounds
    map_sf <- nat_bounds %>% 
        right_join(country_re, by = c("WB_NAME" = "country"))

    # Intercept and year slope
    country_re_plots <- plot_country_random_effects(
        map_sf     = map_sf,
        nat_bounds = nat_bounds
    )

    for (i in seq_along(country_re_plots)) {
        ggplot2::ggsave(
            plot        = country_re_plots[[i]],
            filename    = file.path(out_dir,
                                    paste0("map_country_random_",
                                            names(country_re_plots)[[i]],
                                            ".png")),
            width       = 8,
            height      = 6,
            bg          = "white"    
        )
    }
}

# --- 2.4 Maps of grid-level random effects ------------------------------------
if (!is.null(grid_re)) {
    logging("Plotting grid-level random intercept + year slope...")

    # Join grid REs to df (which has geometries) to map
    map_sf <- df %>%
        group_by(lon, lat) %>%  # group by lon/lat, get geometry
        slice(1) %>%
        left_join(grid_re, by = "grid_id") %>%
        mutate(geometry = sf::st_as_sfc(geometry)) %>%
        sf::st_as_sf(crs = 4326)

    # Intercept and year sloep
    grid_re_plots <- plot_grid_random_effects(
        map_sf     = map_sf,
        nat_bounds = nat_bounds
    )

    for (i in seq_along(grid_re_plots)) {
        ggplot2::ggsave(
            plot        = grid_re_plots[[i]],
            filename    = file.path(out_dir,
                                    paste0("map_grid_random_",
                                            names(grid_re_plots)[[i]],
                                            ".png")),
            width       = 8,
            height      = 6,
            bg          = "white"    
        )
    }
}

logging("Done!")
