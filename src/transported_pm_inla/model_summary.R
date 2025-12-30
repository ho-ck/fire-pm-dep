# Utility functions for wrangling INLA posteriors
# Date created: 12/12/2025

posterior_summary_fixed <- function(model) {
    # Returns data.frame of fixed-effects coef summaries, using broom::tidy 
    # naming convention. "estimate" is the posterior mean effect.
    model$summary.fixed %>% 
        rownames_to_column("term") %>% 
        rename(
            "estimate"  = "mean",
            "conf.low"  = "0.025quant",
            "conf.high" = "0.975quant",
            "median"    = "0.5quant"
        )
}
