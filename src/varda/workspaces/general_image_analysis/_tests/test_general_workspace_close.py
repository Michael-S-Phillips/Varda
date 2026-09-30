"""Closing a General Image Analysis workspace must not raise."""

from varda.utilities.debug import generate_random_image
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)


def test_close_runs_cleanly(qapp):
    workflow = GeneralImageAnalysisWorkflow(
        GeneralImageAnalysisConfig([generate_random_image((20, 20, 10))])
    )
    assert workflow.close() is True
