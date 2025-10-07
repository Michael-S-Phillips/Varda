# src/varda/infra/persistence/project_io.py
"""
Handles I/O for persistent project storage, via JSON format.

Eventually, if we want to support other storage setups (e.g. an SQL database, or a custom binary format)
Then we just create a Protocol for ProjectIO, and pass the implementation we want into the ProjectContext.
"""
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Protocol

import numpy as np

from varda.project.project_entity import Project

logger = logging.getLogger(__name__)


class ProjectIO(Protocol):
    """
    Protocol for project I/O handlers. Implementations must provide save and load methods.
    """

    def save(self, data: Project) -> bool:
        """Save project data to a file."""
        ...

    def load(self, filePath: Path) -> tuple[bool, Project | None]:
        """Load project data from a file."""
        ...


class ProjectJsonIO:
    """
    JSON-based implementation of ProjectIO.
    """

    def save(self, project: Project) -> bool:
        """
        Safely writes project data to disk.

        Args:
            project: The serialized project data to save.

        Returns:
            tuple: (bool, Path) - Success status and the path where the project was saved.
        """

        if project.path is None:
            logger.error("No save path provided and no current project path set.")
            return False

        # Write new data to a temp file, then replace the original file only if the write operation was successful.
        # This avoids losing data if the write operation fails somehow.
        try:
            filePath = project.path
            data = project.serialize()

            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=filePath.parent,
                prefix=filePath.name,
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                json.dump(data, temp_file, indent=4, cls=NumpyJSONEncoder)
                temp_file.flush()

            os.replace(temp_file.name, filePath)
            logger.info(f"Project saved to {filePath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project! {e}", exc_info=True)
            # Cleanup temp file
            if "temp_file" in locals() and Path(temp_file.name).exists():
                os.remove(temp_file.name)
            return False

    def load(self, filePath: Path) -> tuple[bool, Project | None]:
        """
        Load a project from a file.

        Args:
            filePath: Path to load the project from. If None, uses the current project path.

        Returns:
            tuple: (bool, dict, Path) - Success status, loaded data, and the path that was loaded.
        """

        if filePath is None:
            logger.error("No load path provided and no current project path set.")
            return False, None

        try:
            with open(filePath, "r") as file:
                data = json.load(file)
            logger.info(f"Loaded project from {filePath}")

            return True, Project.deserialize(data)
        except Exception as e:
            logger.error(f"Error loading project: {e}", exc_info=True)
            return False, None


class NumpyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy data types and bytes objects."""

    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj.resolve())
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return list(obj)
        return super().default(obj)
