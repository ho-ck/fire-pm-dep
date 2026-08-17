# Utility functions for getting attributable PM2.5 from band-specific emissions
# Date created: 12/12/2025


get_transformed_emis_coefs <- function(model, emis_data) {
    # Returns a data.frame of regression coefs on band-specific emissions terms,
    # transformed into the original units of the emissions data (bc data were
    # scaled prior to INLA)

    # Get model coefs and CrIs
    coefs <- posterior_summary_fixed(model)

    # Filter for emissions terms
    emis_coef <- coefs %>% 
        filter( grepl("^emis", term) ) 
        
    # Back-transform emissions betas (because predictors were standardised)
    emis_coef <- emis_coef %>% 
        rowwise() %>% 
        mutate(
            # SD of the corresponding original predictor
            sd_orig = sd(emis_data[[term]], na.rm = TRUE),
            
            # Back-transform the estimate and CIs (divide by sd)
            estimate = estimate / sd_orig,
            conf.low = conf.low / sd_orig,
            conf.high = conf.high / sd_orig
        ) %>% 
        ungroup() %>% 
        select(-sd_orig) # drop the helper column
    
    emis_coef
}

attr_pm_frac_by_band <- function(emis_coef, emis_data, outcome = "fire_PM25") {
    # Use fitted regression coefficients to estimate:
    # - 1. Attributable fire PM2.5 for each band (coef_band * Emis_band)
    # - 2. Attributable fractions of fire PM2.5 from each emissions band
    # - 3. Bias-corrected attr. fire PM2.5 (attr. frac * Xu estim. fire PM2.5)
    # Returns dataframe of the above 3 columns.
    # Motivation for the 'bias-correction' is that scaled Xu estimates likely
    # better reflect true fire PM2.5 exposure. And AFs are the mechanical 
    # attribution from the statistical model.    
    
    data_aug <- emis_data   # copy the data to augment

    # Loop through emissions bands, get attr PM2.5 for emissions from each band
    for ( var in emis_coef$term ) {
        # Name format e.g. `attr_fire_PM25_emis_0_20km`
        data_aug[[ paste0("attr_fire_PM25_", var) ]] <- 
            data_aug[[var]] * 
            emis_coef[emis_coef$term == var,]$estimate # posterior mean estimate
    }

    # Sum of all bands' attributable PM2.5 (for calculating fractions)
    data_aug[["total_attr_fire_PM25"]] <- rowSums(
        data_aug[, grep("^attr_fire_PM25_emis_", names(data_aug), value = TRUE)]
    )

    # Loop through emissions bands, get fraction of PM2.5 from band
    for ( var in emis_coef$term ) {
        data_aug[[ paste0("frac_fire_PM25_", var) ]] <- 
            data_aug[[ paste0("attr_fire_PM25_", var) ]] / 
            data_aug[["total_attr_fire_PM25"]]
    }

    # Loop through emissiosn bands, get bias-corrected fire PM2.5 (scale Xu 
    # estimates by band attributable fractions)
    for ( var in emis_coef$term ) {
        data_aug[[ paste0("bc_attr_fire_PM25_", var) ]] <- 
            data_aug[[ paste0("frac_fire_PM25_", var) ]] * data_aug[[outcome]]
    }

    # Return the attributable PM/frac/bc-PM cols
    data_aug[, grep(
        "^attr_fire_PM25_emis_|^frac_fire_PM25_emis_|^bc_attr_fire_PM25_emis_",
        names(data_aug), value = TRUE
    )]
}
