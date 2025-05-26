import logging

from core.data import ProjectContext
from features.image_view_metadata.metadata_editor import MetadataEditor

logger = logging.getLogger(__name__)


def openMetadataEditor(proj: ProjectContext, imageIndex, parent):
    """
    Opens the metadata editor for the specified image.

    Args:
        proj: The project context.
        imageIndex: The image index.

    Returns:
        bool: True if the metadata was updated, False otherwise.
    """

    editor = MetadataEditor(proj, imageIndex, parent)
    editor.exec()
