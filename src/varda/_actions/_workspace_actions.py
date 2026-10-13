from app_model.types import Action, MenuRule, StandardKeyBinding

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.context_keys import EXPR_HAS_IMAGES, EXPR_HAS_WORKSPACE
from varda.common.di_types import ProjectImages
from varda.maingui import WORKSPACE_TAB_MENU_ID, MainGUI
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog
from varda.workspaces.general_image_analysis import (
    NewGeneralImageAnalysisWorkspaceDialog,
)
from varda.workspaces.spectral_hourglass.new_hourglass_dialog import (
    NewSpectralHourglassDialog,
)
from varda.workspaces.workspace_kinds import duplicateWorkspace


def newDualImageWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    NewDualImageWorkspaceDialog(images).connectOnAccept(mainGui.addTab).open()


def newGeneralAnalysisWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    NewGeneralImageAnalysisWorkspaceDialog(images).connectOnAccept(
        mainGui.addTab
    ).open()


def newSpectralHourglassWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    NewSpectralHourglassDialog(images, parent=mainGui).connectOnAccept(
        mainGui.addTab
    ).open()


def duplicateCurrentWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    """Open a copy of the current workspace in a new tab."""
    source = mainGui.currentWorkspace()
    copy = duplicateWorkspace(source, images) if source is not None else None
    if source is not None and copy is not None:
        mainGui.addTab(copy, f"{source.windowTitle()} (copy)")


def closeCurrentWorkspace(mainGui: MainGUI) -> None:
    mainGui.closeWorkspace(mainGui.currentWorkspace())


WORKSPACE_ACTIONS: list[Action] = [
    Action(
        id="varda.workspace.new_dual_image",
        title="New Dual Image Workspace",
        callback=newDualImageWorkspace,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_NEW, order=1)],
    ),
    Action(
        id="varda.workspace.new_general_analysis",
        title="New General Image Analysis Workspace",
        callback=newGeneralAnalysisWorkspace,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_NEW, order=2)],
    ),
    Action(
        id="varda.workspace.new_spectral_hourglass",
        title="New Spectral Hourglass Workspace…",
        tooltip=(
            "Find endmembers (MNF, pixel purity, n-D visualizer), identify them "
            "against a spectral library, and map them across the scene"
        ),
        callback=newSpectralHourglassWorkspace,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_NEW, order=3)],
    ),
    Action(
        id="varda.workspace.duplicate",
        title="Duplicate Workspace",
        tooltip=(
            "Open a copy of this workspace: the same images, with its own copies "
            "of the ROIs and display settings"
        ),
        callback=duplicateCurrentWorkspace,
        enablement=EXPR_HAS_WORKSPACE,
        menus=[
            MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_MANAGE, order=0),
            MenuRule(id=WORKSPACE_TAB_MENU_ID, order=0),
        ],
    ),
    Action(
        id="varda.workspace.close",
        title="Close Workspace",
        callback=closeCurrentWorkspace,
        enablement=EXPR_HAS_WORKSPACE,
        menus=[
            MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_MANAGE, order=1),
            MenuRule(id=WORKSPACE_TAB_MENU_ID, order=1),
        ],
        keybindings=[StandardKeyBinding.Close.to_keybinding_rule()],
    ),
]
