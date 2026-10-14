"""Plugins → Kindle a Feature: describe a feature, watch your AI build it as a
plugin, review it (summary, where it appears, the checks, warnings and the
code), then Enable, Ask for Changes, or Discard."""

from __future__ import annotations

import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from varda.branding.loader import RedrawSpinner
from varda.common.entities import VardaRaster
from varda.common.ui import MutedLabel
from varda.kindling.agent import Kindler, Outcome
from varda.kindling.ai_settings import AISettings
from varda.kindling.checks import runChecks, scanForWarnings
from varda.kindling.providers import ProviderError
from varda.kindling.tools import KindlingTools, PluginFolder
from varda.plugins.plugin_manager import VardaPluginManager, defaultPluginsFolder
from varda.plugins.plugins_dialog import installPlugin
from varda.utilities.background import onMainThread, runInBackground

PLACEHOLDER = (
    "Describe the feature, e.g. “A band depth map at 1.9 µm, against a "
    "straight-line continuum between 1.8 and 2.1 µm.”"
)
PRIVACY_NOTE = (
    "Sent to Anthropic: your description, Varda's plugin docs, and the image's "
    "size, wavelengths and no-data value. Never its pixels: the checks that run "
    "the plugin on a crop of the image stay on this computer."
)
AI_NOTE = (
    "This plugin was written by an AI. Read the summary and any warnings before "
    "enabling it: once enabled, it runs inside Varda like any installed plugin."
)


def draftsFolder() -> Path:
    """Where plugins are built before they're enabled (beside ``plugins``)."""
    return defaultPluginsFolder().parent / "kindling"


def _monospace(text: str = "") -> QPlainTextEdit:
    box = QPlainTextEdit(text)
    box.setReadOnly(True)
    box.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    return box


