# Utility functions for constructing a PCA-based deprivation index. Allows
# estimation of probabilistic PCA, using pcaMethods package.
# Date created: 19/12/2025

# --- Compute PCA (classical SVD or probabilistic PCA) -------------------------
# Returns a list with augmented data and the pcaMethods::pca object
compute_pca <- function(df, se_indicators, n_pcs,
                        method = c("svd", "ppca"),
                        scale = TRUE, centre = TRUE,
                        seed = 42, 
                        positive_vars = NULL, negative_vars = NULL) {

    # Ensure 'method' is one of "svd", "ppca"
    method <- match.arg(method)

    # Row filtering: ppca allows partially missing data, svd does not
    df_pca <- df %>%
        {
            if (method == "svd") {
                filter(., if_all(se_indicators, ~ !is.na(.))) # all non-NA
            } else {
                filter(., if_any(se_indicators, ~ !is.na(.))) # any non-NA
            }
        }

    # Prepare data matrix (scale + centre)
    X <- df_pca %>%
        select(all_of(se_indicators)) 
    if (centre) {
        X <- X %>% mutate(across(everything(), ~ .x - mean(.x, na.rm = TRUE)))
    }
    if (scale) {
        X <- X %>% mutate(across(everything(), ~ .x / sd(.x, na.rm = TRUE)))
    }
    X <- X %>% as.matrix()

    # Fit PCA
    pca <- if (method == "svd") {
        pcaMethods::svdPca(X, nPcs = n_pcs)
    } else {
        pcaMethods::ppca(X, nPcs = n_pcs, seed = seed)
    }

    # Flip PC1 as necessary so that it represents increasing deprivation
    # (ppca sometimes returns negative of deprivation)
    if (!is.null(positive_vars) && !is.null(negative_vars)) {
        
        loadings_pc1 <- pca@loadings[, 1]

        # Expect stunting & child dep to load positively, GDP, edu, san negative
        if (mean(loadings_pc1[positive_vars]) <
            mean(loadings_pc1[negative_vars])) {

            logging("Flipping PC1 so higher = more deprivation")

            pca@scores[, 1]   <- -pca@scores[, 1]
            pca@loadings[, 1] <- -pca@loadings[, 1]
        }
    }

    # Bind PCA scores back onto data
    df_pca <- bind_cols(
        df_pca,
        as_tibble(pca@scores, .name_repair = ~ paste0("PC", 1:n_pcs))
    )

    list(data = df_pca, pca  = pca)
}


# --- Helper to write out PCA results (loadings + var explained) ---------------
save_pca_res <- function(pca, method, n_pcs, out_dir) {
    # Loadings
    pc_loadings             <- as.data.frame(pca@loadings)
    colnames(pc_loadings)   <- paste0("PC", seq_len(ncol(pc_loadings)))
    pc_loadings             <- rownames_to_column(pc_loadings, "Variable")

    readr::write_csv(
        pc_loadings,
        file.path(out_dir, paste0(method, "_loadings_", n_pcs, ".csv"))
    )

    # Proportion of variance explained
    # Cumulative R2 is available from pcaMethods::pca; derive per-PC R2 from it
    r2_cum      <- as.numeric(pca@R2cum)
    r2          <- diff(c(0, r2_cum))
    pc_names    <- paste0("PC", seq_along(r2))
    var_expl    <- dplyr::bind_rows(                                          
        tibble::as_tibble_row(setNames(r2, pc_names)),
        tibble::as_tibble_row(setNames(r2_cum, pc_names))
    ) %>% 
        mutate(Metric = c("Proportion of Variance", 
                          "Cumulative Proportion")) %>% 
        relocate(Metric)
    
    write_csv(
        var_expl,
        file.path(out_dir, paste0(method, "_var_explained_", n_pcs, ".csv"))
    )
}


# --- Compute PCA, with option to do probabilistic PCA -------------------------
# Computes PCA and returns both PCA object and augmented df
# CHRIS NOTE 25/12: deprecated because the generic `pcaMethods::pca()` function
# doesn't take a random seed
DEPRECATED__compute_pca <- function(df, se_indicators, n_pcs, 
                        # positive_vars, negative_vars,
                        method = "svd", scale = TRUE, centre = TRUE, seed = 42
                        # orient_pc1_flag = TRUE
                        ) {
    
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
        nPcs    = n_pcs,
        seed    = seed
    )

    # if (orient_pc1_flag) {
    #     pca <- orient_pc1(
    #         pca,
    #         positive_vars = positive_vars,
    #         negative_vars = negative_vars,
    #         pc = "PC1"
    #     )
    # }
    
    df_pca <- bind_cols(
        df_pca, 
        as_tibble(pca@scores)   # has colnames PC1, etc.
    )
    
    list(data = df_pca, pca = pca)
}

# --- Orient PC1 so higher values = more deprivation ---------------------------
# Chris note 24/12: with ppca, sometimes PC1 is 'flipped', such that the 
# loadings represent decreasing deprivation, rather than increasing.
# Flips PC1 scores and loadings if reference positive/negative vars load in 
# the wrong direction
DEPRECATED__orient_pc1 <- function(pca,
                       positive_vars,
                       negative_vars,
                       pc = "PC1") {

    L <- pca@loadings[, pc]

    if (!all(c(positive_vars, negative_vars) %in% names(L))) {
        stop("Some variables not found in PCA loadings.")
    }

    # direction_score 'should' be positive
    direction_score <-
        mean(L[positive_vars], na.rm = TRUE) -
        mean(L[negative_vars], na.rm = TRUE)

    if (direction_score < 0) {
        pca@scores[, pc]   <- -pca@scores[, pc]
        pca@loadings[, pc] <- -pca@loadings[, pc]
    }

    pca
}
