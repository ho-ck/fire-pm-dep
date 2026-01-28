# Some useful plots: forest plots and maps of regression coefficients
# Date created: 25/06/2025
# Chris note 25/06: some of these functions require data in specific format
# w/ specific column names.


# --- Panel figure of forestplot and maps of coefs -----------------------
build_forestplot_map_panel <- function(
    slopes_ur,
    slopes_pw_avg,
    sf_slopes_ur,
    axis_title_x_forestplot = "Change in fire PM₂.₅ (μg m⁻³) per SD increase in deprivation", #nolint
    fill_name_maps          = "Change in fire PM₂.₅ (μg m⁻³) per\nSD increase in deprivation" # nolint
    ) {

    # Forest plot
    forest_data <- slopes_ur %>%
        bind_rows(slopes_pw_avg) %>%
        filter(term == "PC1") %>%
        mutate(
            country = recode(country,
                "eSwatini"                        = "Eswatini",
                "Congo, Democratic Republic of"   = "DR Congo",
                "Egypt, Arab Republic of"         = "Egypt"
            ),
            country = forcats::fct_relevel(country, "Pooled, all countries"),
            urban_rural_cat = recode(urban_rural_cat,
                                    "pooled" = "Pooled",
                                    "rural" = "Rural", "urban" = "Urban"),
            country = forcats::fct_relevel(
                forcats::fct_reorder(country, estimate, .desc = TRUE),
                "Pooled, all countries"
            ),
            facet_group = dplyr::case_when( # create a faceting variable for the two forestplot panels -- one with pooled effects, one with urban and rural # nolint
                urban_rural_cat == "Pooled" ~ "Pooled urban & rural",
                TRUE                        ~ "Stratified urban & rural"
            )
        )

    forestplot_fig <- ggplot(
        data = forest_data,
        mapping = aes(
            x     = estimate,
            y     = fct_rev(country),
            color = urban_rural_cat
        )
    ) +
        facet_wrap(~ facet_group) +
        geom_point(position = position_dodge(width = 0.5)) +
        geom_errorbarh(
            aes(xmin = conf.low, xmax = conf.high),
            height   = 0,
            position = position_dodge(width = 0.5)
        ) +
        scale_color_manual(values = c(
            "Pooled" = "#366A9FFF", # blue-ish (mako)
            "Rural"  = "#018571",   # teal
            "Urban"  = "#a6611a"    # brown
        )) +
        geom_vline(
            xintercept = 0,
            linetype   = "dashed",
            color      = "gray50"
        ) +
        labs(
            x     = axis_title_x_forestplot,
            y     = NULL,
            color = NULL,
            title = NULL
        ) +
        theme_minimal() +
        theme(
            legend.position      = "top",
            legend.box.spacing   = unit(-8, "pt"),
            legend.title         = element_blank(),
            legend.text          = element_text(color = "black", size = 12),
            panel.border         = element_rect(color = "black", fill = NA, linewidth = 1), # nolint
            axis.ticks           = element_line(color = "black"),
            panel.grid.major     = element_blank(),
            panel.grid.minor     = element_blank(),
            axis.title           = element_text(color = "black", size = 12),
            axis.text            = element_text(color = "black", size = 12),
            strip.text           = element_text(color = "black", size = 12),
            plot.title           = element_blank(),
            plot.margin          = margin(0, 0, 0, 0)#30)  # left margin to stop Central African Republic getting clipped  # nolint
        )

    # Map figure (uses `map_country_effects()` helper from plotting_functions.R)
    map_fig <- map_country_effects(
        sf_slopes_ur %>%
            mutate(urban_rural_cat = recode(
                urban_rural_cat, "rural" = "Rural", "urban" = "Urban"
            )),
        variable_name    = "PC1",
        urban_rural_var  = "urban_rural_cat",
        fill_name        = fill_name_maps,
        pattern_name     = NULL,
        facet_ncol       = 1
    ) +
        guides(
            fill    = guide_colorbar(order = 1, barwidth = unit(4, "cm")),
            pattern = guide_legend(order = 2)
        ) +
        theme(
            strip.text       = element_text(size = 14, face = "bold"),
            legend.position  = "bottom",
            legend.key.spacing.x = unit(0.5, "cm"),
            legend.title     = element_text(margin = margin(r = 25), size = 12, vjust = 1.1),   # nolint
            legend.text      = element_text(color = "black", size = 12)
        )

    forestplot_maps_patchwork <- forestplot_fig + map_fig +
        # plot_layout(widths = c(1.8, 1)) +
        plot_layout(widths = c(1.72, 1)) +
        plot_layout(guides = "collect") &
        theme(legend.position  = "bottom",
              legend.spacing.x = unit(1, "cm"))

    # Return the patchwork plot
    return(forestplot_maps_patchwork)
}



