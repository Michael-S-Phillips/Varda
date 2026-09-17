"""Rebuild a saved session: reload its images one after another (the loading
service works asynchronously), then reopen its workspaces with their ROIs."""

from __future__ import annotations

import logging
from collections.abc import Callable

import attrs
from PyQt6.QtCore import QObject, pyqtSignal

from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading import ImageLoadingService
from varda.session import SessionState, WorkspaceState, roisFromJson
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
)
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)

logger = logging.getLogger(__name__)

# (path, onSuccess(image), onFailure(message)) — the loading service's shape
ImageLoader = Callable[
    [str, Callable[[VardaRaster], None], Callable[[str], None]], None
]


@attrs.frozen
class RestoreReport:
    loaded: tuple[str, ...]  # paths loaded for the session
    failed: tuple[str, ...]  # paths that could not be loaded
    workspaces: int  # workspaces reopened


class SessionRestorer(QObject):
    sigFinished = pyqtSignal(object)  # RestoreReport

    def __init__(
        self,
        images: ProjectImages,
        mainGui,
        loadImage: ImageLoader = ImageLoadingService.load_image_data,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._images = images
        self._mainGui = mainGui
        self._loadImage = loadImage
        self._state = SessionState((), ())
        self._pending: list[str] = []
        self._loaded: list[str] = []
        self._failed: list[str] = []

    def restore(self, state: SessionState) -> None:
        self._state = state
        # images already in the project (matched by path) are not loaded twice
        self._pending = [path for path in state.images if self._byPath(path) is None]
        self._loaded, self._failed = [], []
        self._loadNext()

    def _byPath(self, path: str) -> VardaRaster | None:
        return next((image for image in self._images if image.filePath == path), None)

    def _loadNext(self) -> None:
        if not self._pending:
            self._openWorkspaces()
            return
        path = self._pending.pop(0)

        def onSuccess(image: VardaRaster) -> None:
            self._images.append(image)
            self._loaded.append(path)
            self._loadNext()

        def onFailure(message: str) -> None:
            logger.warning("Session image %s could not be loaded: %s", path, message)
            self._failed.append(path)
            self._loadNext()

        self._loadImage(path, onSuccess, onFailure)

    def _openWorkspaces(self) -> None:
        count = 0
        for workspace in self._state.workspaces:
            images = [self._byPath(path) for path in workspace.images]
            if any(image is None for image in images):
                continue
            built = self._build(workspace, [image for image in images if image])
            if built is None:
                continue
            widget, title = built
            roisFromJson(workspace.rois, widget.roiCollection)
            self._mainGui.addTab(widget, title)
            count += 1
        self.sigFinished.emit(
            RestoreReport(tuple(self._loaded), tuple(self._failed), count)
        )

    def _build(self, workspace: WorkspaceState, images: list[VardaRaster]):
        if workspace.kind == "general":
            config = GeneralImageAnalysisConfig(list(self._images))
            config.image.set(images[0])
            return GeneralImageAnalysisWorkflow(
                config
            ), "General Image Analysis Workspace"
        if workspace.kind == "dual" and len(images) == 2:
            config = DualImageWorkspaceConfig(list(self._images))
            config.image1Param.set(images[0])
            config.image2Param.set(images[1])
            return DualImageWorkspace(config), "Dual Image Workspace"
        logger.warning("Unknown workspace kind %r in session; skipped", workspace.kind)
        return None
