# Post-processing for deprivation-PM2.5 Bayesian hierarchical models
# - Loads fitted brms models
# - Extracts posterior PC1 slopes (global, country, U/R, pooled)
# - Computes population-weighted country-average effects
# - Joins to shapefiles and produces plots/maps (saves to output dir)
# Usage:
#   Rscript results_bhm.R configs/post_proc_cfg.yaml <model_index>
# Date created: 08/12/2025

# ========================================================================
# 0. Setup & libraries ---------------------------------------------------
# ========================================================================
suppressPackageStartupMessages({
    library(tidyverse)
    library(brms)
    library(rstan)
    library(cmdstanr)
    library(yaml)
    library(sf)
    library(ggplot2)
    library(patchwork)
    library(ggpattern)
    library(grDevices)
})

# --- 0.1 Parse args -----------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
    stop("Usage: Rscript results_bhm.R <config.yml> <model_index>",
         call. = FALSE)
}
config_file  <- args[1]
model_index  <- as.integer(args[2])

# --- 0.2 Load config & set environment ----------------------------------
cfg <- yaml::read_yaml(config_file)

Sys.setenv(PROJ_DATA = cfg$environment$proj_data)
set_cmdstan_path(cfg$environment$cmdstan_path)
setwd(cfg$project$wd)

data_dir  <- cfg$project$data_dir
model_dir <- cfg$project$model_save_dir

# --- 0.3 Source post-processing helper functions ------------------------
source("post_proc_utils.R")

# --- 0.4 Model choice ---------------------------------------------------
model_names <- names(cfg$models)

if (model_index < 1 || model_index > length(model_names)) {
    stop(paste0("model_index must be between 1 and ", length(model_names)))
}
model_choice  <- model_names[model_index]
model_cfg     <- cfg$models[[model_choice]]
model_formula <- as.formula(model_cfg$formula)

message("Post-processing model: ", model_choice,
        " (", model_cfg$description, ")")

# ---- 0.5 Output directory ----------------------------------------------
out_dir <- file.path(cfg$project$results_out_dir, model_choice) # TODO: use the config filename as the dirname for the outputs
if (!dir.exists(out_dir)) {
    dir.create(out_dir, recursive = TRUE)
}

# ========================================================================
# 1. Main: load data, load model, post-processing ------------------------
# ========================================================================

# --- 1.1 Load nat bounds shapefile, data, and do PCA --------------------
nat_bounds <- sf::read_sf(
    file.path(data_dir, "nat_boundaries/WB_countries_Admin0_10m/")
) %>%
    filter(CONTINENT == "Africa")

df <- readr::read_csv(
    file.path(data_dir, "descriptive_stats_GDP_pc/df_af_annual.csv"),
    show_col_types = FALSE
)

# Do PCA
df <- prepare_data(df, cfg$pca, model_formula)

# --- 1.2 Load model -----------------------------------------------------
model_file <- build_modelfile(model_dir, model_choice, cfg$mcmc, cfg$priors)
model      <- readRDS(model_file)

# Summary diagnostics, priors, Stan code
capture.output(summary(model), file = file.path(out_dir, "model_summary.txt"))
write_csv(model$prior, file = file.path(out_dir, "model_priors.csv"))
capture.output(stancode(model), file = file.path(out_dir, "model.stan"))

# Trace plots
trace_plots <- plot(model)
for (i in seq_along(trace_plots)) {
    ggsave(
        filename = file.path(out_dir, paste0("mcmc_trace_", i, ".png")),
        plot     = trace_plots[[i]]
    )
}

# --- 1.3 Posterior draws and marginal effects ---------------------------
draws <- as_draws_df(model)

slopes_list <- extract_slopes_ur(draws)
slopes_global_ur   <- slopes_list$slopes_global_ur  # posterior summary
slopes_country_ur  <- slopes_list$slopes_country_ur # posterior summary
b_PC1              <- slopes_list$b_PC1             # draws
b_PC1_x_urban      <- slopes_list$b_PC1_x_urban     # draws
r_country_PC1_long <- slopes_list$r_country_PC1_long    # draws
r_country_PC1_x_urban_long <- slopes_list$r_country_PC1_x_urban_long    # draws

# Post-stratification: pop-weighted country-average effects (& global pooled)
pw_list <- compute_pw_slopes(
    df,
    b_PC1,
    b_PC1_x_urban,
    r_country_PC1_long,
    r_country_PC1_x_urban_long
)

slopes_global_avg  <- pw_list$slopes_global_avg
slopes_country_avg <- pw_list$slopes_country_avg

# ========================================================================
# 2. Plot results --------------------------------------------------------
# ========================================================================

# --- 2.1 Join U/R PC1 slopes to country polygons (to map) ---------------
sf_slopes_country_ur <- nat_bounds %>%
    select(WB_NAME, SUBREGION, geometry) %>%
    right_join(
        slopes_country_ur,
        by = c("WB_NAME" = "country")
    )

# --- 2.2 Forestplot + map panel -----------------------------------------
forestplot_maps_patchwork <- build_forestplot_map_panel(
    slopes_global_ur     = slopes_global_ur,
    slopes_country_ur    = slopes_country_ur,
    slopes_global_avg    = slopes_global_avg,
    slopes_country_avg   = slopes_country_avg,
    sf_slopes_country_ur = sf_slopes_country_ur
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

# --- 2.3 Maps of country-level random intercept and year slope ----------
country_re <- extract_country_re(draws, model_choice)   # will be NULL if no country-level intercept or year slope   # nolint

if (!is.null(country_re)) {
    # Join country REs to nat_bounds
    map_sf <- nat_bounds %>% 
        right_join(country_re, by = c("WB_NAME" = "country"))

    # Plot country REs (function does saving, plots are specific to model_choice)   # nolint
    plot_country_random_effects(
        map_sf     = map_sf,
        nat_bounds = nat_bounds,
        out_dir    = out_dir,
        model_choice = model_choice
    )
}

# --- 2.4 Maps of grid-level random effects ------------------------------
grid_re <- extract_grid_re(draws, model_choice) # will be NULL if no grid-level intercept or year slope   # nolint

if (!is.null(grid_re)) {
    # Join grid REs to df (which has geometries) to map
    map_data <- df %>%
        group_by(lon, lat) %>%  # group by lon/lat, get geometry
        summarise(
            across(
                c("geometry", "country", "region", "ISO_A3", "grid_id"),
                ~ first(.x)
            ),
            .groups = "drop"
        ) %>%
        left_join(grid_re, by = "grid_id")

    # Convert to sf to map
    map_sf <- map_data %>%
        mutate(geometry = sf::st_as_sfc(geometry)) %>%
        sf::st_as_sf(crs = 4326)

    # Plot grid REs (function does saving, plots are specific to model_choice)
    plot_grid_random_effects(
        map_sf     = map_sf,
        nat_bounds = nat_bounds,
        out_dir    = out_dir,
        model_choice = model_choice
    )
}

message("Done!")
