"""The catalogs Varda offers: its own, plus those plugins register (the
plugin system's app sink adds and removes them)."""

from __future__ import annotations

from varda.catalogs.catalog import Catalog

# Varda's own catalogs, then plugins' (in the order they load)
catalogRegistry: list[type[Catalog]] = []


def availableCatalogs() -> list[type[Catalog]]:
    return list(catalogRegistry)
