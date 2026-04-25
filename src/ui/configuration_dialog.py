from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from ..base.config_panel import ConfigPanel


class ConfigurationDialog(QDialog):

    def __init__(self, parent: QWidget | None, panels: list[ConfigPanel]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self._panels = panels

        layout = QVBoxLayout(self)

        if len(panels) == 1:
            layout.addWidget(panels[0])
        else:
            tabs = QTabWidget(self)
            for panel in panels:
                tabs.addTab(panel, panel.title or panel.__class__.__name__)
            layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(440, 320)

    def _on_accept(self) -> None:
        for panel in self._panels:
            if not panel.apply():
                return
        self.accept()
