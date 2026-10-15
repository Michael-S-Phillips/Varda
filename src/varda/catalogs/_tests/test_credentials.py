"""Catalog logins live in the keychain, one entry per catalog and field."""

from varda.catalogs.catalog import Catalog
from varda.catalogs.credentials import (
    KEYRING_SERVICE,
    forgetCredentials,
    isSecret,
    loadCredentials,
    saveCredentials,
)


class Archive(Catalog):
    catalogId = "archive"
    credentialFields = ("username", "password")


def test_a_saved_login_comes_back_for_a_new_catalog(memoryKeyring):
    assert not loadCredentials(Archive())
    saveCredentials(Archive(), {"username": "ada", "password": "s3cret"})
    assert memoryKeyring.passwords[(KEYRING_SERVICE, "archive/password")] == "s3cret"
    catalog = Archive()
    assert loadCredentials(catalog)
    assert catalog.credentials == {"username": "ada", "password": "s3cret"}


def test_forgetting_a_login_clears_it(memoryKeyring):
    catalog = Archive()
    saveCredentials(catalog, {"username": "ada", "password": "s3cret"})
    forgetCredentials(catalog)
    forgetCredentials(catalog)  # nothing left is fine
    assert catalog.credentials == {} and memoryKeyring.passwords == {}
    assert not loadCredentials(Archive())


def test_passwords_and_tokens_are_typed_hidden():
    assert isSecret("password") and isSecret("api_token") and isSecret("API key")
    assert not isSecret("username")
