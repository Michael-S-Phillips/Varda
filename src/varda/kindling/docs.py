"""What the model reads to write a plugin: the authoring guide, a reference
for ``varda.api`` generated from the module itself (so it can't drift), and
the example plugins. All bundled with the app (``docs/plugins``)."""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path

import varda.api
from varda.utilities.resources import resource_path

PLUGIN_DOCS = Path(resource_path("docs/plugins"))
GUIDE = PLUGIN_DOCS / "authoring.md"
EXAMPLES = PLUGIN_DOCS / "examples"
EXAMPLE_SUFFIXES = (".py", ".toml", ".md")
INTERNAL_MEMBERS = {"clone"}  # ParameterGroup machinery plugins never call


def authoringGuide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def _signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return ""


def _doc(obj) -> str:
    return inspect.cleandoc(obj.__doc__) if obj.__doc__ else ""


def _indented(text: str, prefix: str) -> str:
    return textwrap.indent(text, prefix) if text else ""


def _describeClass(cls: type) -> str:
    """The class's signature and docstring, then its public methods and
    properties (all of them for Analysis, the base plugins subclass)."""
    lines = [f"class {cls.__name__}{_signature(cls)}", _indented(_doc(cls), "  ")]
    for name, member in inspect.getmembers(cls):
        if name.startswith("_") or name in INTERNAL_MEMBERS:
            continue
        if inspect.isfunction(member) or inspect.ismethod(member):
            ownClass = member.__qualname__.split(".")[0] == cls.__name__
            if not ownClass and cls is not varda.api.Analysis:
                continue
            lines.append(f"  def {name}{_signature(member)}")
            lines.append(_indented(_doc(member), "      "))
        elif isinstance(member, property):
            doc = _doc(member)
            lines.append(
                f"  {name}: property" + (f"  # {doc.splitlines()[0]}" if doc else "")
            )
    if cls is varda.api.Analysis:
        lines.append("  # class attributes a subclass sets:")
        lines += [
            f"  {name} = {value!r}"
            for name, value in vars(cls).items()
            if not name.startswith("_")
            and not callable(value)
            and not isinstance(value, (classmethod, staticmethod))
        ]
    return "\n".join(line for line in lines if line)


def apiReference() -> str:
    """Every name ``varda.api`` exports, with its signature and docstring."""
    parts = [_doc(varda.api)]
    for name in varda.api.__all__:
        obj = getattr(varda.api, name)
        if inspect.isclass(obj):
            parts.append(_describeClass(obj))
        elif callable(obj):
            parts.append(
                f"def {name}{_signature(obj)}\n{_indented(_doc(obj), '  ')}".rstrip()
            )
        else:
            parts.append(f"{name} = {obj!r}")
    return "\n\n".join(parts)


def exampleNames() -> list[str]:
    return sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir())


def readExample(name: str) -> str:
    """Every source file of an example plugin, each under its path."""
    folder = EXAMPLES / name
    if name not in exampleNames():
        raise ValueError(
            f"No example called {name!r}; examples: {', '.join(exampleNames())}"
        )
    files = sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix in EXAMPLE_SUFFIXES and "__pycache__" not in p.parts
    )
    return "\n\n".join(
        f"--- {p.relative_to(folder)} ---\n{p.read_text(encoding='utf-8')}"
        for p in files
    )
