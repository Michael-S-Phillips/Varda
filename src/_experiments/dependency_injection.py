import in_n_out as ino


class Thing:
    def __init__(self, name: str):
        self.name = name


# use ino.inject to create a version of the function
# that will retrieve the required dependencies at call time
@ino.inject
def func(thing: Thing):
    return thing.name


def give_me_a_thing() -> Thing:
    return Thing("Thing")


# register a provider of Thing
ino.register_provider(give_me_a_thing)
print(func())  # prints "Thing"


def give_me_another_thing() -> Thing:
    return Thing("Another Thing")


with ino.register_provider(give_me_another_thing, weight=10):
    print(func())  # prints "Another Thing"
