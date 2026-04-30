from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QWidget

from .user_settings import UserSettings


class PersistentSizeDialog(QDialog):
    """A `QDialog` that remembers its size in `UserSettings`.

    Subclasses set `size_settings_prefix` to a unique string — width and
    height are stored under `<prefix>_width` and `<prefix>_height`, so two
    dialogs with different prefixes don't share state. After building their
    layout, subclasses call `restore_size(default)` once with the size to
    use when no saved value exists. The class auto-saves on close, OK, or
    Cancel.
    """

    size_settings_prefix: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        # Promote from Qt.Dialog (no taskbar entry on Windows) to Qt.Window
        # so this dialog gets its own taskbar button + the app icon while
        # the tray's hidden TrayWidget would otherwise leave it iconless.
        # Set flags explicitly because Qt.Dialog has the Qt.Window bit
        # baked in — toggling the Dialog bit alone strips Window too.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

    def restore_size(self, default: QSize) -> None:
        if not self.size_settings_prefix:
            self.resize(default)
            return
        saved_w = self._user_settings.get_int(f'{self.size_settings_prefix}_width', 0)
        saved_h = self._user_settings.get_int(f'{self.size_settings_prefix}_height', 0)
        if saved_w > 0 and saved_h > 0:
            self.resize(saved_w, saved_h)
        else:
            self.resize(default)

    def _save_size(self) -> None:
        if not self.size_settings_prefix:
            return
        self._user_settings.set(f'{self.size_settings_prefix}_width', self.width())
        self._user_settings.set(f'{self.size_settings_prefix}_height', self.height())

    def closeEvent(self, event) -> None:
        self._save_size()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self._save_size()
        super().done(result)
