# Generic script to fir deprivation-PM2.5 Bayesian hierarchical models
# - Load data & do PCA to construct deprivation index
# - Estimate model as specified in config file and save to RDS file
# Usage:
#   Rscript fit_bhm.R configs/fit_bhm_cfg.yaml <model_index>
# Date created: 19/12/2025

# --- Setup & libraries --------------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(brms)
    library(rstan)
    library(cmdstanr)
    library(yaml)
})

# --- Source helper functions --------------------------------------------------
root    <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
source(file.path(root, "src/deprivation_pm_bhm/data_prep.R"))
source(file.path(root, "src/deprivation_pm_bhm/pca.R"))
source(file.path(root, "src/deprivation_pm_bhm/model_setup.R"))
source(file.path(root, "src/deprivation_pm_bhm/model_summary.R"))
source(file.path(root, "src/utils/utils.R"))    # logging, outdirs etc.

# --- Parse args ---------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
    stop("Usage: Rscript bhm_results.R <config.yml>",
         call. = FALSE)
}
config_file  <- args[1]

# --- Load model config & set Stan environment ---------------------------------
cfg             <- yaml::read_yaml(file.path(root, config_file))
data_filepath   <- cfg$project$data_filepath
model_save_dir  <- cfg$project$model_save_dir
if (!dir.exists(model_save_dir)) {
    dir.create(model_save_dir, recursive = TRUE)
}
set_cmdstan_path(cfg$environment$cmdstan_path)

# Build model formula from config
model_formula   <- as.formula(paste(
    cfg$model$outcome, "~", cfg$model$formula_rhs
))

logging("Running model:", cfg$model$name, "(", cfg$model$description, ").",
        "\nOutcome:", cfg$model$outcome, "\nPCA method:", cfg$pca$method)

# --- MCMC settings ------------------------------------------------------------
n_chains    <- cfg$mcmc$chains
n_iter      <- cfg$mcmc$iter
n_warmup    <- cfg$mcmc$warmup
n_threads   <- cfg$mcmc$threads
adapt_delta <- cfg$mcmc$adapt_delta

beta_prior_sd    <- cfg$priors$beta_sd
scale_prior_dist <- cfg$priors$scale_dist

# --- Load data ----------------------------------------------------------------
logging("Loading data...")
df <- readr::read_csv(data_filepath)

# --- Do PCA -------------------------------------------------------------------
logging("Computing PCA...")
pca_res <- compute_pca(
    df,
    method          = cfg$pca$method,
    se_indicators   = cfg$data$se_indicators,
    n_pcs           = cfg$pca$n_pcs,
    scale           = cfg$pca$scale,
    centre          = cfg$pca$centre
)

# Augmented df with PCs (523,116 rows for svd / 807012 rows for ppca)
df_aug <- pca_res$data

# Save PCA loadings & variance explained
save_pca_res( pca_res$pca, cfg$pca$method, cfg$project$model_save_dir )

# --- Prepare data for model ---------------------------------------------------
data_mod <- prepare_model_data(df_aug, 
                               model_formula, 
                               scale_PC1    = cfg$data$scale_PC1,
                               centre_year  = cfg$data$centre_year
                               )

# --- Priors --------------------------------------------------------------
prior   <- build_priors(beta_prior_sd, scale_prior_dist)

# --- Fit model -----------------------------------------------------------
logging("Fitting model...")

outfile <- build_modelfile(
    out_path    = model_save_dir,
    model_name  = cfg$model$name,
    pca_method  = cfg$pca$method,
    outcome     = cfg$model$outcome,
    mcmc_cfg    = cfg$mcmc,
    priors_cfg  = cfg$priors
)

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
