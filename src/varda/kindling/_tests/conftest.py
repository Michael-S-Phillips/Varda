import os

import keyring
import keyring.errors
import pytest
from keyring.backend import KeyringBackend

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryKeyring(KeyringBackend):
    """Keeps passwords in a dict, so tests never touch the real keychain."""

    priority = 1  # type: ignore[assignment]

    def __init__(self):
        super().__init__()
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        if self.passwords.pop((service, username), None) is None:
            raise keyring.errors.PasswordDeleteError(username)


@pytest.fixture(autouse=True)
def memoryKeyring():
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)
