# Utility functions for fitting the deprivation-PM Bayesian hierarchical model
# Date created: 11/12/2025

# --- Helper: do PCA -----------------------------------------------------
# Computes PCA and returns both PCA object and augmented df
compute_pca <- function(df, se_indicators, scale = TRUE, center = TRUE) {
    df_clean <- df[complete.cases(df[, se_indicators]), ]
    
    pca <- stats::prcomp(
        formula = as.formula(
            paste("~", paste(se_indicators, collapse = " + "))
        ),
        data   = df_clean,
        scale  = TRUE,
        center = TRUE,
        retx   = TRUE
    )
    
    df_aug <- bind_cols(df_clean, as.data.frame(pca$x))
    
    list(data = df_aug, pca = pca)
}

# --- Helper: prepare data for model (scale PC1 and centre year) ---------
prepare_model_data <- function(data, model_formula, cfg_data = list()) {
    data <- data %>%
        mutate(urban_rural_cat = as.factor(urban_rural)) %>% 
        group_by(lon, lat) %>% 
        mutate(grid_id = cur_group_id()) %>%   # Grid IDs
        ungroup()
    
    # select only variables needed for model
    vars_needed <- setdiff(all.vars(model_formula), "Intercept")
    data_mod <- data %>% select(all_of(vars_needed))
    
    # Standardise PC1 / centre year if requested
    if (isTRUE(cfg_data$scale_PC1)) {
        data_mod <- data_mod %>%
            mutate(PC1 = scale(PC1))
    }
    if (isTRUE(cfg_data$centre_year)) {
        data_mod <- data_mod %>% 
            mutate(year = year - mean(year, na.rm = TRUE))
    }
    
    data_mod
}


# --- Helper: define priors ----------------------------------------------
build_priors <- function(beta_sd, scale_type) {
    base <- c(
        set_prior(paste0("normal(0, ", beta_sd, ")"), class = "b")
    )

    scale_priors <- switch(
        scale_type,
        "normal" = c(
            prior(normal(0, 1), class = "sd"),
            prior(normal(0, 1), class = "sigma")
        ),
        "student_t" = c(
            prior(student_t(4, 0, 1), class = "sd"),
            prior(student_t(4, 0, 1), class = "sigma")
        ),
        "cauchy" = c(
            prior(cauchy(0, 1), class = "sd"),
            prior(cauchy(0, 1), class = "sigma")
        ),
        stop("Invalid scale_type; must be 'cauchy', 'normal', or 'student_t'.")
    )
    
    c(base, scale_priors)
}


# --- Helper: file name builder ------------------------------------------
build_modelfile <- function(out_path, outcome, model_name, 
                            mcmc_cfg, priors_cfg) {
    file.path(
        out_path,
        paste0(
        model_name, "_",
        outcome, "_",
        mcmc_cfg$chains, "chains_",
        mcmc_cfg$iter, "iter_",
        mcmc_cfg$warmup, "warmup_",
        mcmc_cfg$threads, "threads_",
        "normal", priors_cfg$beta_sd, "_betaPrior_",
        priors_cfg$scale_dist, "_scalePrior.rds"
        )
    )
}
