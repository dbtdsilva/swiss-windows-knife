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

    def cleanup(self) -> None:
        """Called by `ConfigurationDialog` once when the dialog is closing
        (OK, Cancel, or X), *before* Qt's parent-child destruction cascade.

        Override to cancel in-flight async work whose callbacks would emit
        on widgets that are about to be torn down. Tests don't need to call
        this; production wiring goes through `ConfigurationDialog.done`.
        """
        return None
