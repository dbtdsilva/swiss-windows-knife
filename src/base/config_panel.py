from PySide6.QtWidgets import QWidget


class ConfigPanel(QWidget):
    """A plugin's section inside the unified Configuration dialog.

    Subclasses set `title` (shown as the tab label when more than one
    panel is contributed) and override `apply()` to validate and
    persist the panel's settings. Returning False from `apply()` keeps
    the dialog open so the user can fix invalid input.
    """

    title: str = ""

    def apply(self) -> bool:
        return True
