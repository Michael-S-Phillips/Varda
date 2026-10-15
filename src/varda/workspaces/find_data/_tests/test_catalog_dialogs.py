"""The STAC API list is saved in the settings and replaces the defaults; a
catalog's login dialog saves to the keychain."""

import pytest

from varda.catalogs.catalog import Catalog
from varda.catalogs.stac import DEFAULT_APIS, StacApi, StacCatalog
from varda.workspaces.find_data.catalog_dialogs import (
    CredentialsDialog,
    StacApisDialog,
    applySavedStacApis,
)


@pytest.fixture(autouse=True)
def defaultApis():
    StacCatalog.apis = DEFAULT_APIS
    yield
    StacCatalog.apis = DEFAULT_APIS


def test_edited_stac_apis_are_saved_and_applied(qtbot):
    dialog = StacApisDialog()
    qtbot.addWidget(dialog)
    dialog.setApis((StacApi("Mine", "https://stac.example.org/api"),))
    dialog._addRow("", "not a url")  # skipped
    dialog.accept()
    mine = (StacApi("Mine", "https://stac.example.org/api"),)
    assert StacCatalog.apis == mine
    StacCatalog.apis = DEFAULT_APIS
    applySavedStacApis()  # as the next Find Data workspace does
    assert StacCatalog.apis == mine


def test_without_saved_apis_the_defaults_stay():
    applySavedStacApis()
    assert StacCatalog.apis == DEFAULT_APIS


def test_the_login_dialog_saves_the_login(qtbot):
    class Archive(Catalog):
        catalogId = "archive"
        name = "Archive"
        credentialFields = ("username", "password")

    catalog = Archive()
    dialog = CredentialsDialog(catalog)
    qtbot.addWidget(dialog)
    dialog.edits["username"].setText("ada")
    dialog.edits["password"].setText("s3cret")
    assert (
        dialog.edits["password"].echoMode()
        == dialog.edits["password"].EchoMode.Password
    )
    dialog.accept()
    assert catalog.credentials == {"username": "ada", "password": "s3cret"}
