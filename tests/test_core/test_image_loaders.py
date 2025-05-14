# tests/test_core/test_image_loaders.py

import os
import pytest
import numpy as np
from pathlib import Path

from core.utilities.load_image.loaders.tiffimageloader import TIFFImageLoader
from core.utilities.load_image.loaders.pillowimageloader import PillowImageLoader
from core.utilities.load_image import ImageLoadingService


def create_test_images():
    """Create small test images for testing loaders"""
    from PIL import Image
    import rasterio
    from rasterio.transform import from_origin
    import tempfile
    
    test_files = {}
    
    # Create a small PNG image
    png_data = np.zeros((10, 10, 3), dtype=np.uint8)
    png_data[3:7, 3:7, 0] = 255  # Red square
    png_path = os.path.join(tempfile.gettempdir(), "test_image.png")
    Image.fromarray(png_data).save(png_path)
    test_files['png'] = png_path
    
    # Create a small JPEG image
    jpg_data = np.zeros((10, 10, 3), dtype=np.uint8)
    jpg_data[3:7, 3:7, 1] = 255  # Green square
    jpg_path = os.path.join(tempfile.gettempdir(), "test_image.jpg")
    Image.fromarray(jpg_data).save(jpg_path)
    test_files['jpg'] = jpg_path
    
    # Create a small GeoTIFF
    tif_data = np.zeros((10, 10, 3), dtype=np.uint8)
    tif_data[3:7, 3:7, 2] = 255  # Blue square
    tif_path = os.path.join(tempfile.gettempdir(), "test_image.tif")
    
    try:
        transform = from_origin(0, 0, 1, 1)
        with rasterio.open(
            tif_path, 'w',
            driver='GTiff',
            height=tif_data.shape[0],
            width=tif_data.shape[1],
            count=3,
            dtype=tif_data.dtype,
            transform=transform,
            crs='+proj=latlong',
        ) as dst:
            # Write each band
            for i in range(3):
                dst.write(tif_data[:, :, i], i+1)
    except Exception as e:
        print(f"Error creating test GeoTIFF: {e}")
    
    test_files['tif'] = tif_path
    
    return test_files


@pytest.fixture
def test_images():
    """Fixture to create test images and clean up after tests"""
    files = create_test_images()
    yield files
    
    # Clean up test files
    for file_path in files.values():
        try:
            os.remove(file_path)
        except:
            pass


def test_tiff_loader(test_images):
    """Test loading a TIFF image"""
    if 'tif' not in test_images:
        pytest.skip("GeoTIFF creation failed")
    
    # Load the image
    loader = TIFFImageLoader()
    raster = loader.loadRasterData(test_images['tif'])
    metadata = loader.loadMetadata(raster, test_images['tif'])
    
    # Verify results
    assert raster is not None
    assert raster.shape == (10, 10, 3)
    assert metadata is not None
    assert metadata.width == 10
    assert metadata.height == 10
    assert metadata.bandCount == 3
    
    # Check that the blue square is correctly loaded
    assert raster[5, 5, 2] > 0


def test_pillow_loader(test_images):
    """Test loading common image formats with Pillow"""
    # Load PNG
    png_loader = PillowImageLoader()
    raster = png_loader.loadRasterData(test_images['png'])
    metadata = png_loader.loadMetadata(raster, test_images['png'])
    
    # Verify results
    assert raster is not None
    assert raster.shape == (10, 10, 3)
    assert metadata is not None
    assert metadata.width == 10
    assert metadata.height == 10
    assert metadata.bandCount == 3
    
    # Check that the red square is correctly loaded
    assert raster[5, 5, 0] > 0
    
    # Load JPEG
    jpg_loader = PillowImageLoader()
    raster = jpg_loader.loadRasterData(test_images['jpg'])
    metadata = jpg_loader.loadMetadata(raster, test_images['jpg'])
    
    # Verify results
    assert raster is not None
    assert raster.shape == (10, 10, 3)
    assert metadata is not None
    assert metadata.width == 10
    assert metadata.height == 10
    assert metadata.bandCount == 3
    
    # Check that the green square is correctly loaded
    # Note: JPEG compression may affect exact values, so we check if it's significantly green
    assert raster[5, 5, 1] > raster[5, 5, 0]
    assert raster[5, 5, 1] > raster[5, 5, 2]


def test_image_loading_service(test_images):
    """Test using the ImageLoadingService to load different image types"""
    service = ImageLoadingService()
    
    # Test loader detection
    for ext, path in test_images.items():
        # Get the correct loader for each file type
        try:
            loader = service._getLoader(path)
            assert loader is not None
        except ValueError:
            pytest.fail(f"Could not find loader for {ext} file")