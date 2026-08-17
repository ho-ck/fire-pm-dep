# Utility functions for preparing data for the deprivation-PM Bayesian
# hierarchical model
# Date created: 15/12/2025

# --- Helper: prepare data for analysis / post-processing of model -------------
# NOTE 16/12: the annual PM and SE data 'df' has a grid_id column from 
# upstream data downloading/wrangling scripts. This is inconsistent with the 
# grid_id's used in the deprivation-PM BHM, which was fitted to rows with non-NA
# PC1 (i.e., complete socioeconomic data). Thus, re-create the grid_id's of 'df'
# to match the model data, i.e., grid_id's for non-NA PC1.
prepare_analysis_data <- function(df, df_pca, 
    outcome = NA_character_, scale_y = FALSE, scale_PC1 = TRUE, n_pcs = 5) {
    df_pca  <- df_pca %>%   # contains only non-NA PC1 (523,116 rows)
        filter(!is.na(urban_rural)) %>% 
        group_by(lon, lat) %>% 
        mutate(grid_id = cur_group_id()) %>%
        ungroup()

    # Scale PC1 if requested (so that maps etc. will have SDs as units)
    if (scale_PC1) {
        df_pca <- df_pca %>%
            mutate(PC1 = as.numeric(scale(PC1)))
    }
    
    # Join PCs back onto df
    if ("grid_id" %in% names(df)) {
        df <- df |> select(-grid_id)    # remove pre-existing grid IDs, replace with the IDs consistent with the model # nolint
    }
    
    df  <- df %>% 
        left_join(    
            df_pca %>% select(lon, lat, year, grid_id, paste0("PC", 1:n_pcs)),
            by = c("year", "lon", "lat")
        )
    
    # Scale outcome if requested
    if (scale_y) { # Use mean/sd of the model input data (df_pca, w/ non-NA PC1)
        df <- df %>%
            mutate("{outcome}" := 
                (!!sym(outcome) - mean(df_pca[[outcome]], na.rm = TRUE)) /
                    sd(df_pca[[outcome]], na.rm = TRUE)
            )
    }
    
    df  # (523,116 rows with non-NA PC1)
}


# --- Helper: prepare data for model (scale PC1 and centre year) ---------------
prepare_model_data <- function(
    data, outcome, model_formula, scale_PC1 = TRUE, centre_year = TRUE, 
    scale_y = FALSE
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
    
    # Standardise PC1 / centre year / standardise outcome if requested
    if (scale_PC1) {
        data_mod <- data_mod %>%
            mutate(PC1 = as.numeric(scale(PC1)))
    }
    if (centre_year) {
        data_mod <- data_mod %>% 
            mutate(year = year - mean(year, na.rm = TRUE))
    }
    if (scale_y) {
        data_mod <- data_mod %>%
            mutate("{outcome}" := as.numeric(scale(!!sym(outcome))))
    }
    
    data_mod
}


forecast_indicator_lmer <- function(df, var, max_year) {
    # Projects a socioeconomic indicator forward beyond max_year using a
    # mixed-effects model with a linear time trend and grid-level random
    # intercepts and slopes.
    # Only grid cells with observed historical data are projected.
    
    model <- lme4::lmer(
        as.formula(paste(var, "~ year_c + (year_c | grid_id)")),
        data = df |> filter(year <= max_year, !is.na(.data[[var]]))
    )

    observed_grids <- df |>
        filter(year <= max_year, !is.na(.data[[var]])) |>
        distinct(grid_id) |>
        pull(grid_id)

    idx <- which(
        df$year > max_year &
        is.na(df[[var]])   &
        df$grid_id %in% observed_grids
    )

    df[[var]][idx] <- predict(model, newdata = df[idx, ], re.form = NULL)

    df
}


project_indicators <- function(df, projections) {
    # projections: named list of indicator -> max observed year, e.g.:
    #   list(edu_mean_years = 2017, imp_san_access_pct = 2017, ...)
    
    # Centred year needed for lmer trend term
    df <- df |> mutate(year_c = year - mean(year))

    for (var in names(projections)) {
        max_year <- projections[[var]]
        print(paste("Projecting", var, "forward from", max_year))
        df <- forecast_indicator_lmer(df, var, max_year)
    }

    df
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