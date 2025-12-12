# Fit deprivation-PM2.5 Bayesian hierarchical models
# - Load data & do PCA to construct deprivation index
# - Estimate model as specified in config file and save to RDS file
# Usage:
#   Rscript fit_bhm.R configs/fit_bhm_cfg.yaml <model_index>
# (Path to config should be relative to this script)
# Date created: 08/12/2025

# --- Setup & libraries --------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(brms)
    library(cmdstanr)
    library(rprojroot)
    library(yaml)
})

# --- Parse args ---------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
    stop("Usage: Rscript fit_bhm.R configs/fit_bhm_cfg.yaml <model_index>",
         call. = FALSE)
}
config_file  <- args[1]
model_index  <- as.integer(args[2])

# --- Load config and set environment ------------------------------------
root <- rprojroot::find_root(rprojroot::has_file(".gitignore")) # project root has a .gitignore # nolint
cfg <- yaml::read_yaml(file.path(
    root, "src/deprivation_pm_model", config_file))

# Environment & paths
Sys.setenv(PROJ_DATA = cfg$environment$proj_data)
set_cmdstan_path(cfg$environment$cmdstan_path)

data_dir        <- cfg$project$data_dir
model_save_dir  <- cfg$project$model_save_dir
if (!dir.exists(model_save_dir)) {
    dir.create(model_save_dir, recursive = TRUE)
}

# Source helper functions
source(file.path(root, "src/deprivation_pm_model", "utils/utils_fit_bhm.R" ))

# --- MCMC settings ------------------------------------------------------
n_chains    <- cfg$mcmc$chains
n_iter      <- cfg$mcmc$iter
n_warmup    <- cfg$mcmc$warmup
n_threads   <- cfg$mcmc$threads
adapt_delta <- cfg$mcmc$adapt_delta

beta_prior_sd    <- cfg$priors$beta_sd
scale_prior_dist <- cfg$priors$scale_dist

# --- Model choice -------------------------------------------------------
model_names <- names(cfg$models)

if (model_index < 1 || model_index > length(model_names)) {
    stop(paste0("model_index must be between 1 and ", length(model_names)))
}
model_choice <- model_names[model_index]
model_cfg    <- cfg$models[[model_choice]]

message("Running model: ", model_choice, " (", model_cfg$description, ")")

# --- Load data -----------------------------------------------------------
df <- readr::read_csv(
    file.path(data_dir, "descriptive_stats_GDP_pc/df_af_annual.csv"),   # TODO: update this so that the full path to the CSV is in the config file. that way it is easier to use a differnet input dataset, i.e., where the outcome is local_fire_PM25 (or transported etc.)
    show_col_types = FALSE
)

# --- Do PCA -------------------------------------------------------------
pca_res <- compute_pca(
    df,
    se_indicators = cfg$data$se_indicators,
    scale = TRUE,
    center = TRUE
)

df_aug <- pca_res$data  # 523,116 rows

# Save PCA loadings & variance explained
write_csv(
    as.data.frame(pca_res$pca$rotation) %>% 
        rownames_to_column("Variable"),
    file.path(model_save_dir, "pca_loadings.csv")
)
write_csv(
    as.data.frame(summary(pca_res$pca)$importance) %>% 
        rownames_to_column("Metric"),
    file.path(model_save_dir, "pca_var_explained.csv")
)

# --- Build formula from config ------------------------------------------
model_formula <- as.formula(
    paste( cfg$data$outcome, " ~ ", model_cfg$formula_rhs )
)

# --- Prepare data --------------------------------------------------------
data_mod <- prepare_model_data(df_aug, model_formula, cfg$data)

# --- Priors --------------------------------------------------------------
prior <- build_priors(beta_prior_sd, scale_prior_dist)

# --- Fit model -----------------------------------------------------------
outfile <- build_modelfile(model_save_dir, cfg$data$outcome,
                           model_choice, cfg$mcmc, cfg$priors)

brm_model <- brms::brm(
    formula = model_formula,
    data    = data_mod,
    family  = gaussian(),
    prior   = prior,
    chains  = n_chains,
    cores   = min(parallel::detectCores(), n_chains),
    iter    = n_iter,
    warmup  = n_warmup,
    control = list(adapt_delta = adapt_delta),
    backend = "cmdstanr",
    threads = if (n_threads > 1) {threading(n_threads)} else {NULL},
    file    = outfile
)

message("Model fit complete. Saved to: ", outfile)
