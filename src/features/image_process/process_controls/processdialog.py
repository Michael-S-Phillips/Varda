from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QDialog, QMessageBox

import core.utilities as utils
from core.data import ProjectContext


class ProcessDialog(QDialog):
    """Dialog box that can dynamically generate parameter controls for an image
    process and create new images in the workspace.
    """

    sigProcessFinished = QtCore.pyqtSignal()

    def __init__(self, image=None):
        super().__init__()
        self.image = image
        self.current_dialog = None
        self.proj = self._getProjectContext()

    def openProcessControlMenu(self, process):
        if self.current_dialog:
            self.current_dialog.close()
            
        self.current_dialog = QtWidgets.QDialog()
        self.current_dialog.setWindowTitle(process.name)
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(10)
        self.current_dialog.setLayout(layout)

        # Store parameter widgets
        self.parameter_widgets = {}

        for name, details in process.parameters.items():
            paramName = QtWidgets.QLabel()
            paramName.setText(name)
            paramName.setToolTip(details["description"])

            if details["type"] == float:
                lineEdit = QtWidgets.QDoubleSpinBox()
                lineEdit.setValue(details["default"])
                lineEdit.setDecimals(2)
                if "min" in details and "max" in details:
                    lineEdit.setRange(details["min"], details["max"])
                self.parameter_widgets[name] = lineEdit
                layout.addRow(paramName, lineEdit)
                
            elif details["type"] == bool:
                lineEdit = QtWidgets.QCheckBox()
                lineEdit.setChecked(details["default"])
                self.parameter_widgets[name] = lineEdit
                layout.addRow(paramName, lineEdit)

        layout.addItem(
            QtWidgets.QSpacerItem(
                0,
                20,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        )
        executeButton = QtWidgets.QPushButton("Execute")
        executeButton.clicked.connect(lambda: self.processImage(process))
        layout.addWidget(executeButton)
        layout.addItem(
            QtWidgets.QSpacerItem(
                60,
                0,
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Minimum,
            )
        )
        self.current_dialog.exec()

    def processImage(self, process):
        """Execute the image process and create a new image."""
        if self.image is None:
            return
            
        try:
            # Import dataclasses for copying metadata
            from dataclasses import replace
            
            # Get parameter values
            kwargs = {}
            for param_name, widget in self.parameter_widgets.items():
                if isinstance(widget, QtWidgets.QDoubleSpinBox):
                    kwargs[param_name] = widget.value()
                elif isinstance(widget, QtWidgets.QCheckBox):
                    kwargs[param_name] = widget.isChecked()
            
            # Close the dialog first
            if self.current_dialog:
                self.current_dialog.accept()
            
            # Create and execute the process directly
            process_instance = process()
            
            # Execute process with image raster data
            processed_raster = process_instance.execute(self.image.raster, **kwargs)
            
            # Create new metadata using dataclasses.replace
            # this might need updated in the future to replace other fields as well
            original_name = self.image.metadata.name or "Image"
            new_metadata = replace(
                self.image.metadata,
                name=f"{original_name} - {process.name}"
            )
            
            # Get the project context from the image
            project_context = self._getProjectContext()
            if project_context:
                # Create new image in the project
                new_index = project_context.createImage(
                    raster=processed_raster,
                    metadata=new_metadata
                )
                
                QMessageBox.information(
                    self,
                    "Process Complete",
                    f"{process.name} completed successfully!\n"
                    f"New image created: {new_metadata.name}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Could not add processed image to workspace. "
                    "Processing completed but image may not appear in the list."
                )
            
            # Emit signal that processing is finished
            self.sigProcessFinished.emit()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Process Error", 
                f"Error executing {process.name}:\n{str(e)}"
            )

    def _getProjectContext(self):
        """Get the project context from the parent widget chain."""
        # Walk up the parent chain to find the MainGUI window
        parent = self.parent()
        while parent:
            if hasattr(parent, 'proj'):
                return parent.proj
            parent = parent.parent()
        return None