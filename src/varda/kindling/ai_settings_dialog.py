"""Plugins → AI Assistant Settings: the provider, API key, model and token
limit Kindle a Feature uses."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from varda.common.ui import MutedLabel
from varda.kindling.ai_settings import AISettings
from varda.kindling.providers import ANTHROPIC_MODELS, AnthropicProvider, ProviderError
from varda.utilities.background import runInBackground

KEYS_URL = "https://console.anthropic.com/settings/keys"


class AISettingsDialog(QDialog):
    def __init__(
        self, settings: AISettings | None = None, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("AI Assistant Settings")
        self.setMinimumWidth(520)
        self.settings = settings if settings is not None else AISettings()

        provider = QComboBox()
        provider.addItem("Anthropic (Claude)")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.removeKey = QPushButton("Remove Key")
        self.removeKey.clicked.connect(self._removeKey)
        keyRow = QHBoxLayout()
        keyRow.addWidget(self.key, 1)
        keyRow.addWidget(self.removeKey)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems(ANTHROPIC_MODELS)
        self.model.setCurrentText(self.settings.model)
        self.budget = QSpinBox()
        self.budget.setRange(50_000, 5_000_000)
        self.budget.setSingleStep(50_000)
        self.budget.setGroupSeparatorShown(True)
        self.budget.setSuffix(" tokens")
        self.budget.setValue(self.settings.tokenBudget)

        form = QFormLayout()
        form.addRow("Provider:", provider)
        form.addRow("API key:", keyRow)
        keyHelp = QLabel(
            f'Create a key at <a href="{KEYS_URL}">console.anthropic.com</a>. It\'s '
            "kept in your system's keychain, never in a file."
        )
        keyHelp.setOpenExternalLinks(True)
        keyHelp.setWordWrap(True)
        form.addRow("", keyHelp)
        form.addRow("Model:", self.model)
        form.addRow("Limit per feature:", self.budget)
        budgetNote = MutedLabel(
            "Varda stops building a feature when it has used this many tokens. "
            "Anthropic bills your account for the tokens used."
        )
        budgetNote.setWordWrap(True)
        form.addRow("", budgetNote)

        self.status = MutedLabel("")
        self.status.setWordWrap(True)
        test = QPushButton("Test Connection")
        test.clicked.connect(self._test)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.addButton(test, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(buttons)
        self._showSavedKey()

    def _showSavedKey(self) -> None:
        try:
            saved = bool(self.settings.apiKey())
        except ProviderError as error:
            saved = False
            self.status.setText(str(error))
        self.key.clear()
        self.key.setPlaceholderText("Saved in your keychain" if saved else "sk-ant-…")
        self.removeKey.setEnabled(saved)

    def _keyToUse(self) -> str:
        return self.key.text().strip() or self.settings.apiKey()

    def _test(self) -> None:
        try:
            key = self._keyToUse()
        except ProviderError as error:
            self.status.setText(str(error))
            return
        if not key:
            self.status.setText("Enter an API key first.")
            return
        self.status.setText("Testing…")
        provider = AnthropicProvider(key, self.model.currentText().strip())
        runInBackground(
            provider.test,
            self.status.setText,
            lambda error: self.status.setText(str(error)),
            description="Testing the AI connection",
        )

    def _removeKey(self) -> None:
        try:
            self.settings.removeApiKey()
            self.status.setText("The key was removed from your keychain.")
        except ProviderError as error:
            self.status.setText(str(error))
        self._showSavedKey()

    def _save(self) -> None:
        try:
            if self.key.text().strip():
                self.settings.setApiKey(self.key.text().strip())
        except ProviderError as error:
            self.status.setText(str(error))
            return
        self.settings.model = self.model.currentText().strip()
        self.settings.tokenBudget = self.budget.value()
        self.accept()
