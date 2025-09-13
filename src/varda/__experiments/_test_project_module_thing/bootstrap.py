"""
Bootstrap for the _test_project_module_thing feature.

This module provides functions for initializing the _test_project_module_thing feature.
"""

import logging

from varda._test_project_module_thing.api import WorkspaceService
from varda._test_project_module_thing.implementation import WorkspaceServiceImpl
from varda._test_project_module_thing.infrastructure import ProjectJsonIO

logger = logging.getLogger(__name__)


def create_workspace_service() -> WorkspaceService:
    """
    Create and initialize the _test_project_module_thing service.

    This function creates a new instance of the _test_project_module_thing service with
    all necessary dependencies.

    Returns:
        WorkspaceService: The initialized _test_project_module_thing service.
    """
    # Create the project I/O handler
    project_io = ProjectJsonIO()

    # Create the _test_project_module_thing service
    workspace_service = WorkspaceServiceImpl(project_io)

    logger.info("Workspace service initialized")
    return workspace_service


def register_workspace_service(
    registry, image_loading_service=None, roi_service=None
) -> None:
    """
    Register the _test_project_module_thing service in the service registry.

    This function creates a new instance of the _test_project_module_thing service and
    registers it in the service registry.

    Args:
        registry: The service registry.
        image_loading_service: Optional image loading service.
        roi_service: Optional ROI service.
    """
    # Create the _test_project_module_thing service
    workspace_service = create_workspace_service()

    # Set dependencies
    if image_loading_service is not None:
        workspace_service.set_image_loading_service(image_loading_service)

    if roi_service is not None:
        workspace_service.set_roi_service(roi_service)

    # Register the service
    registry.register("workspace_service", workspace_service)

    logger.info("Workspace service registered")
