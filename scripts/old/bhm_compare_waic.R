# Compare WAIC of Bayesian hierarchical models.
# - Loads fitted brms models and does LOO comparison using WAIC criterion
# - Saves comparison table to CSV
# Usage:
#   Rscript bhm_compare_waic.R 
#       configs/bhm_fit_ppca_15kiter_24threads_cfg.yaml
#       configs/bhm_fit_ppca_15kiter_24threads_no_country_year_slope_cfg.yaml
# Date created: 08/01/2026

# --- Params for subsampled LOO WAIC comparison --------------------------------
N_CORES <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", unset = "1"))
N_OBS   <- 10000 # 1000 # NULL for full sample
N_DRAWS <- 1000


# --- Libraries & helper funcs -------------------------------------------------
suppressPackageStartupMessages({
    library(tidyverse)
    library(brms)
    library(rstan)
    library(cmdstanr)
    library(yaml)
})

root    <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
source(file.path(root, "src/deprivation_pm_bhm/model_setup.R"))
source(file.path(root, "src/utils/utils.R"))    # logging, outdirs etc.

OUT_DIR <- file.path(root, "outputs/deprivation_pm_bhm")

# Helper to load models from cfgs
load_models_from_cfgs <- function(cfg_files) {
    all_models  <- list()
    all_cfgs    <- list()

    for (cfg_file in cfg_files) {
        cfg <- yaml::read_yaml(cfg_file)
        model_file <- build_modelfile(
            out_path    = cfg$project$model_save_dir,
            model_name  = cfg$model$name,
            outcome     = cfg$model$outcome,
            scale_y     = cfg$data$scale_y,
            pca_method  = cfg$pca$method,
            mcmc_cfg    = cfg$mcmc,
            priors_cfg  = cfg$priors
        )
        model <- readRDS(model_file)
        
        all_models[[cfg$model$name]]    <- model
        all_cfgs[[cfg$model$name]]      <- cfg
    }
    
    list(models = all_models, cfgs = all_cfgs)
}

# # Helper to do LOO comparison for a list of models
# loo_compare_list <- function(model_list, ...) {
#     x       <- model_list[[1]]  # first model in list
#     others  <- model_list[-1]   # all models except first
    
#     # Strangely have to provide a list containing the first brmsfit 
#     # then a list of the other brmsfits as a second arg
#     do.call(brms::loo_compare, c(list(x), others, list(...)))
# }

# --- Parse args ---------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
    stop(paste("Usage: Rscript bhm_compare_waic.R <model1_cfg.yaml>",
               "<model2_cfg.yaml> [<model3_cfg.yaml> ...]\n"), call. = FALSE)
}
config_files <- args

logging("Comparing WAIC for configs:")
logging(config_files)

# --- Main ---------------------------------------------------------------------

# Load models & configs
logging("Loading models...")
models_and_cfgs <- load_models_from_cfgs(config_files)
models          <- models_and_cfgs$models
cfgs            <- models_and_cfgs$cfgs

# # Add WAIC criterion
# logging("Adding WAIC criterion...")
# models <- lapply(models, function(m) add_criterion(m, "waic"))

# # Compare WAIC for models
# logging("Doing LOO-WAIC comparison...")
# waic_compare <- loo_compare_list(models, 
#                                  criterion = "waic", 
#                                  model_names = names(models)) %>% 
#                 as.data.frame() %>% 
#                 rownames_to_column("model_name")


# Compare WAIC for models (sub-sampled LOO)
logging("Doing LOO-WAIC comparison...")
waic_results <- lapply(
    models, 
    function(m) {
        set.seed(42)
        brms::loo_subsample(
            m,
            observations    = N_OBS,    # subsample of grid cell-years
            ndraws          = N_DRAWS,  # subsample of draws
            cores           = N_CORES,
            loo_approximation = "waic"
        )
    }
)

waic_compare <- loo_compare(waic_results) %>% 
    as.data.frame() %>% 
    rownames_to_column("model_name")


# Write to CSV
logging("Writing to CSV...")
outfile <- paste(
    "waic_comp",
    paste(names(models), collapse = "_vs_"),
    # models must be fitted to same dataset (outcome, pca method etc) for
    # meaningful WAIC comp. Thus pick arbitrary cfg (e.g. 1st) for naming
    cfgs[[1]]$model$outcome,
    paste0("scaley", cfgs[[1]]$data$scale_y),
    cfgs[[1]]$pca$method,
    "subsample", 
    paste0(N_OBS, "obs"),
    paste0(N_DRAWS, "draws.csv"),
    # "SUBSAMPLE_1000OBS_1000DRAWS", # TMP 08/01/2026 (to update naming...)
    sep = "_"
)
write_csv(waic_compare, file.path(OUT_DIR, outfile))
logging("Done! Written to CSV:", file.path(OUT_DIR, outfile))
