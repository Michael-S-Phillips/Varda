# Sensor spectral responses

Measured relative spectral responses that Varda's **Convolve to Sensor
Bands** uses. Each CSV is a 1 nm grid: `wavelength_nm`, then one column of
relative response (peak 1) per band; its first line says where it comes
from.

| File | Sensor | Source |
|---|---|---|
| `landsat8_oli.csv` | Landsat 8 OLI | NASA/USGS (Ball Aerospace measurements) |
| `landsat9_oli2.csv` | Landsat 9 OLI-2 | NASA/USGS (Ball Aerospace measurements) |
| `sentinel2a_msi.csv`, `sentinel2b_msi.csv`, `sentinel2c_msi.csv` | Sentinel-2A, -2B, -2C MSI | ESA, COPE-GSEG-EOPG-TN-15-0007 |

All five were taken from the pyspectral relative spectral response data,
v1.5.0: Pytroll/pyspectral contributors, "Satellite Sensor Relative
Spectral Response data", Zenodo, doi:10.5281/zenodo.17238136, under the
Creative Commons Attribution 4.0 International license (CC-BY 4.0). They
were resampled to 1 nm and each band normalized to peak 1; Landsat 9's
thermal (TIRS) bands were left out.

CTX, HiRISE and THEMIS VIS are defined in `varda/analysis/sensor_bands.py`
from published numbers: CTX from the measured system passband of Bell et
al. (2013, *Mars* 8, 1-14, Fig. 6; CC-BY), the others from half-maximum
band edges or band centers, as their measured curves aren't published as
tables.
