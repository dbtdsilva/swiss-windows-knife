from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from .user_settings import UserSettings

SETTINGS_KEY = "appearance/color_scheme"


class ColorSchemePreference(Enum):
    SYSTEM = "Follow system"
    LIGHT = "Light"
    DARK = "Dark"


_QT_BY_PREFERENCE = {
    ColorSchemePreference.SYSTEM: Qt.ColorScheme.Unknown,
    ColorSchemePreference.LIGHT: Qt.ColorScheme.Light,
    ColorSchemePreference.DARK: Qt.ColorScheme.Dark,
}


def load_preference() -> ColorSchemePreference:
    return UserSettings.instance().get(
        SETTINGS_KEY, ColorSchemePreference, ColorSchemePreference.SYSTEM,
    )


def save_preference(preference: ColorSchemePreference) -> None:
    UserSettings.instance().set(SETTINGS_KEY, preference)


def apply_preference(preference: ColorSchemePreference) -> None:
    """Push the preference into Qt's style hints.

    `Qt.ColorScheme.Unknown` means "follow the system" — Qt's Windows
    platform plugin then tracks the OS light/dark setting (and live updates
    when the user toggles it). Light/Dark force the palette regardless of
    the OS setting.
    """
    hints = QGuiApplication.styleHints()
    if hints is None:
        logging.warning("QStyleHints unavailable; cannot apply color scheme")
        return
    hints.setColorScheme(_QT_BY_PREFERENCE[preference])


def apply_persisted_preference() -> None:
    apply_preference(load_preference())