class KindleDialog(QDialog):
    def __init__(
        self,
        manager: VardaPluginManager,
        images: list[VardaRaster],
        settings: AISettings | None = None,
        parent: QWidget | None = None,
        folder: Path | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Kindle a Feature")
        self.resize(820, 640)
        self.manager = manager
        self.images = images
        self.settings = settings if settings is not None else AISettings()
        self.folder = folder or draftsFolder() / datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )
        self.kindler: Kindler | None = None
        self.tools: KindlingTools | None = None
        self.building = False
        self.closeWhenDone = False

        self.pages = QStackedWidget()
        self.pages.addWidget(self._describePage())
        self.pages.addWidget(self._buildPage())
        self.pages.addWidget(self._reviewPage())
        layout = QVBoxLayout(self)
        layout.addWidget(self.pages)

    # --- pages ---------------------------------------------------------------

    def _describePage(self) -> QWidget:
        page = QWidget()
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(PLACEHOLDER)
        self.imageChoice = QComboBox()
        for image in self.images:
            self.imageChoice.addItem(image.name, image)
        self.imageChoice.addItem("No image (assume 400-2500 nm)", None)
        form = QFormLayout()
        form.addRow("Build it for:", self.imageChoice)
        note = MutedLabel(PRIVACY_NOTE)
        note.setWordWrap(True)
        self.startButton = QPushButton("Kindle")
        self.startButton.setDefault(True)
        self.startButton.clicked.connect(self._start)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.startButton)
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<b>What should Varda be able to do?</b>"))
        layout.addWidget(self.description, 1)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(buttons)
        return page

    def _buildPage(self) -> QWidget:
        page = QWidget()
        self.spinner = RedrawSpinner(40)
        self.buildStatus = QLabel("Starting…")
        self.tokensLabel = MutedLabel("")
        header = QHBoxLayout()
        header.addWidget(self.spinner)
        header.addWidget(self.buildStatus, 1)
        header.addWidget(self.tokensLabel)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.stopButton = QPushButton("Stop")
        self.stopButton.clicked.connect(self._stop)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.stopButton)
        layout = QVBoxLayout(page)
        layout.addLayout(header)
        layout.addWidget(self.log, 1)
        layout.addLayout(buttons)
        return page

    def _reviewPage(self) -> QWidget:
        page = QWidget()
        self.headline = QLabel()
        self.headline.setWordWrap(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.location = QLabel()
        self.location.setWordWrap(True)
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        aiNote = MutedLabel(AI_NOTE)
        aiNote.setWordWrap(True)
        self.details = QTabWidget()
        self.feedback = QPlainTextEdit()
        self.feedback.setPlaceholderText(
            "What should change? e.g. “Also output the band center.”"
        )
        self.feedback.setMaximumHeight(70)
        self.reviseButton = QPushButton("Ask for Changes")
        self.reviseButton.clicked.connect(self._revise)
        discard = QPushButton("Discard")
        discard.clicked.connect(self.reject)
        self.enableButton = QPushButton("Enable")
        self.enableButton.clicked.connect(self._enable)
        buttons = QHBoxLayout()
        buttons.addWidget(discard)
        buttons.addStretch(1)
        buttons.addWidget(self.reviseButton)
        buttons.addWidget(self.enableButton)
        layout = QVBoxLayout(page)
        for widget in (
            self.headline,
            self.summary,
            self.location,
            self.warnings,
            aiNote,
        ):
            layout.addWidget(widget)
        layout.addWidget(self.details, 1)
        layout.addWidget(self.feedback)
        layout.addLayout(buttons)
        return page

    # --- building --------------------------------------------------------------

    def _start(self) -> None:
        description = self.description.toPlainText().strip()
        if not description:
            self.description.setFocus()
            return
        try:
            provider = self.settings.createProvider()
        except ProviderError as error:
            QMessageBox.warning(self, "Kindle a Feature", str(error))
            return
        image = self.imageChoice.currentData()
        self.tools = KindlingTools(
            PluginFolder(self.folder), lambda folder: runChecks(folder, image)
        )
        self.kindler = Kindler(
            provider,
            self.tools,
            self.settings.tokenBudget,
            onMainThread(self._progress),
        )
        kindler = self.kindler
        self._build(lambda: kindler.kindle(description, image))

    def _revise(self) -> None:
        feedback = self.feedback.toPlainText().strip()
        if not feedback or self.kindler is None:
            self.feedback.setFocus()
            return
        self.feedback.clear()
        self.log.appendPlainText(f"\nYou asked: {feedback}")
        kindler = self.kindler
        self._build(lambda: kindler.revise(feedback))

    def _build(self, task) -> None:
        self.building = True
        self.buildStatus.setText("Building…")
        self.stopButton.setEnabled(True)
        self.pages.setCurrentIndex(1)
        runInBackground(
            task, self._built, self._failed, description="Kindling a feature"
        )

    def _progress(self, message: str) -> None:
        self.log.appendPlainText(message)
        if message.endswith("…"):
            self.buildStatus.setText(message)
        if self.kindler is not None:
            self.tokensLabel.setText(f"{self.kindler.tokens:,} tokens")

    def _stop(self) -> None:
        if self.kindler is not None:
            self.kindler.cancelled.set()
        self.stopButton.setEnabled(False)
        self.buildStatus.setText("Stopping after this step…")

    def _failed(self, error: Exception) -> None:
        """A request failed (the network, say): show what there is, so the
        user can continue with Ask for Changes or discard it."""
        self.building = False
        if self.closeWhenDone:
            self._discard()
            return
        self.log.appendPlainText(f"\n{error}")
        if self.kindler is None:
            QMessageBox.warning(self, "Kindle a Feature", str(error))
            return
        kindler = self.kindler
        self._showReview(Outcome(False, "", str(error), kindler.tokens, kindler.turns))

    def _built(self, outcome: Outcome) -> None:
        self.building = False
        if self.closeWhenDone:
            self._discard()
            return
        self._showReview(outcome)

    # --- review ----------------------------------------------------------------

    def _showReview(self, outcome: Outcome) -> None:
        assert self.tools is not None
        report = self.tools.lastReport
        passed = report is not None and report.passed
        if outcome.finished:
            self.headline.setText("<h3>Your feature is ready to review</h3>")
        else:
            self.headline.setText(
                f"<h3>The plugin isn't finished</h3>{escape(outcome.stopReason)} "
                "To keep going, write “continue” (or what to change) and click "
                "Ask for Changes."
            )
        self.summary.setText(outcome.summary)
        self.summary.setVisible(bool(outcome.summary))
        places = [a.location for a in report.analyses] if report is not None else []
        self.location.setText("<b>Adds:</b> " + "; ".join(places) if places else "")
        warnings = scanForWarnings(self.folder)
        self.warnings.setText(
            "<b>⚠ Warnings:</b><br>" + "<br>".join(warnings) if warnings else ""
        )
        self.warnings.setVisible(bool(warnings))
        self.details.clear()
        self.details.addTab(
            _monospace(report.describe() if report else "The checks haven't run."),
            "Checks ✓" if passed else "Checks ✗",
        )
        for relative in PluginFolder(self.folder).files():
            self.details.addTab(
                _monospace(PluginFolder(self.folder).read(relative)), relative
            )
        self.details.addTab(_monospace(self.log.toPlainText()), "Log")
        self.enableButton.setEnabled(passed)
        self.enableButton.setToolTip(
            "" if passed else "Enable needs the checks to pass"
        )
        self.tokensLabel.setText(f"{outcome.tokens:,} tokens")
        self.pages.setCurrentIndex(2)

    def _enable(self) -> None:
        if installPlugin(self.manager, self.folder, self) is not None:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.accept()

    def _discard(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)
        super().reject()

    def reject(self) -> None:
        """Escape, the close button or Cancel: while building, stop first
        (the build finishes its current step), then close."""
        if self.building:
            self.closeWhenDone = True
            self._stop()
            return
        if self.pages.currentIndex() == 2:
            answer = QMessageBox.question(
                self, "Discard Plugin", "Discard this plugin? It isn't enabled yet."
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._discard()
