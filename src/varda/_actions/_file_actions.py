import logging

from app_model.types import Action, MenuRule, StandardKeyBinding
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.common.di_types import ProjectImages
from varda.context_keys import EXPR_HAS_IMAGES
from varda.image_loading import ImageLoadingService
from varda.image_loading.export_image_dialog import ExportImageDialog
from varda.maingui import MainGUI
from varda.session import SESSION_FILE_FILTER, captureSession, readSession, writeSession
from varda.session_restore import RestoreReport, SessionRestorer

logger = logging.getLogger(__name__)


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
            "them (export them first to keep them):\n"
            + "\n".join(capture.unsavedImages),
        )


def openSession(images: ProjectImages, mainGui: MainGUI) -> None:
    """Load a .varda session's images and reopen its workspaces, alongside
    whatever is already open."""
    path, _ = QFileDialog.getOpenFileName(
        mainGui, "Open Session", "", SESSION_FILE_FILTER
    )
    if not path:
        return
    try:
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
        id="varda.file.exit",
        title="Exit",
        icon="fa6-solid:close",
        callback=exitApp,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_EXIT, order=1)],
        keybindings=[StandardKeyBinding.Quit.to_keybinding_rule()],
    ),
]
