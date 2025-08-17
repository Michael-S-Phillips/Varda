def getRasterFromBand(image: Image, band: Band):
    """Get a subset of the raster data for RGB display.

    Creates a 3-band subset of the raster data based on the RGB channels
    defined in the selected band configuration.

    Returns:
        np.ndarray: Array with shape (height, width, 3) for RGB display
    """

    try:
        # Get the RGB bands from the raster data
        if isinstance(image, Image):
            rgb_data = image.raster[:, :, [band.r, band.g, band.b]]

        # Handle any out-of-range values
        if np.isnan(rgb_data).any():
            logger.warning(
                f"NaN values found in raster data for bands {[band.r, band.g, band.b]}"
            )
            rgb_data = np.nan_to_num(rgb_data)

        return rgb_data
    except IndexError as e:
        logger.error(f"Error extracting RGB bands", exc_info=e)
        # Return a placeholder if there's an error
        if isinstance(image, Image):
            h, w = image.raster.shape[0:2]
        else:
            h, w = image.shape[0:2]

        return np.zeros((h, w, 3))
