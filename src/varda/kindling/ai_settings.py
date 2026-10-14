"""Settings → AI Assistant: which AI builds plugins. The API key lives only in
the operating system's keychain (``keyring``), never in a settings file or a
session; the model and token limit are ordinary settings."""

from __future__ import annotations

import keyring
import keyring.errors
from PyQt6.QtCore import QSettings

from varda.kindling.providers import (
    ANTHROPIC,
    ANTHROPIC_MODELS,
    AnthropicProvider,
    ProviderError,
)

KEYRING_SERVICE = "Varda AI Assistant"
MODEL_KEY = "ai/model"
TOKEN_BUDGET_KEY = "ai/tokenBudget"
DEFAULT_TOKEN_BUDGET = 400_000


class AISettings:
    provider = ANTHROPIC  # the only provider so far

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings if settings is not None else QSettings()

    @property
    def model(self) -> str:
        return str(self.settings.value(MODEL_KEY, ANTHROPIC_MODELS[0]))

    @model.setter
    def model(self, model: str) -> None:
        self.settings.setValue(MODEL_KEY, model)

    @property
    def tokenBudget(self) -> int:
        return int(
            self.settings.value(TOKEN_BUDGET_KEY, DEFAULT_TOKEN_BUDGET, type=int)
        )

    @tokenBudget.setter
    def tokenBudget(self, tokens: int) -> None:
        self.settings.setValue(TOKEN_BUDGET_KEY, tokens)

    def apiKey(self) -> str:
        """The saved key, or "" if there's none. Raises ProviderError when the
        keychain can't be used."""
        try:
            return keyring.get_password(KEYRING_SERVICE, self.provider) or ""
        except keyring.errors.KeyringError as error:
            raise ProviderError(f"Varda couldn't read the keychain: {error}") from error

    def setApiKey(self, key: str) -> None:
        try:
            keyring.set_password(KEYRING_SERVICE, self.provider, key)
        except keyring.errors.KeyringError as error:
            raise ProviderError(
                f"Varda couldn't save the key in the keychain: {error}"
            ) from error

    def removeApiKey(self) -> None:
        try:
            keyring.delete_password(KEYRING_SERVICE, self.provider)
        except keyring.errors.PasswordDeleteError:
            pass  # there was none
        except keyring.errors.KeyringError as error:
            raise ProviderError(f"Varda couldn't remove the key: {error}") from error

    def createProvider(self) -> AnthropicProvider:
        key = self.apiKey()
        if not key:
            raise ProviderError(
                "Add an API key in Plugins → AI Assistant Settings first."
            )
        return AnthropicProvider(key, self.model)
