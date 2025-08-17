from dataclasses import dataclass


@dataclass
class _Wavelength:
    name: str | float
    index: int


@dataclass
class _Image:
    name: str
    wavelengths: list[_Wavelength]
