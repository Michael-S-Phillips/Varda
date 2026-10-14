"""Telling the user about a new Varda release: a check a few seconds after
Varda starts (which they can turn off) and Help → Check for Updates. Updating
itself is a download from the release page."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QSettings, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QCheckBox, QMessageBox, QWidget

from varda.common.ui import openOwnedDialog
from varda.updates import (
    RELEASES_URL,
    Release,
    fetchLatestRelease,
    isNewer,
    shouldNotify,
)
from varda.utilities.background import runInBackground
from varda.version import vardaVersion

logger = logging.getLogger(__name__)

AUTOMATIC_KEY = "updates/checkAutomatically"
SKIPPED_KEY = "updates/skippedVersion"
STARTUP_DELAY_MS = 5000  # once the window is up and settled


class UpdateSettings:
    """Whether Varda checks when it starts, and the version the user skipped."""

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings if settings is not None else QSettings()

    @property
    def checkAutomatically(self) -> bool:
        return bool(self.settings.value(AUTOMATIC_KEY, True, type=bool))

    @checkAutomatically.setter
    def checkAutomatically(self, value: bool) -> None:
        self.settings.setValue(AUTOMATIC_KEY, value)

    @property
    def skippedVersion(self) -> str:
        return str(self.settings.value(SKIPPED_KEY, ""))

    @skippedVersion.setter
    def skippedVersion(self, version: str) -> None:
        self.settings.setValue(SKIPPED_KEY, version)


def _automaticCheckBox(settings: UpdateSettings, parent: QMessageBox) -> QCheckBox:
    # Parented: setCheckBox doesn't keep the Python object alive
    box = QCheckBox("Check for updates when Varda starts", parent)
    box.setChecked(settings.checkAutomatically)
    box.toggled.connect(
        lambda checked: setattr(settings, "checkAutomatically", checked)
    )
    return box


def showUpdateNotice(
    parent: QWidget, release: Release, settings: UpdateSettings
) -> QMessageBox:
    """Varda ``release`` is out: download it, skip it, or decide later."""
    box = QMessageBox(
        QMessageBox.Icon.Information, "Update Available", "", parent=parent
    )
    box.setText(
        f"<b>Varda {release.version} is available.</b> You have {vardaVersion()}."
    )
    box.setInformativeText(
        "Download it from the release page, which also lists what's new."
    )
    download = box.addButton("Download…", QMessageBox.ButtonRole.AcceptRole)
    skip = box.addButton("Skip This Version", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(download)
    box.setCheckBox(_automaticCheckBox(settings, box))

    def clicked(button) -> None:
        if button is download:
            QDesktopServices.openUrl(QUrl(release.url))
        elif button is skip:
            settings.skippedVersion = release.version

    box.buttonClicked.connect(clicked)
    openOwnedDialog(box)
    return box


def _showUpToDate(parent: QWidget, settings: UpdateSettings) -> None:
    box = QMessageBox(
        QMessageBox.Icon.Information, "No Update Available", "", parent=parent
    )
    box.setText(f"<b>Varda {vardaVersion()} is the latest version.</b>")
    box.setCheckBox(_automaticCheckBox(settings, box))
    openOwnedDialog(box)


def _showCheckFailed(parent: QWidget, error: Exception) -> None:
    box = QMessageBox(QMessageBox.Icon.Warning, "Check for Updates", "", parent=parent)
    box.setText("<b>Varda couldn't check for updates.</b>")
    box.setInformativeText(
        "Check your internet connection, or see the latest release on "
        f'<a href="{RELEASES_URL}">GitHub</a>.'
    )
    box.setDetailedText(str(error))
    openOwnedDialog(box)


def checkForUpdatesNow(parent: QWidget, settings: UpdateSettings | None = None) -> None:
    """Help → Check for Updates: always says what it found, even a version
    the user skipped."""
    settings = settings if settings is not None else UpdateSettings()

    def done(release: Release) -> None:
        if isNewer(release.version, vardaVersion()):
            showUpdateNotice(parent, release, settings)
        else:
            _showUpToDate(parent, settings)

    runInBackground(
        fetchLatestRelease,
        done,
        lambda error: _showCheckFailed(parent, error),
        description="Checking for updates",
    )


def _latestOrNone() -> Release | None:
    """The latest release, or None when it can't be found (offline, say),
    which the startup check shouldn't bother anyone about."""
    try:
        return fetchLatestRelease()
    except (OSError, ValueError) as error:
        logger.info("Couldn't check for updates: %s", error)
        return None


def checkForUpdatesLater(
    parent: QWidget, settings: UpdateSettings | None = None
) -> None:
    """The startup check: unless turned off, look a few seconds from now and
    show the notice only for a new version the user hasn't skipped."""
    settings = settings if settings is not None else UpdateSettings()
    if not settings.checkAutomatically:
        return

    def done(release: Release | None) -> None:
        current, skipped = vardaVersion(), settings.skippedVersion
        if release is not None and shouldNotify(release, current, skipped):
            showUpdateNotice(parent, release, settings)

    # A child timer, so it's dropped with the window
    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(STARTUP_DELAY_MS)
    timer.timeout.connect(
        lambda: runInBackground(
            _latestOrNone, done, lambda _error: None, description="Update check"
        )
    )
    timer.start()
