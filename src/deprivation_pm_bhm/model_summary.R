# Utility functions for model summary and diagnostics etc.
# Date created: 15/12/2025

save_brms_diagnostics <- function(model,
                                  out_dir,
                                  save_trace = TRUE,
                                  save_stan  = TRUE) {
    # Summary
    capture.output(
        summary(model),
        file = file.path(out_dir, "model_summary.txt")
    )

    # Priors
    if (!is.null(model$prior)) {
        readr::write_csv(
        model$prior,
        file = file.path(out_dir, "model_priors.csv")
        )
    }

    # Stan code
    if (save_stan) {
        capture.output(
        stancode(model),
        file = file.path(out_dir, "model.stan")
        )
    }

    # Trace plots
    if (save_trace) {
        trace_plots <- plot(model)
        for (i in seq_along(trace_plots)) {
            ggplot2::ggsave(
                filename = file.path(
                out_dir,
                sprintf("mcmc_trace_%02d.png", i)
                ),
                plot = trace_plots[[i]],
                width = 8,
                height = 6
            )
        }
    }
}
