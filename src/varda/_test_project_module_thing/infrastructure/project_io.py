"""
Handles I/O for persistent project storage, via JSON format.

This module provides classes for saving and loading project data to/from disk.
"""
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Protocol, Tuple, Optional

import numpy as np

from varda.common.domain import Project

logger = logging.getLogger(__name__)


class ProjectIO(Protocol):
    """
    Protocol for project I/O handlers. Implementations must provide save and load methods.
    """

    def save(self, project: Project) -> bool:
        """Save project data to a file."""
        ...

    def load(self, file_path: Path) -> Tuple[bool, Optional[Project]]:
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
            project: The project to save.

        Returns:
            bool: True if the save was successful.
        """

        if project.path is None:
            logger.error("No save path provided and no current project path set.")
            return False

        # Write new data to a temp file, then replace the original file only if the write operation was successful.
        # This avoids losing data if the write operation fails somehow.
        try:
            file_path = project.path
            data = project.serialize()

            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=file_path.parent,
                prefix=file_path.name,
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                json.dump(data, temp_file, indent=4, cls=NumpyJSONEncoder)
                temp_file.flush()

            os.replace(temp_file.name, file_path)
            logger.info(f"Project saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project! {e}")
            # Cleanup temp file
            if "temp_file" in locals() and Path(temp_file.name).exists():
                os.remove(temp_file.name)
            return False

    def load(self, file_path: Path) -> Tuple[bool, Optional[Project]]:
        """
        Load a project from a file.

        Args:
            file_path: Path to load the project from.

        Returns:
            Tuple[bool, Optional[Project]]: Success status and the loaded project.
        """

        if file_path is None:
            logger.error("No load path provided.")
            return False, None

        try:
            with open(file_path, "r") as file:
                data = json.load(file)
            logger.info(f"Loaded project from {file_path}")

            # Create a new Project instance and deserialize the data
            project = Project()
            project = project.deserialize(data)
            return True, project
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            return False, None


class NumpyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy data types and bytes objects."""

    def default(self, obj):
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