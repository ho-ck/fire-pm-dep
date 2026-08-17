# Fit INLA model for a cross-validation fold
# - Hold out 2 years of data, fit to rest
# - Write out OOS predictions
# Usage:
#   Rscript pred_fold.R
# Date created: 15/08/2026

library(tidyverse)
library(INLA)

# Setup and paths
root    <- rprojroot::find_root(rprojroot::has_file(".gitignore"))
source(file.path(root, "src/transported_pm_inla/data_prep.R"))

SCRATCH_DIR <- Sys.getenv("SCRATCH_DIR")
DATA_PATH   <- file.path(SCRATCH_DIR, 
                         "data/spatial/fire_pm_dep_paper_data",
                         "transported_GFED_emissions_incl_global_2000_2023")
ADJ_PATH    <- file.path(SCRATCH_DIR, 
                         "data/spatial/transported_pm_inla/afr.adj")
RES_PATH    <- file.path(SCRATCH_DIR, 
                         "data/spatial/transported_pm_inla",
                         "kfold_cv_results")

if (!dir.exists(RES_PATH)) {
    dir.create(RES_PATH, recursive = TRUE)
}

# Params
YEARS_PER_FOLD  <- 3
YEARS_SEL       <- 2000:2023

# Load data
data    <- load_data_and_wrangle(
    filepath    = DATA_PATH,
    years_sel   = YEARS_SEL
)

# Use slurm array ID to select test fold
fold_id     <- as.integer(Sys.getenv("SLURM_ARRAY_TASK_ID"))
all_years   <- sort(unique(data$year))
folds       <- split(all_years, ceiling(seq_along(all_years) / YEARS_PER_FOLD))
test_years  <- folds[[fold_id]]

# Train-test split
train_data <- data |> filter(!year %in% test_years)
test_data  <- data |> filter( year %in% test_years)

# Standardise the predictors (using mean/stdev of train set)
emis_vars  <- grep("^emis.*km$", names(data), value = TRUE)
met_vars   <- c("u10", "v10", "d2m", "t2m", "sp", "tp")
scale_vars <- c(emis_vars, met_vars)

for (v in scale_vars) {
    m               <- mean(train_data[[v]], na.rm = TRUE)
    s               <- sd(train_data[[v]],   na.rm = TRUE)
    train_data[[v]] <- (train_data[[v]] - m) / s
    test_data[[v]]  <- (test_data[[v]]  - m) / s
}

# Combine the data and set test response variable to NA (for INLA to make preds)
fold_data  <- bind_rows(train_data, test_data)
test_index <- which(fold_data$year %in% test_years)
fold_data$fire_PM25_hu[test_index] <- NA

# Define model
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

formula <- fire_PM25_hu ~
    emis_0_20km + emis_20_100km + emis_100_200km + emis_200_350km +
    emis_350_500km + emis_500_750km + emis_750_1000km +
    emis_1000_1500km + emis_1500_2000km +
    u10 + v10 + d2m + t2m + sp + tp +
    f(grid_id, model = "bym2", graph = ADJ_PATH, scale.model = TRUE,
      hyper = hyper_bym2)


# Fit INLA (makes preds for OOS/NA responses)
fit <- inla(
    formula,
    data              = fold_data,
    family            = "gaussian",
    control.family    = hyper_sigma,
    control.predictor = list(compute = TRUE),
    control.compute   = list(dic = FALSE, waic = FALSE),
    verbose           = FALSE
)

# Save OOS preds
tibble(
    year      = test_data$year,
    observed  = test_data$fire_PM25_hu,
    predicted = fit$summary.fitted.values$mean[test_index]
) |> 
    write_csv(file.path(
        RES_PATH,
        paste0("preds_fold_", fold_id, ".csv")
    ))
