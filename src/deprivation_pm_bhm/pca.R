# Utility functions for constructing a PCA-based deprivation index. Allows
# estimation of probabilistic PCA, using pcaMethods package.
# Date created: 19/12/2025

# --- Compute PCA, with option to do probabilistic PCA -------------------------
# Computes PCA and returns both PCA object and augmented df
compute_pca <- function(df, se_indicators, n_pcs, method = "svd",
                        scale = "uv", centre = TRUE) {
    
    # Probabilistic PCA allows partially missing data, classical PCA does not
    if (method == "svd") {
        # Keep rows w/ complete SE indicators (no missings)
        df_pca <- df %>% 
            filter(if_all(se_indicators, ~ !is.na(.)))
    } else if (method == "ppca") {
        # Keep rows w/ at least one non-missing SE indicator
        df_pca <- df %>% 
            filter(if_any(se_indicators, ~ !is.na(.)))
    } else {
        stop("Method must be one of 'ppca', 'svd'.")
    }    

    # Fit (probabilistic) PCA
    pca <- pcaMethods::pca(
        object  = as.matrix(df_pca %>% select(se_indicators)),
        method  = method,   # "ppca" "bpca" "svd"
        scale   = scale,    # "uv" (unit variance)
        center  = centre,
        nPcs    = n_pcs
    )
    
    df_pca <- bind_cols(
        df_pca, 
        as_tibble(pca@scores)   # has colnames PC1, etc.
    )
    
    list(data = df_pca, pca = pca)
}

# --- Helper to write out PCA results (loadings + var explained) ---------------
save_pca_res <- function(pca, method, out_dir) {
    # Loadings
    pc_loadings <- as.data.frame(pca@loadings) %>% 
        rownames_to_column("Variable")
    
    write_csv(pc_loadings, file.path(out_dir, paste0(method, "_loadings.csv")))

    # Proportion of variance explained
    var_expl <- bind_cols(
        as_tibble_col(pca@R2), 
        as_tibble_col(pca@R2cum)
    ) %>% 
        t() %>% 
        as_tibble() %>% 
        `colnames<-`(paste0("PC", 1:5)) %>% 
        mutate(Metric = c(
               "Proportion of Variance", "Cumulative Proportion")) %>% 
        relocate(Metric)
    
    write_csv(
        var_expl,
        file.path(out_dir, paste0(method, "_var_explained.csv"))
    )
}
