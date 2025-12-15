# --- Logging helper -----------------------------------------------------------
logging <- function(...) {
    ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
    message(sprintf("[%s] %s", ts, paste(..., collapse = " ")))
    flush.console()
}

# --- Result directory name helper ---------------------------------------------
results_dirname_builder <- function(project_root, outputs_dir, config_fname) {
    # Create a specific results output directory for each config (each model)
    # > results_dirname_builder(
    #       project_root = root,
    #       outputs_dir = "outputs/deprivation_pm_bhm",
    #       config_fname = "configs/bhm_results_cfg.yaml"
    #   )
    # > "/home/users/cho00/fire-pm-dep/outputs/deprivation_pm_bhm/bhm_results_cfg"  #nolint
    
    file.path(
        project_root,
        outputs_dir,
        sub(".yaml", "", basename(config_fname)) 
    )
}
