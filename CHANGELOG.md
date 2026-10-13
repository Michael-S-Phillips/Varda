# Changelog

Notable changes to Varda. Release notes on GitHub are generated from pull
requests; this file records what users need to know, especially changes that
can alter results.

## Unreleased

### Changed: results may differ from earlier versions

- **Wavelength units are read, not guessed.** Varda now reads each file's
  declared wavelength unit (nm, µm or cm⁻¹) and does every calculation in
  nanometres. Before, several analyses guessed the unit from how big the
  numbers were ("below 10 means µm"). Affected:
  - **Spectral Slope** now works on µm images (it found no bands before) and
    gives the same result as on the nm version of the same image.
  - **Spectral Derivative** is per nm whatever the image's unit; its result
    keeps the source's wavelengths.
  - **Spectral libraries**: a thermal-IR library in µm (e.g. 8-14 µm) is no
    longer read as nm. CSV libraries can name their unit in the wavelength
    column (`wavelength_um`) or a `# units:` comment.
  - A file that declares no unit gets one inferred from its values, with a
    warning in the log.
- **Bad bands are honoured.** Bands marked bad in an ENVI header (`bbl`) are
  ignored by analyses (filled along each spectrum), left out of Spectral Slope
  and of the Spectral Hourglass's Prepare step.
- **Scaled reflectance.** Band Parameters divides by the header's reflectance
  scale factor first, so integer-scaled products (e.g. × 10000) work.
- **Half-pixel alignment.** Map coordinates of analysis results now line up
  with their source image (they were half a pixel off). Drawn ROIs on
  map-referenced images keep their exact corners instead of snapping to pixel
  centres.

### Added

- ENVI export writes `fwhm`, `bbl` and `reflectance scale factor`, and no
  longer writes a `wavelength` list for products that aren't spectra.
- Spectral plots label their x axis with the unit, and library spectra are
  shown in the plotted image's unit.
- The Hourglass endmember export names its wavelength unit, so it loads back
  as a library.

### Fixed

- ENVI files open whatever their data file is called: `.img`, `.dat`, `.raw`,
  `.bin`, `.bsq`/`.bil`/`.bip`, no extension, upper case, or `foo.img.hdr`.
  Opening the data file directly also works when its header sits beside it,
  and an `.img` without a header (e.g. Erdas or PDS) is no longer forced
  through the ENVI reader.
- ENVI headers written with capitalised keys (e.g. `Wavelength Units`) lost
  their wavelengths, units and band metadata.
- Integer ENVI files with a `data ignore value` failed to load.
- The Spectral Hourglass library preview was blank for µm images.
- User plugins in `plugins/user_plugins/` never loaded.
- A session saved by a newer Varda is refused with a clear message.
