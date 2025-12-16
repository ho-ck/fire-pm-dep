# Utility functions for post-processing the Bayesian hierarchical model.
# Date created: 15/12/2025

# --- Posterior summary helpers ------------------------------------------------
summarise_posterior <- function(x) {
    tibble::tibble(
        estimate  = mean(x, na.rm = TRUE),
        conf.low  = quantile(x, 0.025, na.rm = TRUE),
        conf.high = quantile(x, 0.975, na.rm = TRUE),
        median    = quantile(x, 0.500, na.rm = TRUE)
    )
}

summarise_draws <- function(
    draws_df,
    group_vars,
    estimands,
    pivot = FALSE,
    pivot_cols = c("rural", "urban"),
    names_to = "urban_rural_cat",
    values_to = "estimate"
) {
    tmp_draws_df <- draws_df
    
    # Pivot U/R longer for marginaleffects style posterior summary slopes in U/R
    if (pivot) {
        tmp_draws_df <- tmp_draws_df %>%
            pivot_longer(
                cols      = all_of(pivot_cols),
                names_to  = names_to,
                values_to = values_to
            )
        estimands <- values_to  # set estimands as the newly pivoted values col(s)  #nolint
    }

    # Group by and summarise
    tmp_draws_df %>%
        group_by(across(all_of(group_vars))) %>%
        summarise(
            across(
                all_of(c(estimands)), ~ summarise_posterior(.x),
                .unpack = ifelse(pivot, "{inner}", "{outer}_{inner}")  
            ),
            .groups = "drop"
        )
}


# --- Extract draws PC1 slopes in urban & rural --------------------------------
# Returns a dataframe with columns:
# .draw | country | term | rural | urban
#   1   |  "Chad" | "PC1"|  -0.5 | -0.1
# Where `rural` is the PC1 slope in rural areas, etc.
# Also includes global pooled U/R effects, with `country` as "Pooled, all countries"    #nolint
extract_pc1_draws_ur <- function(draws) {
    # Fixed effects
    b_PC1         <- draws %>% select(.draw, b_PC1)
    b_PC1_x_urban <- draws %>% select(.draw, `b_PC1:urban_rural_caturban`)

    # Country PC1 random slopes
    r_country_PC1 <- draws %>%
        select(.draw, matches("^r_country\\[.*PC1]")) %>%
            pivot_longer(
            - .draw,
            names_to = "country",
            values_to = "r_country_PC1",
            names_transform = ~ str_replace_all(
                str_remove_all(.x, "r_country\\[|,PC1\\]"),
                "\\.", " "
            )
        )

    # Interaction term
    r_country_PC1_x_urban <- draws %>%
        select(.draw, matches("^r_country\\[.*PC1:urban_rural_caturban]")) %>%
            pivot_longer(
            - .draw,
            names_to = "country",
            values_to = "r_country_PC1_x_urban",
            names_transform = ~ str_replace_all(
                str_remove_all(.x, "r_country\\[|,PC1:urban_rural_caturban\\]"),
                "\\.", " "
            )
        )

    # ---- Global ------------------------------------------------------------
    global_draws <- b_PC1 %>%
        left_join(b_PC1_x_urban, by = ".draw") %>%
        transmute(
            .draw,
            country = "Pooled, all countries",
            term = "PC1",
            rural = b_PC1,
            urban = b_PC1 + `b_PC1:urban_rural_caturban`  # 'base' + interaction
        )

    # ---- Country -----------------------------------------------------------
    country_draws <- r_country_PC1 %>%
        left_join(r_country_PC1_x_urban, by = c("country", ".draw")) %>%
        left_join(b_PC1,         by = ".draw") %>%
        left_join(b_PC1_x_urban, by = ".draw") %>%
        transmute(
            .draw,
            country,
            term = "PC1",
            rural = b_PC1 + r_country_PC1,  # FE + random slope
            urban = b_PC1 + `b_PC1:urban_rural_caturban` +
                    r_country_PC1 + r_country_PC1_x_urban
        )

    bind_rows(global_draws, country_draws) %>%
        mutate(
            country = if_else(
                country == "Congo, Rep  of",
                "Congo, Rep. of",
                country
            )
        )
}


# --- Post-stratification: population-weighted average draws -------------------
# P-W avg of urban and rural PC1 draw estimates
# Returns draws df with columns:
# .draw | country | term | pooled
# Where `pooled` is the P-W avg PC1 slope (post-stratified)
compute_pw_pc1_draws <- function(pc1_draws_ur, df) {
    # --- Global urban % (compute by year, then avg the yearly urban shares) ---
    urban_pct_global <- df %>%
        filter(!is.na(PC1)) %>%
        group_by(urban_rural_cat, year) %>%
        summarise(
            pop_count = sum(pop_count), .groups = "drop"
        ) %>%
        pivot_wider(  # convert to wider -- 1 row per year with U & R pop count cols  # nolint
            id_cols     = c("year"),
            names_from  = urban_rural_cat,
            values_from = pop_count,
            names_glue  = "{.value}_{.name}"
        ) %>%
        mutate(
            urban_share = pop_count_urban / (pop_count_rural + pop_count_urban)
        ) %>%
        replace(is.na(.), 0) %>%
        select(-year) %>%
        summarise(urban_share = mean(urban_share), .groups = "drop") %>%  # mean across years  # nolint
        mutate(country = "Pooled, all countries")

    # --- Get urban % of each country ------------------------------------------
    urban_pct_country <- df %>%
        filter(!is.na(PC1)) %>%
        group_by(country, urban_rural_cat, year) %>%
        summarise(
            pop_count = sum(pop_count), .groups = "drop"
        ) %>%
        pivot_wider(  # convert to wider -- 1 row per country-year with U & R pop count cols  # nolint
            id_cols     = c("country", "year"),
            names_from  = urban_rural_cat,
            values_from = pop_count,
            names_glue  = "{.value}_{.name}"
        ) %>%
        mutate(
            urban_share = pop_count_urban / (pop_count_rural + pop_count_urban)
        ) %>%
        replace(is.na(.), 0) %>%
        select(-year) %>%
        group_by(country) %>%
        summarise(urban_share = mean(urban_share), .groups = "drop")

    # --- Stack the global and country urban %'s -------------------------------
    urban_pct_all <- bind_rows(urban_pct_global, urban_pct_country)

    # --- Join urban % onto U/R draws, compute P-W average of U & R ------------
    pc1_draws_pw_avg <- pc1_draws_ur %>% 
        left_join(urban_pct_all, by = "country") %>% 
        mutate(
            pooled = urban * urban_share + rural * (1 - urban_share)
        ) %>%
        select(.draw, country, term, pooled)

    pc1_draws_pw_avg
}

