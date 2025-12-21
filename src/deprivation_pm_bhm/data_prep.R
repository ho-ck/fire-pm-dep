# Utility functions for preparing data for the deprivation-PM Bayesian
# hierarchical model
# Date created: 15/12/2025

# --- Helper: prepare data for analysis / post-processing of model -------------
# NOTE 16/12: the annual PM and SE data 'df' has a grid_id column from 
# upstream data downloading/wrangling scripts. This is inconsistent with the 
# grid_id's used in the deprivation-PM BHM, which was fitted to rows with non-NA
# PC1 (i.e., complete socioeconomic data). Thus, re-create the grid_id's of 'df'
# to match the model data, i.e., grid_id's for non-NA PC1.
prepare_analysis_data <- function(df, df_pca) {
    df_pca  <- df_pca %>%   # contains only non-NA PC1 (523,116 rows)
        group_by(lon, lat) %>% 
        mutate(grid_id = cur_group_id()) %>%
        ungroup()

    # Join PCs back onto df
    df  <- df %>% 
        select(-grid_id) %>%    # remove pre-existing grid IDs, replace with the IDs consistent with the model # nolint
        left_join(    
            df_pca %>% select(lon, lat, year, grid_id, paste0("PC", 1:5)),
            by = c("year", "lon", "lat")
        )
    df  # 828600 rows (523,116 with non-NA PC1)
}


# --- Helper: prepare data for model (scale PC1 and centre year) ---------
prepare_model_data <- function(
    data, model_formula, scale_PC1 = TRUE, centre_year = TRUE
    ) {
    data <- data %>%
        filter(!is.na(urban_rural)) %>% 
        mutate(urban_rural_cat = as.factor(urban_rural)) %>% 
        group_by(lon, lat) %>% 
        mutate(grid_id = cur_group_id()) %>%   # Grid IDs
        ungroup()
    
    # select only variables needed for model
    vars_needed <- setdiff(all.vars(model_formula), "Intercept")
    data_mod <- data %>% select(all_of(vars_needed))
    
    # Standardise PC1 / centre year if requested
    if (scale_PC1) {
        data_mod <- data_mod %>%
            mutate(PC1 = as.numeric(scale(PC1)))
    }
    if (centre_year) {
        data_mod <- data_mod %>% 
            mutate(year = year - mean(year, na.rm = TRUE))
    }
    
    data_mod
}


# --- Helper: do PCA -----------------------------------------------------------
# Computes PCA and returns both PCA object and augmented df
DEPRECEATED__compute_pca <- function(df, se_indicators) {
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

