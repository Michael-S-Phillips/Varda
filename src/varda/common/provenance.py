"""The provenance record kept in a result's metadata (written by
``analysis.provenance.recordProvenance``) and its one-line form for file
descriptions. Qt-free, so the readers and writers can use it."""

from __future__ import annotations

from collections.abc import Mapping

PROVENANCE_KEY = "provenance"


def provenanceText(image) -> str:
    """One line for a file description, or "" when the image has no record."""
    metadata: Mapping = image.extraMetadata
    record = metadata.get(PROVENANCE_KEY)
    if not record:
        return ""
    parameters = ", ".join(
        f"{name}={value}" for name, value in record.get("parameters", {}).items()
    )
    inputs = ", ".join(i.get("path") or i["name"] for i in record.get("inputs", []))
    return (
        f"Made with Varda {record['vardaVersion']}: {record['analysis']} "
        f"({parameters}) from {inputs} on {record['created']}"
    )
