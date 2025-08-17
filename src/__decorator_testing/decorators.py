from typing import Protocol, runtime_checkable, Callable, Type, List
from pydantic import BaseModel, validate_call, field_validator, ConfigDict


def storeInProject(func):
    def wrapper(*args, **kwargs):
        print(f"In wrapper: {args} {kwargs}")
        return func(*args, **kwargs)

    return wrapper


class Image(BaseModel):
    name: str


class Metadata(BaseModel):
    name: str


class ImageLoader(BaseModel):
    name: str
    fileExtensions: List[str]
    loadMetadata: Callable[[str], Metadata]
    loadImage: Callable[[str], Image]


# Original protocol idea
image_loaders = []


class LoaderProtocol(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def fileExtensions(self) -> List[str]: ...
    def loadImage(self, path: str = "") -> Image: ...
    def loadMetadata(self, path: str = "") -> Metadata: ...


def register_loader(loader: Type[LoaderProtocol]):
    loaderInstance = loader()
    imageLoader = ImageLoader(
        name=loaderInstance.name,
        fileExtensions=loaderInstance.fileExtensions,
        loadImage=loaderInstance.loadImage,
        loadMetadata=loaderInstance.loadMetadata,
    )
    image_loaders.append(imageLoader)
    print("Loader registered!:", loaderInstance.name)
    print("Loader Base Model Instance:", imageLoader)
    # no need to actually wrap it, at least not for now
    return loader


def register(name, fileExtensions, loadImage, loadMetadata):
    pass


@register_loader
class PNGLoader:
    name = "PNG Loader"
    fileExtensions = [".png"]

    @classmethod
    def loadImage(cls, path: str = "") -> Image:
        print("PNGLoader loadImage called. path:", path)
        return Image(name="ImageFromPNG")

    @classmethod
    def loadMetadata(cls, path: str = "") -> Metadata:
        print("PNGLoader loadMetadata called. path:", path)
        return Metadata(name="MetadataFromPNG")


# Other, potential function-based idea
image_loader_functions = {}


def register_loader_func(loaderName: str, fileExtensions: List[str]):
    def decorator(loader: Callable[[str], Image]):
        # not sure how I can validate the signature of the loader function at runtime. This commented out code didnt work
        # if not loader is Callable[[str], Image]:
        #     raise TypeError(
        #         "Loader must match expected signature: (path: str) -> Image"
        #     )
        # maybe add the extensions as an attribute of the function?
        setattr(loader, "fileExtensions", fileExtensions)
        image_loader_functions[loaderName] = loader
        print("Loader registered!:", loaderName)

        return loader

    return decorator


@register_loader_func("My Loader Function", [".jpg", ".jpeg"])
def JPGLoaderFunction(path: str) -> Image:
    print("Loader Function called. path:", path)
    return Image(name="ImageFromFunction")


if __name__ == "__main__":
    print(image_loaders)
    # print(image_loader_functions)
