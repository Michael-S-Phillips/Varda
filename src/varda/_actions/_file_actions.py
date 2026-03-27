from app_model.types import Action, KeyBindingRule, KeyCode, KeyMod, MenuRule
from PyQt6.QtWidgets import QApplication

import varda
from varda._actions._menu_ids import MenuId, MenuGroup
from varda.common.observable_list import ImageList
from varda.image_loading import ImageLoadingService


def importImage(images: ImageList) -> None:
    ImageLoadingService.load_image_data(on_success_callback=images.append)


def exitApp() -> None:
    varda.log.info("Exiting application...")
    QApplication.instance().quit()


FILE_ACTIONS: list[Action] = [
    Action(
        id="varda.file.import_image",
        title="Import Image",
        icon="fa6-solid:folder-open",
        callback=importImage,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_IO, order=1)],
        keybindings=[KeyBindingRule(primary=KeyMod.CtrlCmd | KeyCode.KeyN)],
    ),
    Action(
        id="varda.file.exit",
        title="Exit",
        icon="fa6-solid:close",
        callback=exitApp,
        menus=[MenuRule(id=MenuId.FILE, group=MenuGroup.FILE_EXIT, order=1)],
        keybindings=[KeyBindingRule(primary=KeyMod.CtrlCmd | KeyCode.KeyQ)],
    ),
]