map_country_effects <- function(
    plot_data, 
    estimate_colname = "estimate", 
    term_colname = "term", # column containing names of variables
    pattern_values = c("95% CrI includes 0" = "circle"),
    pattern_name = "95% CrI includes 0", # legend name of scale_pattern_manual
    variable_name = "PC1", # variable of interest to map coefs
    urban_rural_var = NULL, # "urban_rural_cat" -- for stratification by U/R
    facet_ncols = 2, # cols for facet_wrap
    conf_low_colname = "conf.low",
    conf_high_colname = "conf.high",
    fill_name = NULL, # legend name of scale_fill_gradient2
    palette_low = "#0072B2",         # Negative association - blue
    palette_mid = "#f9f9f9",         # White (zero)
    palette_high = "#D55E00",        # Positive association - red
    palette_na = "grey45",           # colour for any NA values
    title = NULL

    ) {
    # --- Map of country-specific effects ---
    # Get 95% credibilty
    plot_data_sf <- plot_data %>%
        filter(!!sym(term_colname) == variable_name) %>% 
        mutate(
            credible = as.numeric(
                (!!sym(conf_low_colname) > 0) | (!!sym(conf_high_colname) < 0)
            )
        ) %>% 
        mutate( # convert to char for labels
            credible = case_when(
                credible == 0 ~ "95% CrI includes 0",
                # credible == 1 ~ "95% CrI excludes 0",
                .default = NA_character_
            )
        )

    # Map
    p <- ggplot(plot_data_sf) +
            geom_sf_pattern(
                aes(fill = !!sym(estimate_colname), pattern = credible),
                color = "black", size = 0.1,
                pattern_fill = "black",
                pattern_colour = "black",
                # pattern_density = 0.2,
                pattern_spacing = 0.01,
                pattern_angle = 90,
                pattern_size = 0.04,
            ) +
            scale_pattern_manual(
                values = pattern_values,
                name = pattern_name,
                breaks = c("95% CrI includes 0") # to stop the legend having an empty box for NA (i.e., values which have 95%Cr association)
            ) +
            scale_fill_gradient2(
                low = palette_low,         # Negative association - blue
                mid = palette_mid,         # White (zero)
                high = palette_high,        # Positive association - red
                midpoint = 0,
                na.value = palette_na,
                name = fill_name
            ) +
            labs(title = title) +
            theme_minimal() +
            theme(
                strip.text = element_text(face = "bold"),
                # strip.text.y.left = element_text(angle = 0), # rotate U/R labels to 0°
                panel.grid = element_blank(),
                axis.ticks = element_blank(),
                axis.text = element_blank(),
                # legend.position = "inside",
                # legend.position.inside = c(0.9, 0.32), # horiz, vert
                plot.title = element_text(size = 14, face = "bold", margin = margin(b=15)),
            )

    # Facet wrap by urban/rural
    if (!is.null(urban_rural_var)) {
        p <- p +
            facet_wrap( reformulate(urban_rural_var), ncol = facet_ncols )
    }
    
    return(p)
}


