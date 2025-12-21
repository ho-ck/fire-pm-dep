# Utility functions for defining the deprivation-PM Bayesian hierarchical model
# Date created: 15/12/2025


# --- Helper: define priors ----------------------------------------------------
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


# --- Helper: file name builder ------------------------------------------------
build_modelfile <- function(out_path, outcome, model_name, pca_method,
                            mcmc_cfg, priors_cfg) {
    file.path(
        out_path,
        paste0(
            model_name, "_",
            outcome, "_",
            pca_method, "PcaMethod_",
            mcmc_cfg$chains, "chains_",
            mcmc_cfg$iter, "iter_",
            mcmc_cfg$warmup, "warmup_",
            mcmc_cfg$threads, "threads_",
            "normal", priors_cfg$beta_sd, "_betaPrior_",
            priors_cfg$scale_dist, "_scalePrior.rds"
        )
    )
}
