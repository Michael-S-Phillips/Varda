"""Catalog logins, kept only in the operating system's keychain (``keyring``):
asked for once, then set on the catalog as ``credentials``."""

from __future__ import annotations

from collections.abc import Mapping

import keyring
import keyring.errors

from varda.catalogs.catalog import Catalog, CatalogError

KEYRING_SERVICE = "Varda catalogs"


def _account(catalog: Catalog, field: str) -> str:
    return f"{catalog.catalogId}/{field}"


def loadCredentials(catalog: Catalog) -> bool:
    """Fill the catalog's credentials from the keychain; whether every field
    it needs has a value."""
    try:
        for field in catalog.credentialFields:
            value = keyring.get_password(KEYRING_SERVICE, _account(catalog, field))
            if value:
                catalog.credentials[field] = value
    except keyring.errors.KeyringError as error:
        raise CatalogError(f"Varda couldn't read the keychain: {error}") from error
    return hasCredentials(catalog)


def hasCredentials(catalog: Catalog) -> bool:
    return all(catalog.credentials.get(field) for field in catalog.credentialFields)


def saveCredentials(catalog: Catalog, values: Mapping[str, str]) -> None:
    try:
        for field in catalog.credentialFields:
            keyring.set_password(
                KEYRING_SERVICE, _account(catalog, field), values.get(field, "")
            )
    except keyring.errors.KeyringError as error:
        raise CatalogError(f"Varda couldn't save the login: {error}") from error
    catalog.credentials.update(values)


def forgetCredentials(catalog: Catalog) -> None:
    for field in catalog.credentialFields:
        try:
            keyring.delete_password(KEYRING_SERVICE, _account(catalog, field))
        except keyring.errors.PasswordDeleteError:
            pass  # there was none
        except keyring.errors.KeyringError as error:
            raise CatalogError(f"Varda couldn't remove the login: {error}") from error
    catalog.credentials.clear()


def isSecret(field: str) -> bool:
    """Whether a login field is typed hidden (a password, token or key)."""
    return any(word in field.lower() for word in ("password", "token", "key", "secret"))
