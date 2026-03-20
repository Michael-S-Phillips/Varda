from app_model.types import Action, KeyBindingRule, KeyCode, KeyMod

ACTIONS: list[Action] = [
    Action(
        id="open",
        title="Open",
        icon="fa6-solid:folder-open",
        callback=open_file,
        menus=["File"],
        keybindings=[KeyBindingRule(primary=KeyMod.CtrlCmd | KeyCode.KeyO)],
    )
]
