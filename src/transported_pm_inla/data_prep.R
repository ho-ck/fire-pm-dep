# Utility functions for loading data for the emissions-smoke BYM2 INLA  model
# Date created: 11/12/2025


load_data_and_wrangle <- function(filepath, years_sel = 2000:2017) {
    # --- Load PM & emissions CSV files -------------------------------------
    csv_dir <- file.path(filepath)

    csv_files <- list.files(csv_dir, full.names = TRUE, pattern = "\\.csv$")

    # Extract year
    years <- as.numeric(sub(".*_(\\d{4})\\.csv$", "\\1", csv_files))
    csv_files <- csv_files[ years %in% years_sel ]

    if (length(csv_files) == 0) {
        stop("No CSV files found for years 2000-2017", call. = FALSE)
    }

    # --- Read data ----------------------------------------------------------
    data <- purrr::map_dfr(csv_files, readr::read_csv) %>% as_tibble()

    # --- Create grid IDs ----------------------------------------------------
    data <- data %>%
        group_by(lon, lat) %>%
        mutate(grid_id = cur_group_id()) %>%
        ungroup()

    # --- Rename Middle Africa and make factor ------------------------------
    data <- data %>%
        mutate(
            month  = as.factor(month),
            region = recode(region, "Middle Africa" = "Central Africa"),
            region = factor(region, levels = c(
                "Northern Africa", "Western Africa", "Central Africa",
                "Eastern Africa", "Southern Africa"
            ))
        )
    
    # Also need to update source region emissions colnames
    colnames(data) <- gsub("Middle Africa", "Central Africa", colnames(data))

    # --- Emissions wrangling ------------------------------------------------
    data <- data %>%
        mutate(
            emis_0_20km   = gfed_PM25_mass_emis,            # local grid cell emissions  # nolint
            # emis_20_100km = emis_14_50km + emis_50_100km    # combine 20-50 and 50-100km bands (renaming the '14km' to '20km', as 20km is approx the hypotenuse of the 0.25° grid cell. note that I had originally named them '14km' in the GFED emissions data processing script, corresponding to half the width of a 0.25° grid cell) # nolint
            emis_20_100km = emis_20_50km + emis_50_100km    # combine 20-50 and 50-100km bands  #nolint
        ) %>%
        rename(
            # "__emis_14_50km"  = emis_14_50km,               # bit hacky: rename unused emissions cols so they don't interfere w/ regex matching later  # nolint
            "__emis_20_50km"  = emis_20_50km,               # bit hacky: rename unused emissions cols so they don't interfere w/ regex matching later  # nolint
            "__emis_50_100km" = emis_50_100km
        )

    # Same wrangling for the source region emissions cols
    for (r in unique(data$region)) {
        data[[paste0("emis_20_100km_", r)]] <-
            # data[[paste0("emis_14_50km_", r)]] +
            data[[paste0("emis_20_50km_", r)]] +
            data[[paste0("emis_50_100km_", r)]]

        data <- data %>%
            rename(
                # !!paste0("__emis_14_50km_", r)  := paste0("emis_14_50km_", r),
                !!paste0("__emis_20_50km_", r)  := paste0("emis_20_50km_", r),
                !!paste0("__emis_50_100km_", r) := paste0("emis_50_100km_", r)
            )
    }

    # Convert to thousand tonnes
    data <- data %>%
        mutate(across(starts_with("emis"), ~ .x * 1e-9))

    data
}


# --- Logging helper -----------------------------------------------------
logging <- function(...) {
    ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
    message(sprintf("[%s] %s", ts, paste(..., collapse = " ")))
    flush.console()
}
