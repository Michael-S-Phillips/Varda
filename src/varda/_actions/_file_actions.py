from app_model.types import Action, MenuRule, StandardKeyBinding
from PyQt6.QtWidgets import QApplication

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.common.di_types import ProjectImages
from varda.image_loading import ImageLoadingService


def importImage(images: ProjectImages) -> None:
    ImageLoadingService.load_image_data(on_success_callback=images.append)


def exitApp() -> None:
    QApplication.instance().quit()


FILE_ACTIONS: list[Action] = [
    Action(
        id="varda.file.import_image",
        title="Import Image",
        icon="fa6-solid:folder-open",
        callback=importImage,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_IO, order=1)],
        keybindings=[StandardKeyBinding.New.to_keybinding_rule()],
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
