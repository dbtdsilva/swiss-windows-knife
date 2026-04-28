import pytest


class _FakeUserSettings:
    def __init__(self) -> None:
        self._data: dict = {}

    def get(self, key):
        return self._data.get(key)

    def has_key(self, key) -> bool:
        return key in self._data

    def set(self, key, value) -> None:
        self._data[key] = value


@pytest.fixture
def fake_user_settings(monkeypatch):
    """Replace `UserSettings.instance()` with a dict-backed fake.

    Panels and plugins fetch settings via the singleton at __init__ time,
    so this fixture must be applied before instantiating them.
    """
    from src.base.user_settings import UserSettings
    fake = _FakeUserSettings()
    monkeypatch.setattr(UserSettings, 'instance', classmethod(lambda cls: fake))
    return fake


@pytest.fixture
def silent_messagebox(monkeypatch):
    """Suppress QMessageBox modals so apply()-style validation can run headless."""
    from PySide6.QtWidgets import QMessageBox
    for method in ('warning', 'critical', 'information', 'question'):
        monkeypatch.setattr(QMessageBox, method, lambda *args, **kwargs: None)
