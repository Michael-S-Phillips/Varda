"""Decoding bit masks (a pipeline's per-frame exclusions, a QA band): the
number of bits set, one bit, or any of several, band by band."""

import numpy as np
import pytest

from varda.analysis.bit_masks import (
    BitOutput,
    DecodeBitMaskAnalysis,
    anyBits,
    bitPlane,
    parseBits,
    setBitCount,
)
from varda.analysis.registry import ANALYSES
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

MASK = np.array([[[0b101, 0], [0b10, 0b111]]], dtype=np.uint32)  # (1, 2, 2)


def test_bits_are_counted_picked_and_combined():
    np.testing.assert_array_equal(setBitCount(MASK), [[[2, 0], [1, 3]]])
    np.testing.assert_array_equal(bitPlane(MASK, 0), [[[1, 0], [0, 1]]])
    np.testing.assert_array_equal(bitPlane(MASK, 1), [[[0, 0], [1, 1]]])
    np.testing.assert_array_equal(anyBits(MASK, [1, 2]), [[[1, 0], [1, 1]]])


def test_bit_lists_read_like_band_lists():
    assert parseBits("0, 3-5", 32) == [0, 3, 4, 5]
    assert parseBits("", 32) == []
    with pytest.raises(ValueError, match="0 to 7"):
        parseBits("9", 8)


def _mask(nodata=None):
    rng = np.random.default_rng(0)
    frames = rng.random((6, 7, 5, 20)) < 0.15  # 20 frames per value
    mask = (frames * (1 << np.arange(20))).sum(axis=3).astype(np.uint32)
    if nodata is not None:
        mask[0, 0, :] = nodata
    return VardaRaster(ArrayDataSource(mask, nodata=nodata), name="EXCLUDE"), frames


def test_the_analysis_counts_the_excluded_frames_like_a_count_product():
    assert DecodeBitMaskAnalysis in ANALYSES
    image, frames = _mask(nodata=4294967295)
    analysis = DecodeBitMaskAnalysis()
    result = analysis.run(image, lambda *_: None)
    data = result.getData()
    np.testing.assert_array_equal(data[1:, :], frames.sum(axis=3)[1:, :])
    assert np.isnan(data[0, 0]).all()  # no data stays no data
    assert result.bandCount == 5 and "set bits" in result.name


def test_one_bit_or_any_of_several():
    image, frames = _mask()
    analysis = DecodeBitMaskAnalysis()
    analysis.output.set(BitOutput.ONE_BIT)
    analysis.bits.set("19")
    np.testing.assert_array_equal(
        analysis.run(image, lambda *_: None).getData(), frames[..., 19]
    )
    analysis.output.set(BitOutput.ANY_BITS)
    analysis.bits.set("0-1")
    np.testing.assert_array_equal(
        analysis.run(image, lambda *_: None).getData(), frames[..., :2].any(axis=3)
    )


def test_masks_must_be_whole_numbers():
    image = VardaRaster(ArrayDataSource(np.zeros((2, 2, 1), np.float32)), name="f")
    assert "whole-number" in DecodeBitMaskAnalysis().unavailableReason(image)
