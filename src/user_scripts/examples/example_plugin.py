import src.api as varda_api


class ExamplePlugin(varda_api.VPlugin):
    """
    Example plugin that demonstrates how to create a simple plugin for Varda.
    This plugin does not add any functionality but serves as a template.
    """
    name = "ExamplePlugin"
    description = "This is an example plugin for Varda. It does not add any functionality but serves as a template."
    def __init__(self):
        super().__init__()

    def run(self):
        pass