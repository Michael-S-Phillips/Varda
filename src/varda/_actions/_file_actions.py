import logging
from datetime import datetime
from pathlib import Path

from app_model.types import Action, MenuRule, StandardKeyBinding
from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.common.di_types import ProjectImages
from varda.context_keys import EXPR_HAS_IMAGES
from varda.image_loading import ImageLoadingService
from varda.image_loading.export_image_dialog import ExportImageDialog
from varda.maingui import MainGUI
from varda.session import (
    BUNDLE_SUFFIX,
    SESSION_FILE_FILTER,
    captureSession,
    openSessionBundle,
    readSession,
    saveSessionBundle,
    writeSession,
)
from varda.session_autosave import defaultAutosavePath
from varda.session_restore import RestoreReport, SessionRestorer

logger = logging.getLogger(__name__)

BUNDLE_FILE_FILTER = f"Self-contained Varda session (*{BUNDLE_SUFFIX})"
OPEN_SESSION_FILE_FILTER = f"Varda sessions (*.varda *{BUNDLE_SUFFIX})"


def _bundleFolder(bundle: Path) -> Path:
    """Where an opened bundle is extracted: Varda's data folder, one per open."""
    root = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return root / "sessions" / f"{bundle.name.removesuffix(BUNDLE_SUFFIX)}-{stamp}"


def exportImage(images: ProjectImages, mainGui: MainGUI) -> None:
    """Write one of the project's images to an ENVI or GeoTIFF file."""
    ExportImageDialog(list(images), parent=mainGui).open()


def saveSession(images: ProjectImages, mainGui: MainGUI) -> None:
    """Save the open images, workspaces and ROIs to a .varda file."""
    path, _ = QFileDialog.getSaveFileName(
        mainGui, "Save Session", "", SESSION_FILE_FILTER
    )
    if not path:
        return
    capture = captureSession(list(images), mainGui.childWindows)
    written = writeSession(capture.state, path)
    logger.info("Session saved to %s", written)
    if capture.unsavedImages:
        QMessageBox.warning(
            mainGui,
            "Some images were left out",
            "These images exist only in memory, so the session cannot refer to "
            "them. Export them first, or use Save Session (Self-Contained) to "
            "keep them inside the session:\n" + "\n".join(capture.unsavedImages),
        )


def saveSessionSelfContained(images: ProjectImages, mainGui: MainGUI) -> None:
    """Save the session as one zip that also holds every result that exists
    only in memory (as ENVI files), so it can be reopened anywhere."""
    path, _ = QFileDialog.getSaveFileName(
        mainGui, "Save Session (Self-Contained)", "", BUNDLE_FILE_FILTER
    )
    if not path:
        return
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        written = saveSessionBundle(list(images), mainGui.childWindows, path)
    except (OSError, ValueError) as error:
        QMessageBox.critical(mainGui, "Cannot save session", str(error))
        return
    finally:
        QApplication.restoreOverrideCursor()
    inMemory = sum(1 for image in images if not image.filePath)
    logger.info("Self-contained session saved to %s", written)
    QMessageBox.information(
        mainGui,
        "Session saved",
        f"Saved {written.name}, including {inMemory} result(s) that existed "
        "only in memory. Images opened from files are referenced where they are.",
    )


def openSession(images: ProjectImages, mainGui: MainGUI) -> None:
    """Load a .varda session (or a self-contained .varda.zip) and reopen its
    workspaces, alongside whatever is already open."""
    path, _ = QFileDialog.getOpenFileName(
        mainGui, "Open Session", "", OPEN_SESSION_FILE_FILTER
    )
    if path:
        _restoreSession(Path(path), images, mainGui)


def restoreLastSession(images: ProjectImages, mainGui: MainGUI) -> None:
    """Reopen the autosaved session (written every few minutes and on quit)."""
    path = defaultAutosavePath()
    if not path.exists():
        QMessageBox.information(
            mainGui,
            "No autosaved session yet",
            f"Varda autosaves the session every few minutes to\n{path}\n"
            "once an image is open. Nothing has been saved yet.",
        )
        return
    _restoreSession(path, images, mainGui)


def _restoreSession(path: Path, images: ProjectImages, mainGui: MainGUI) -> None:
    try:
        if path.name.lower().endswith(".zip"):
            path = openSessionBundle(path, _bundleFolder(path))
        state = readSession(path)
    except (OSError, ValueError, KeyError) as error:
        QMessageBox.critical(mainGui, "Cannot open session", str(error))
        return

    def report(result: RestoreReport) -> None:
        if result.failed:
            QMessageBox.warning(
                mainGui,
                "Some images could not be loaded",
                "Workspaces using them were skipped:\n" + "\n".join(result.failed),
            )

    restorer = SessionRestorer(images, mainGui, parent=mainGui)
    restorer.sigFinished.connect(report)
    restorer.restore(state)


def importImage(images: ProjectImages) -> None:
    """Prompt for one or more image files and load them into the project."""
    ImageLoadingService.load_images(on_success_callback=images.append)


def importImagePaths(filePaths: list[str], images: ProjectImages) -> None:
    """Load the given image files into the project (e.g. files dropped on the window)."""
    ImageLoadingService.load_images(
        file_paths=filePaths, on_success_callback=images.append
    )


def exitApp() -> None:
    QApplication.instance().quit()


FILE_ACTIONS: list[Action] = [
    Action(
        id="varda.file.import_image",
        title="Import Image(s)",
        icon="fa6-solid:folder-open",
        callback=importImage,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_IO, order=1)],
        keybindings=[StandardKeyBinding.New.to_keybinding_rule()],
    ),
    Action(
        id="varda.file.export_image",
        title="Export Image…",
        icon="fa6-solid:floppy-disk",
        callback=exportImage,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_IO, order=2)],
    ),
    Action(
        id="varda.file.open_session",
        title="Open Session…",
        icon="fa6-solid:folder-tree",
        callback=openSession,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_SESSION, order=1)],
        keybindings=[StandardKeyBinding.Open.to_keybinding_rule()],
    ),
    Action(
        id="varda.file.save_session",
        title="Save Session…",
        icon="fa6-solid:bookmark",
        callback=saveSession,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_SESSION, order=2)],
        keybindings=[StandardKeyBinding.Save.to_keybinding_rule()],
    ),
    Action(
        id="varda.file.save_session_self_contained",
        title="Save Session (Self-Contained)…",
        tooltip="One zip with the session and every result that exists only in memory",
        callback=saveSessionSelfContained,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_SESSION, order=3)],
    ),
    Action(
        id="varda.file.restore_last_session",
        title="Restore Last Session",
        icon="fa6-solid:clock-rotate-left",
        callback=restoreLastSession,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_SESSION, order=4)],
    ),
    Action(
        id="varda.file.exit",
        title="Exit",
        icon="fa6-solid:close",
        callback=exitApp,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_EXIT, order=1)],
        keybindings=[StandardKeyBinding.Quit.to_keybinding_rule()],
    ),
]
