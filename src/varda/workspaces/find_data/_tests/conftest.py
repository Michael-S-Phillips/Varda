import os

import pytest
from PyQt6.QtCore import QSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolatedSettings(tmp_path):
    """QSettings() writes to a throwaway file, never the user's settings."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path / "settings"),
    )
    yield
    QSettings.setDefaultFormat(QSettings.Format.NativeFormat)
