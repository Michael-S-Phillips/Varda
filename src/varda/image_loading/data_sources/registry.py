"""
DataSource registry: decorator-based registration of DataSource classes.

DataSource implementations use ``@register_data_source(...)`` to register
themselves with a format name and file extensions. The ``ImageLoadingService``
and ``openDataSource()`` factory use the registry to dispatch by file extension
and to generate file dialog filters dynamically.
"""

from __future__ import annotations

import logging

import attrs


logger = logging.getLogger(__name__)


@attrs.frozen
class RegisteredDataSource:
    formatName: str
    fileExtensions: tuple[str, ...]
    dataSourceClass: type


datasource_registry: list[RegisteredDataSource] = []


def register_data_source(formatName: str, fileExtensions: str | list | tuple):
    """Decorator to register a DataSource class for specific file extensions.

    Example::

        @register_data_source("ENVI Image", (".hdr", ".img"))
        class ENVIDataSource(RasterioDataSource):
            ...
    """

    def decorator(cls):
        exts = (
            tuple(fileExtensions)
            if not isinstance(fileExtensions, tuple)
            else fileExtensions
        )
        datasource_registry.append(RegisteredDataSource(formatName, exts, cls))
        return cls

    return decorator


def get_image_type_filter() -> str:
    """Dynamically generate file filters from the DataSource registry."""
    # Start with a catch-all filter (rasterio can open many unregistered formats)
    filters = ["All Supported Images (*)"]

    # Add per-format filters from the registry
    for entry in datasource_registry:
        ext_str = " ".join(f"*{ext}" for ext in entry.fileExtensions)
        filters.append(f"{entry.formatName} ({ext_str})")

    return ";;".join(filters)
