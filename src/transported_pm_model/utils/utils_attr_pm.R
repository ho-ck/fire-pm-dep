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

attr_pm_frac_by_band <- function(emis_coef, emis_data) {
    # Uses fitted regression coefficients to estimate attributable fire PM2.5
    # and fractions of fire PM2.5 from each distance band of emissions.
    # Returns dataframe of attributable fraction columns
    
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

    # Return the attributable fraction cols (frac_fire_PM25_emis_0_20km etc.)
    data_aug[, grep(
        "^attr_fire_PM25_emis_|^frac_fire_PM25_emis_",
        names(data_aug), value = TRUE
    )]
}
