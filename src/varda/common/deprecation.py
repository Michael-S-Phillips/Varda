"""One way to retire an API: warn with the version it was deprecated in.

Varda's own tests turn these warnings into errors (pyproject.toml), so Varda
never calls what it has deprecated; plugins see the warning and have time to
move. Record each deprecation in CHANGELOG.md.
"""

import warnings


class VardaDeprecationWarning(DeprecationWarning):
    """A Varda API that will be removed."""


def warnDeprecated(name: str, *, since: str, instead: str, stacklevel: int = 2) -> None:
    """Warn that ``name`` is deprecated since Varda ``since``; use ``instead``.

    ``stacklevel`` counts from the caller of ``warnDeprecated``: the default
    blames whoever called the deprecated function."""
    warnings.warn(
        f"{name} is deprecated since Varda {since} and will be removed; "
        f"use {instead} instead.",
        VardaDeprecationWarning,
        stacklevel=stacklevel + 1,
    )
