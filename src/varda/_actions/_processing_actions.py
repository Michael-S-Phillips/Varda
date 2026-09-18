"""The Processing menu: one entry per analysis, grouped into category submenus.

Entries are generated from the analysis registry, so adding an analysis is
just registering it with a ``category``. Analyses whose optional dependency
is missing stay visible but disabled, saying what they need.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from app_model.types import Action, MenuRule, SubmenuItem
from PyQt6.QtWidgets import QMessageBox

from varda._actions._menu_ids import MenuId
from varda.analysis.analysis import Analysis
from varda.analysis.dialog import RunAnalysisDialog
from varda.analysis.eigenvalue_dialog import EigenvaluePlotDialog
from varda.analysis.registry import ANALYSES
from varda.analysis.runner import AnalysisRunner
from varda.analysis.transforms import TRANSFORM_METADATA_KEY, InverseTransformAnalysis
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.context_keys import EXPR_HAS_IMAGES, EXPR_NEVER
from varda.maingui import MainGUI


def openRunAnalysisDialog(
    images: ProjectImages, mainGui: MainGUI, *, analysis: type[Analysis]
) -> None:
    """Show the dialog for one analysis; the run lands in the project images."""
    if not analysis.isAvailable():
        QMessageBox.information(
            mainGui,
            f"{analysis.name} is unavailable",
            f"{analysis.name} needs {analysis.requirement}; see the README.",
        )
        return
    runner = AnalysisRunner(images, parent=mainGui)
    # Analyses that use ROIs get the current workspace's collection (the
    # workspaces assume their images are co-registered with it).
    rois = getattr(mainGui.currentWorkspace(), "roiCollection", None)
    RunAnalysisDialog(
        list(images), [analysis], analysis=analysis, rois=rois, parent=mainGui
    ).connectOnRun(runner.run).open()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def categoryMenuId(root: str, category: str) -> str:
    return f"{root}/{_slug(category)}"


def processingSubmenus(
    root: str, analyses: Sequence[type[Analysis]]
) -> list[tuple[str, SubmenuItem]]:
    """One submenu under ``root`` per category, in first-appearance order."""
    categories = list(dict.fromkeys(analysis.category for analysis in analyses))
    return [
        (
            root,
            SubmenuItem(
                submenu=categoryMenuId(root, category), title=category, order=i
            ),
        )
        for i, category in enumerate(categories)
    ]


def processingActions(
    root: str,
    idPrefix: str,
    analyses: Sequence[type[Analysis]],
    makeCallback: Callable[[type[Analysis]], Callable],
) -> list[Action]:
    """One action per analysis, filed under its category's submenu."""
    actions = []
    for analysis in analyses:
        available = analysis.isAvailable()
        title = f"{analysis.name}…"
        if not available:
            title += f" (needs {analysis.requirement})"
        actions.append(
            Action(
                id=f"{idPrefix}.{analysis.analysisId}",
                title=title,
                tooltip=analysis.description,
                callback=makeCallback(analysis),
                enablement=EXPR_HAS_IMAGES if available else EXPR_NEVER,
                menus=[MenuRule(id=categoryMenuId(root, analysis.category))],
            )
        )
    return actions


def _menuCallback(analysis: type[Analysis]) -> Callable:
    def run(images: ProjectImages, mainGui: MainGUI) -> None:
        openRunAnalysisDialog(images, mainGui, analysis=analysis)

    return run


def _latestTransformResult(images: ProjectImages) -> VardaRaster | None:
    return next(
        (
            image
            for image in reversed(list(images))
            if TRANSFORM_METADATA_KEY in image.extraMetadata
        ),
        None,
    )


def openEigenvaluePlot(images: ProjectImages, mainGui: MainGUI) -> None:
    """Inspect a transform result's eigenvalues; non-modal so the component
    images can be browsed alongside."""
    dialog = EigenvaluePlotDialog(
        list(images), image=_latestTransformResult(images), parent=mainGui
    )
    dialog.sigInverseRequested.connect(
        lambda image, count: openInverseTransformDialog(images, mainGui, image, count)
    )
    dialog.show()


def openInverseTransformDialog(
    images: ProjectImages, mainGui: MainGUI, image: VardaRaster, components: int
) -> None:
    """The Inverse Transform dialog for ``image`` with the component count preset."""
    runner = AnalysisRunner(images, parent=mainGui)
    dialog = RunAnalysisDialog(
        list(images),
        [InverseTransformAnalysis],
        image=image,
        analysis=InverseTransformAnalysis,
        parent=mainGui,
    )
    analysis = dialog.selectedAnalysis()
    assert isinstance(analysis, InverseTransformAnalysis)
    analysis.components.set(components)
    dialog.connectOnRun(runner.run).open()


EIGENVALUE_PLOT_ACTION_ID = "varda.processing.eigenvalue_plot"

PROCESSING_SUBMENUS = processingSubmenus(MenuId.PROCESSING, ANALYSES)
PROCESSING_ACTIONS = processingActions(
    MenuId.PROCESSING, "varda.processing", ANALYSES, _menuCallback
) + [
    Action(
        id=EIGENVALUE_PLOT_ACTION_ID,
        title="Eigenvalue Plot…",
        tooltip=(
            "Plot and tabulate a PCA / MNF / ICA result's eigenvalues to decide "
            "how many components to keep"
        ),
        callback=openEigenvaluePlot,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=categoryMenuId(MenuId.PROCESSING, "Transforms"), order=99)],
    )
]
