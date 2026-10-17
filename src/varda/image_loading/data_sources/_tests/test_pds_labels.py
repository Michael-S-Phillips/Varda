"""PDS products open through their labels: the data file beside a detached
label has no header of its own, so only the label says what it holds."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from varda.image_loading.data_sources.pds_data_source import PdsLabelDataSource
from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource
from varda.image_loading.data_sources.registry import get_image_type_filter
from varda.image_loading.image_loading_service import openDataSource
from varda.workspaces.find_data.downloads_panel import openableFiles


@pytest.fixture
def pds4(tmp_path: Path) -> Path:
    """A PDS4 product as archives ship it: an XML label and a raw data file."""
    label = tmp_path / "obs.xml"
    with rasterio.open(
        label,
        "w",
        driver="PDS4",
        width=5,
        height=4,
        count=1,
        dtype="float32",
        transform=Affine(1, 0, 0, 0, -1, 4),
    ) as dst:
        dst.write(np.arange(20, dtype="float32").reshape(1, 4, 5))
    return label


def test_a_pds4_label_opens(pds4: Path):
    source = openDataSource(str(pds4))
    assert isinstance(source, PdsLabelDataSource)
    assert (source.height, source.width, source.bandCount) == (4, 5, 1)


def test_the_label_is_opened_after_a_download_not_the_raw_data(pds4: Path):
    files = sorted(pds4.parent.iterdir())  # obs.img (raw) and obs.xml
    assert openableFiles(files) == [pds4]


def test_other_xml_files_are_not_images(tmp_path: Path):
    plain = tmp_path / "notes.xml"
    plain.write_text("<notes><note>not a label</note></notes>")
    aux = tmp_path / "scene.tif.aux.xml"
    aux.write_text("<PAMDataset></PAMDataset>")
    assert not PdsLabelDataSource.canOpen(str(plain))
    assert not PdsLabelDataSource.canOpen(str(aux))
    assert openableFiles([plain, aux]) == []


def test_the_open_dialog_lists_pds_labels():
    assert "*.xml" in get_image_type_filter()
    assert "*.lbl" in get_image_type_filter()


def test_a_source_that_failed_to_open_is_collected_quietly():
    # __init__ raised before the reader lock existed; __del__ must not raise
    source = RasterioDataSource.__new__(RasterioDataSource)
    source.__del__()


MISSING = -3.40282265508890445e38
HIGH_REPR = -3.4028234663852886e38  # ISIS's HRS: CaSSIS's off-image fill
LOW_INSTR = -3.40282306073709653e38


def test_every_special_constant_is_no_data(tmp_path: Path):
    """GDAL treats only the missing constant as no-data; the saturation
    constants (CaSSIS fills the area off the image with one) and values
    beyond the valid range aren't measurements either."""
    label = tmp_path / "obs.xml"
    pixels = np.array(
        [[0.02, HIGH_REPR, LOW_INSTR, MISSING, 0.05, 2.0]], dtype="float32"
    )
    with rasterio.open(
        label,
        "w",
        driver="PDS4",
        width=6,
        height=1,
        count=1,
        dtype="float32",
        nodata=MISSING,
        transform=Affine(1, 0, 0, 0, -1, 1),
    ) as dst:
        dst.write(pixels[np.newaxis])
    text = label.read_text()
    text = text.replace(
        "</missing_constant>",
        "</missing_constant>\n"
        "        <valid_maximum>1.0</valid_maximum>\n"
        f"        <high_representation_saturation>{HIGH_REPR!r}"
        "</high_representation_saturation>\n"
        f"        <low_instrument_saturation>{LOW_INSTR!r}"
        "</low_instrument_saturation>",
    )
    label.write_text(text)

    values = openDataSource(str(label)).readAllBands()[0, :, 0]
    assert np.isnan(values[1:4]).all()  # the three special constants
    assert np.isnan(values[5])  # above valid_maximum
    np.testing.assert_allclose(values[[0, 4]], [0.02, 0.05])
