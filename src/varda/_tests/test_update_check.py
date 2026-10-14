from collections.abc import Iterator

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QMessageBox, QWidget

from varda import update_check
from varda.update_check import (
    UpdateSettings,
    checkForUpdatesLater,
    checkForUpdatesNow,
    showUpdateNotice,
)
from varda.updates import Release

RELEASE = Release("99.0.0", "https://example.org/releases/tag/v99.0.0")


@pytest.fixture
def settings(tmp_path) -> UpdateSettings:
    return UpdateSettings(
        QSettings(str(tmp_path / "varda.ini"), QSettings.Format.IniFormat)
    )


@pytest.fixture
def window(qtbot) -> Iterator[QWidget]:
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    # A notice is its own window: close it so later tests don't see it
    for box in widget.findChildren(QMessageBox):
        box.close()


@pytest.fixture
def opened(monkeypatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr(
        update_check.QDesktopServices,
        "openUrl",
        lambda url: urls.append(url.toString()),
    )
    return urls


def _button(box: QMessageBox, text: str):
    return next(b for b in box.buttons() if b.text() == text)


def _notices(window: QWidget) -> list[QMessageBox]:
    return [box for box in window.findChildren(QMessageBox) if box.isVisible()]


def test_settings_default_to_checking_with_nothing_skipped(settings):
    assert settings.checkAutomatically is True
    assert settings.skippedVersion == ""


def test_download_opens_the_release_page(window, settings, opened):
    box = showUpdateNotice(window, RELEASE, settings)
    _button(box, "Download…").click()
    assert opened == [RELEASE.url]
    assert settings.skippedVersion == ""


def test_skip_remembers_the_version(window, settings, opened):
    box = showUpdateNotice(window, RELEASE, settings)
    _button(box, "Skip This Version").click()
    assert settings.skippedVersion == "99.0.0"
    assert opened == []


def test_the_notice_can_turn_off_the_startup_check(window, settings):
    box = showUpdateNotice(window, RELEASE, settings)
    checkBox = box.checkBox()
    assert checkBox is not None and checkBox.isChecked()
    checkBox.setChecked(False)
    assert settings.checkAutomatically is False


@pytest.fixture
def latest(monkeypatch) -> list[Release | Exception]:
    """What fetchLatestRelease returns (or raises), without going online."""
    answer: list[Release | Exception] = [RELEASE]

    def fetch() -> Release:
        if isinstance(answer[0], Exception):
            raise answer[0]
        return answer[0]

    monkeypatch.setattr(update_check, "fetchLatestRelease", fetch)
    monkeypatch.setattr(update_check, "STARTUP_DELAY_MS", 0)
    return answer


def test_startup_check_shows_a_new_release(qtbot, window, settings, latest):
    checkForUpdatesLater(window, settings)
    qtbot.waitUntil(lambda: len(_notices(window)) == 1)
    assert "99.0.0" in _notices(window)[0].text()


def test_startup_check_stays_quiet_for_a_skipped_release(
    qtbot, window, settings, latest
):
    settings.skippedVersion = "99.0.0"
    checkForUpdatesLater(window, settings)
    qtbot.wait(300)
    assert _notices(window) == []


def test_startup_check_stays_quiet_offline(qtbot, window, settings, latest):
    latest[0] = OSError("no network")
    checkForUpdatesLater(window, settings)
    qtbot.wait(300)
    assert _notices(window) == []


def test_startup_check_can_be_turned_off(qtbot, window, settings, latest, monkeypatch):
    settings.checkAutomatically = False
    started = []
    monkeypatch.setattr(
        update_check, "runInBackground", lambda *a, **k: started.append(a)
    )
    checkForUpdatesLater(window, settings)
    qtbot.wait(100)
    assert started == []


def test_manual_check_shows_a_skipped_release_anyway(qtbot, window, settings, latest):
    settings.skippedVersion = "99.0.0"
    checkForUpdatesNow(window, settings)
    qtbot.waitUntil(lambda: len(_notices(window)) == 1)
    assert "99.0.0" in _notices(window)[0].text()


def test_manual_check_says_when_up_to_date(qtbot, window, settings, latest):
    latest[0] = Release("0.0.1", RELEASE.url)
    checkForUpdatesNow(window, settings)
    qtbot.waitUntil(lambda: len(_notices(window)) == 1)
    assert "latest version" in _notices(window)[0].text()


def test_manual_check_reports_a_failure(qtbot, window, settings, latest):
    latest[0] = OSError("no network")
    checkForUpdatesNow(window, settings)
    qtbot.waitUntil(lambda: len(_notices(window)) == 1)
    assert "couldn't check" in _notices(window)[0].text()
