"""Export Image: pick an image and a destination, then write it."""

import numpy as np

from varda.image_loading.export_image_dialog import ExportImageDialog
from varda.image_loading.image_loading_service import openDataSource
from varda.utilities.debug import generate_random_image


def test_dialog_preselects_the_given_image_and_suggests_its_name(qtbot):
    first, second = (
        generate_random_image((20, 20, 10)),
        generate_random_image((20, 20, 10)),
    )
    dialog = ExportImageDialog([first, second], image=second)
    qtbot.addWidget(dialog)

    assert dialog.selectedImage() is second
    assert dialog.pathEdit.text().endswith(f"{second.name}.img")


def test_export_is_disabled_without_a_path(qtbot):
    image = generate_random_image((20, 20, 10))
    dialog = ExportImageDialog([image], image=image)
    qtbot.addWidget(dialog)

    dialog.pathEdit.setText("")
    assert not dialog.exportButton.isEnabled()
    dialog.pathEdit.setText("/tmp/x.img")
    assert dialog.exportButton.isEnabled()


def test_accepting_writes_the_image_and_reports_the_path(qtbot, tmp_path):
    image = generate_random_image((20, 20, 10))
    dialog = ExportImageDialog([image], image=image)
    qtbot.addWidget(dialog)
    target = tmp_path / "exported.img"
    dialog.pathEdit.setText(str(target))

    with qtbot.waitSignal(dialog.sigExported, timeout=10_000) as blocker:
        dialog.accept()

    assert blocker.args == [image, str(target)]
    loaded = openDataSource(str(target))
    np.testing.assert_array_equal(loaded.readAllBands(), np.asarray(image.getData()))