# --- Extract draws of country-level random intercept and year slope -----------
# Output draws df with columns:
# .draw | country | Intercept | year
extract_country_re_draws <- function(draws) {
    has_country_re  <- any(grepl(
        "^r_country:grid_id\\[.*Intercept]|^r_country:grid_id\\[.*year]", 
        names(draws)
    ))

    # If model doesn't have country-level random Intercept + year slopes, 
    # return NULL (e.g, for non-nested grid RE model)
    if (!has_country_re) {
        return(NULL)
    }

    # ---- Intercepts ----------------------------------------------------------
    intercepts <- draws %>%
        select(.draw, matches("^r_country\\[.*Intercept]")) %>%
        pivot_longer(
            - .draw,
            names_to  = "country",
            values_to = "Intercept",
            names_transform = ~ str_replace_all(
                str_remove_all(.x, "r_country\\[|,Intercept\\]"),
                "\\.", " "
            )
        )

    # ---- Year slopes ---------------------------------------------------------
    year_slopes <- draws %>%
        select(.draw, matches("^r_country\\[.*year]")) %>%
        pivot_longer(
            - .draw,
            names_to  = "country",
            values_to = "year",
            names_transform = ~ str_replace_all(
                str_remove_all(.x, "r_country\\[|,year\\]"),
                "\\.", " "
            )
        )

    # ---- Combine (only what exists) ------------------------------------------
    re_draws <- full_join(
        intercepts,
        year_slopes,
        by = c(".draw", "country")
    ) %>%
        mutate(
            country = if_else(
                country == "Congo, Rep  of",
                "Congo, Rep. of",
                country
            )
        )

    return(re_draws)
}

# --- Extract draws of grid-level random Intercept and year slope -----------
# Output draws df with columns:
# .draw | grid_id | Intercept | year
extract_grid_re_draws <- function(draws) {
    
    has_nested_grid     <- any(grepl("^r_country:grid_id\\[", names(draws)))
    has_non_nested_grid <- any(grepl("^r_grid_id\\[", names(draws)))

    # If model only has country-level REs, return NULL
    if (!has_nested_grid && !has_non_nested_grid) {
        return(NULL)
    }

    if (has_nested_grid) { # Nested grid-level REs: r_country:grid_id[...]

        intercepts <- draws %>%
        select(.draw, matches("^r_country:grid_id\\[.*Intercept]")) %>%
        pivot_longer(
            - .draw,
            names_to = "country_grid",
            values_to = "Intercept",
            names_transform = ~ str_remove_all(
                .x, "r_country:grid_id\\[|,Intercept\\]"
            )
        ) %>%
        tidyr::separate_wider_delim(
            country_grid,
            delim = "_",
            names = c("country", "grid_id")
        )

        year_slopes <- draws %>%
        select(.draw, matches("^r_country:grid_id\\[.*year]")) %>%
        pivot_longer(
            - .draw,
            names_to = "country_grid",
            values_to = "year",
            names_transform = ~ str_remove_all(
                .x, "r_country:grid_id\\[|,year\\]"
            )
        ) %>%
        tidyr::separate_wider_delim(
            country_grid,
            delim = "_",
            names = c("country", "grid_id")
        )

        re_draws <- full_join(
            intercepts,
            year_slopes,
            by = c(".draw", "country", "grid_id")
        )

    } else { # Non-nested grid-level REs: r_grid_id[...]

        intercepts <- draws %>%
        select(.draw, matches("^r_grid_id\\[.*Intercept]")) %>%
        pivot_longer(
            - .draw,
            names_to  = "grid_id",
            values_to = "Intercept",
            names_transform = ~ str_remove_all(
                .x, "r_grid_id\\[|,Intercept\\]"
            )
        )

        year_slopes <- draws %>%
        select(.draw, matches("^r_grid_id\\[.*year]")) %>%
        pivot_longer(
            - .draw,
            names_to  = "grid_id",
            values_to = "year",
            names_transform = ~ str_remove_all(
                .x, "r_grid_id\\[|,year\\]"
            )
        )

        re_draws <- full_join(
            intercepts,
            year_slopes,
            by = c(".draw", "grid_id")
        )
    }

    re_draws %>%
        mutate(grid_id = as.numeric(grid_id))
}
