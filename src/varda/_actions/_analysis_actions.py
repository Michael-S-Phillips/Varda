from app_model.types import Action, MenuRule
from PyQt6.QtWidgets import QMessageBox

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.analysis.dialog import RunAnalysisDialog
from varda.analysis.registry import availableAnalyses
from varda.analysis.runner import AnalysisRunner
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.context_keys import EXPR_HAS_IMAGES
from varda.maingui import MainGUI


def openRunAnalysisDialog(
    images: ProjectImages, mainGui: MainGUI, image: VardaRaster | None = None
) -> None:
    """Show the Run Analysis dialog, optionally pre-selecting an image."""
    analyses = availableAnalyses()
    if not analyses:
        QMessageBox.information(
            mainGui,
            "No analyses available",
            "No analyses are installed. Band parameters need the optional "
            "HyPyRameter dependency; see the README for how to install it.",
        )
        return
    runner = AnalysisRunner(images, parent=mainGui)
    RunAnalysisDialog(list(images), analyses, image=image, parent=mainGui).connectOnRun(
        runner.run
    ).open()


def runAnalysis(images: ProjectImages, mainGui: MainGUI) -> None:
    openRunAnalysisDialog(images, mainGui)


ANALYSIS_ACTIONS: list[Action] = [
    Action(
        id="varda.analysis.run",
        title="Run Analysis…",
        callback=runAnalysis,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.ANALYSIS, group=MenuGroup.ANALYSIS_RUN, order=1)],
    ),
]
