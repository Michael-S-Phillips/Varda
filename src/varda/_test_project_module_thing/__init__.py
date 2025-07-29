"""
Workspace feature for Varda.

This feature provides functionality for managing project data, including
images, bands, stretches, and ROIs.
"""

from varda._test_project_module_thing.api import (
    WorkspaceService,
    WorkspaceChangeType,
    WorkspaceChangeModifier,
)

__all__ = ["WorkspaceService", "WorkspaceChangeType", "WorkspaceChangeModifier"]
