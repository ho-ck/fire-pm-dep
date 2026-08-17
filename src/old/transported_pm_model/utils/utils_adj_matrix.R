# Utility functions for creating the adjacency matrix for Africa
# Date created: 12/12/2025

create_nb_list <- function(data, crs = 4326) {

    # Data must have a geometry col
    if (!"geometry" %in% names(data)) {
        stop("`data` must contain a column named 'geometry'.", call. = FALSE)
    }

    # Try to coerce geometry (char) to sfc
    try_sfc <- try(sf::st_as_sfc(data$geometry), silent = TRUE)

    if (inherits(try_sfc, "try-error")) {
        stop(
            "`geometry` column exists, but cannot be converted to an sf geometry object.\n",    # nolint
            "Check that it contains valid WKT strings, list-columns of coordinates, or sfg objects.",   # nolint
            call. = FALSE
        )
    }

    # Convert to sf
    sf_data <- data %>%
        dplyr::mutate(geometry = !!try_sfc) %>% 
        sf::st_as_sf(crs = crs)

    # Unique locations (grids)
    sf_unique <- sf_data %>%
        dplyr::group_by(grid_id) %>%
        dplyr::slice(1)

    # Create neighbour list
    nb <- spdep::poly2nb(sf_unique, row.names = sf_unique$grid_id, queen = TRUE)

    return(nb)
}
