"""The Help menu: about Varda, how to cite it, system info for bug reports,
the documentation and the issue tracker."""

from __future__ import annotations

from app_model.types import Action, MenuRule
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.help_info import (
    DOCUMENTATION_URL,
    ISSUES_URL,
    REPOSITORY_URL,
    citation,
    systemInfo,
)
from varda.maingui import MainGUI
from varda.version import vardaVersion


def _copy(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def showAbout(mainGui: MainGUI) -> None:
    QMessageBox.about(
        mainGui,
        "About Varda",
        f"<h3>Varda {vardaVersion()}</h3>"
        "<p>Visualization and analysis of raster data: hyperspectral and "
        "multispectral imagery.</p>"
        "<p>Developed at the Space Imagery Center, Lunar and Planetary "
        "Laboratory, University of Arizona, by Michael Phillips, Jesse Oved, "
        "Emma Elliott and Hamad Ayaz.</p>"
        "<p>Free software under the GNU General Public License v3 or later.</p>"
        f'<p><a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a></p>',
    )


class CiteDialog(QDialog):
    """The citation as APA and BibTeX, each with a copy button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cite Varda")
        apa, bibtex = citation()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("If Varda helps your research, please cite it:"))
        for title, text in (("APA", apa), ("BibTeX", bibtex)):
            layout.addWidget(QLabel(f"<b>{title}</b>"))
            box = QPlainTextEdit(text)
            box.setReadOnly(True)
            box.setMinimumHeight(70 if title == "APA" else 150)
            layout.addWidget(box)
            button = QPushButton(f"Copy {title}")
            button.clicked.connect(lambda _, t=text: _copy(t))
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(520)


def showCitation(mainGui: MainGUI) -> None:
    dialog = CiteDialog(mainGui)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.open()


def copySystemInfo(mainGui: MainGUI) -> None:
    _copy(systemInfo())
    statusBar = mainGui.statusBar()
    if statusBar is not None:
        statusBar.showMessage("System info copied to the clipboard", 4000)


def openDocumentation() -> None:
    QDesktopServices.openUrl(QUrl(DOCUMENTATION_URL))


def reportIssue() -> None:
    QDesktopServices.openUrl(QUrl(ISSUES_URL))


def _inHelp(group: str, order: int) -> list[MenuRule]:
    return [MenuRule(id=MenuId.HELP, group=group, order=order)]


HELP_ACTIONS: list[Action] = [
    Action(
        id="varda.help.documentation",
        title="Documentation",
        callback=openDocumentation,
        menus=_inHelp(MenuGroup.HELP_LINKS, 1),
    ),
    Action(
        id="varda.help.report_issue",
        title="Report an Issue…",
        callback=reportIssue,
        menus=_inHelp(MenuGroup.HELP_LINKS, 2),
    ),
    Action(
        id="varda.help.copy_system_info",
        title="Copy System Info",
        tooltip="Copy the version and platform details a bug report needs",
        callback=copySystemInfo,
        menus=_inHelp(MenuGroup.HELP_INFO, 1),
    ),
    Action(
        id="varda.help.cite",
        title="Cite Varda…",
        callback=showCitation,
        menus=_inHelp(MenuGroup.HELP_INFO, 2),
    ),
    Action(
        id="varda.help.about",
        title="About Varda",
        callback=showAbout,
        menus=_inHelp(MenuGroup.HELP_ABOUT, 1),
    ),
]
