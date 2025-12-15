# Utility functions for preparing data for the deprivation-PM Bayesian
# hierarchical model
# Date created: 15/12/2025

# --- Helper: do PCA -----------------------------------------------------------
# Computes PCA and returns both PCA object and augmented df
compute_pca <- function(df, se_indicators) {
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

