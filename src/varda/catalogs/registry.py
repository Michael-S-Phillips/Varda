"""The catalogs Varda offers: its own, plus those plugins register (the
plugin system's app sink adds and removes them)."""

from __future__ import annotations

from varda.catalogs.catalog import Catalog
from varda.catalogs.footprints import FootprintFileCatalog
from varda.catalogs.ode import OdeCatalog
from varda.catalogs.stac import StacCatalog

# Varda's own catalogs, then plugins' (in the order they load)
catalogRegistry: list[type[Catalog]] = [StacCatalog, OdeCatalog, FootprintFileCatalog]


def availableCatalogs() -> list[type[Catalog]]:
    return list(catalogRegistry)
