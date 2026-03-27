from app_model.types import Action, KeyBindingRule, KeyCode, MenuRule

import varda
from varda._actions._menu_ids import MenuId, MenuGroup
from varda.common.observable_list import ImageList


def loadDummyImage(images: ImageList) -> None:
    images.append(varda.utilities.debug.generate_random_image())


DEBUG_ACTIONS: list[Action] = [
    Action(
        id="varda.debug.load_dummy_image",
        title="Load Dummy Image",
        icon="fa6-solid:bug",
        callback=loadDummyImage,
        menus=[MenuRule(id=MenuId.DEBUG, group=MenuGroup.DEBUG_TESTING, order=1)],
        keybindings=[KeyBindingRule(primary=KeyCode.F11)],
    ),
]
