class IntParameter:
    def __init__(self, name, units, range, default):
        self.name = name
        self.units = units
        self.range = range
        self.default = default
        self.value = default

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class FloatParameter:
    def __init__(self, name, units, range, default):
        self.name = name
        self.units = units
        self.range = range
        self.default = default
        self.value = default

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class StringParameter:
    def __init__(self, name, default):
        self.name = name
        self.default = default
        self.value = default

    def set(self, value):
        self.value = value

    def get(self):
        return self.value