# --- Plot country-level random intercept and year slope -----------------------
plot_country_random_effects <- function(map_sf, nat_bounds) {
    plots <- list()

    # --- Random intercepts -------------------------------------------------
    if ("Intercept_estimate" %in% names(map_sf)) {

        plots$intercept <- plot_map(
            data          = map_sf,
            color         = "Intercept_estimate",
            fill          = "Intercept_estimate",
            name          = "Country-level\nrandom\nintercept",
            palette       = "BrBG",
            direction     = -1,
            nat_bounds_sf = nat_bounds
        )
    }

    # --- Random slopes on year ---------------------------------------------
    if ("year_estimate" %in% names(map_sf)) {

        plots$year <- plot_map(
            data          = map_sf,
            color         = "year_estimate",
            fill          = "year_estimate",
            name          = "Country-level\ntime trend\n(random\nslope)",
            palette       = "BrBG",
            direction     = -1,
            nat_bounds_sf = nat_bounds
        )
    }

    plots
}

# --- Plot grid-level random intercept and year slope --------------------------
plot_grid_random_effects <- function(map_sf, nat_bounds) {
    plots <- list()

    # Grid random intercept
    if ("Intercept_estimate" %in% names(map_sf)) {
        plots$intercept <- plot_map(
        data          = map_sf,
        color         = "Intercept_estimate",
        fill          = "Intercept_estimate",
        name          = "Grid-level\nrandom\nintercept",
        palette       = "BrBG",
        direction     = -1,
        nat_bounds_sf = nat_bounds
        )
    }

    # Grid random slope on year
    if ("year_estimate" %in% names(map_sf)) {
        plots$year <- plot_map(
        data          = map_sf,
        color         = "year_estimate",
        fill          = "year_estimate",
        name          = "Grid-level\ntime trend\n(random\nslope)",
        palette       = "BrBG",
        direction     = -1,
        nat_bounds_sf = nat_bounds
        )
    }

    plots
}


# Plot chloropleth map of a variable
# Note the use of scale_fill_distiller -- doesn't allow setting a midpoint, so (optional) limits must be symmetric
plot_map <- function(
    data,
    color,
    fill,
    name = NULL,
    palette = NULL,
    limits = NULL,
    direction = 1,
    title = NULL,
    subtitle = NULL,
    facet_var = NULL,
    facet_ncol = NULL,
    nat_bounds_sf = NULL,
    # Visual / style parameters
    grid_off = FALSE,
    nat_bounds_color = "black",
    nat_bounds_size = 0.3,
    colorbar_height = 2, # cm
    ticks_color = "white",
    frame_color = "black",
    legend_position = "right",
    legend_title_text_size = 14,
    legend_title_text_face = "bold",
    legend_text_size = 10,
    title_text_size = 14,
    subtitle_text_size = 11,
    axis_text_size = 10,
    strip_text_size = 10,
    strip_text_face = "bold",
    palette_na = "grey40"
) {
    p <- ggplot(data) +
        geom_sf(aes(color = !!sym(color), fill = !!sym(fill))) +
        scale_fill_distiller(
            palette = palette,
            direction = direction,
            name = name,
            limits = limits,
            na.value = palette_na,
            guide = guide_colorbar(
                ticks.colour = ticks_color,
                frame.colour = frame_color
            )
        ) +
        scale_color_distiller(
            palette = palette,
            direction = direction,
            name = name,
            limits = limits,
            na.value = palette_na,
            guide = guide_colorbar(
                ticks.colour = ticks_color,
                frame.colour = frame_color
            )
        ) +
        theme_minimal() +
        theme(
            legend.position = legend_position,
            legend.title = element_text(size = legend_title_text_size, face = legend_title_text_face),
            legend.text = element_text(size = legend_text_size),
            legend.key.height = unit(colorbar_height, "cm"),
            plot.title = element_text(size = title_text_size, face = "bold"),
            axis.text = element_text(size = axis_text_size),
            strip.text = element_text(size = strip_text_size, face = strip_text_face)
        ) +
        labs(title = title, subtitle = subtitle)

    if (!is.null(nat_bounds_sf)) {
        p <- p + geom_sf(
            data = nat_bounds_sf,
            fill = NA,
            color = nat_bounds_color,
            size = nat_bounds_size
        )
    }

    if (!is.null(facet_var)) {
        p <- p + facet_wrap(reformulate(facet_var), ncol = facet_ncol, drop = FALSE)
    }

    if (grid_off) {
        p <- p + theme(
            panel.grid.major = element_blank(),
            panel.grid.minor = element_blank(),
            axis.text = element_blank(),
        )
    }

    return(p)
}