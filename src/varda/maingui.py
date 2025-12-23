from pathlib import Path
import logging
from typing import Optional

from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, pyqtSlot

from varda.common.ui import DetachableTabWidget
from varda.project import ProjectContext

from varda.workspaces import GeneralImageAnalysisWorkflow
from varda.image_processing.process_controls.processingmenu import ProcessingMenu
from varda.image_processing.process_controls.processdialog import ProcessDialog
from varda.workspaces.dual_image_view.dual_image_view import DualImageView
from varda.workspaces.dual_image_view.dual_image_types import DualImageMode
from varda.workspaces.dual_image_view.dual_image_selection_dialog import (
    DualImageSelectionDialog,
)
from varda.all_images_view_list import all_images_view_list

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self, app, menubar, statusbar):
        super().__init__()

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("resources/logo.svg"))
        self.setMenuBar(menubar)
        self.setStatusBar(statusbar)
        self.app = app
        self.proj = app.proj
        self.selectedImage = None
        self.imageList = None
        self.rasterViews = {}  # image index -> RasterView

        # Track all open windows
        self.childWindows = []  # List of all child windows/widgets we need to track

        # Dual image view support
        self.dualImageView: Optional[DualImageView] = None
        self.dualImageDock: Optional[QtWidgets.QDockWidget] = None
        self.initUI()
        self.connectSignals()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = all_images_view_list.newList(self.app.images, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        self.centralTabs = DetachableTabWidget(self)
        self.setCentralWidget(self.centralTabs)
        # # Starting screen label
        # startingScreen = QtWidgets.QLabel(
        #     "Go to File->Import to open your first image!", parent=self
        # )
        # startingScreen.setStyleSheet("font-size: 20px;")
        # startingScreen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.setCentralWidget(startingScreen)

    def newDock(self, title, widget, dockArea):
        dock = QtWidgets.QDockWidget(title, self)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)
        self.addDockWidget(dockArea, dock)
        return dock

    def connectSignals(self):
        self.imageList.itemClicked.connect(self.onSelectedImageChanged)

        self.proj.sigDataChanged[
            int, ProjectContext.ChangeType, ProjectContext.ChangeModifier
        ].connect(self.onProjectDataChanged)

    def onSelectedImageChanged(self, item):
        if item is None:
            self.selectedImage = None
            return

        index = self.imageList.row(item)

        self.selectedImage = self.app.images[index]

        logger.debug(
            f"Selected new image: {self.selectedImage.metadata.name} (index {self.selectedImage.index})"
        )

    def showDualImageSelectionDialog(self):
        """Show dialog to select images for dual view"""
        try:
            # Create and show selection dialog
            dialog = DualImageSelectionDialog(self.proj, self)

            # Set current image as default primary if one is selected
            if hasattr(self, "selectedImage") and self.selectedImage is not None:
                dialog.set_default_images(primary_index=self.selectedImage.index)

            # Show the dialog
            result = dialog.exec()

            if result == QtWidgets.QDialog.DialogCode.Accepted:
                # Get the selected images using the correct method
                primary_index, secondary_index = dialog.get_selected_images()
                config = dialog.get_configuration()

                if primary_index is not None and secondary_index is not None:
                    # Set the selected images in dual view
                    if hasattr(self, "dual_view") and self.dual_view:
                        success_primary = self.dual_view.set_primary_image(
                            primary_index
                        )
                        success_secondary = self.dual_view.set_secondary_image(
                            secondary_index
                        )

                        if success_primary and success_secondary:
                            logger.info(
                                f"Images selected for dual view: {primary_index} and {secondary_index}"
                            )

                            # Apply the configuration from the dialog
                            self._apply_dual_image_config(config)

                            # Auto-link the images
                            if not self.dual_view._is_linked:
                                self.dual_view._toggle_link()

                            logger.info("Images linked for dual view")

                        else:
                            QtWidgets.QMessageBox.warning(
                                self,
                                "Selection Error",
                                "Failed to set one or both selected images.",
                            )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self, "Error", "Dual view not available."
                        )
                else:
                    QtWidgets.QMessageBox.information(
                        self,
                        "No Selection",
                        "Please select both primary and secondary images.",
                    )
            else:
                logger.debug("Dual image selection dialog was canceled")

        except ImportError as e:
            logger.error(f"Failed to import DualImageSelectionDialog: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Import Error",
                "Could not load the image selection dialog. Please check the dual image view module.",
            )
        except Exception as e:
            logger.error(f"Error showing dual image selection dialog: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while opening the image selection dialog: {str(e)}",
            )

    def linkSelectedImages(self):
        """Link two selected images for dual view"""
        selected_items = self.imageList.selectedItems()

        if len(selected_items) != 2:
            QtWidgets.QMessageBox.information(
                self,
                "Link Images",
                "Please select exactly 2 images in the image list to link.",
            )
            return

        # Get indices of selected images
        indices = []
        for item in selected_items:
            index = self.imageList.row(item)
            indices.append(index)

        # Show configuration dialog with pre-selected images
        dialog = DualImageSelectionDialog(self.proj, self)
        dialog.set_default_images(primary_index=indices[0], secondary_index=indices[1])

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            primary_index, secondary_index = dialog.get_selected_images()
            config = dialog.get_configuration()

            # Create dual image view if it doesn't exist
            if self.dualImageView is None:
                self.dualImageView = DualImageView(self.proj, self)

                # Create dock widget
                self.dualImageDock = QtWidgets.QDockWidget("Dual Image View", self)
                self.dualImageDock.setWidget(self.dualImageView)
                self.dualImageDock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

                # Add to bottom area by default
                self.addDockWidget(
                    Qt.DockWidgetArea.BottomDockWidgetArea, self.dualImageDock
                )

                # Connect dual image view signals
                self.dualImageView.primary_image_changed.connect(
                    self._onDualImagePrimaryChanged
                )
                self.dualImageView.secondary_image_changed.connect(
                    self._onDualImageSecondaryChanged
                )
                self.dualImageView.link_toggled.connect(self._onDualImageLinkToggled)

                # Track the dock
                self.childWindows.append(self.dualImageDock)

            # Set up the images and configuration
            self.dualImageView.set_primary_image(primary_index)
            self.dualImageView.set_secondary_image(secondary_index)
            self._apply_dual_image_config(config)

            # Auto-link
            if not self.dualImageView._is_linked:
                self.dualImageView._toggle_link()

            # Show the dock
            self.dualImageDock.show()
            self.dualImageDock.raise_()

    def unlinkSelectedImages(self):
        """Unlink selected images"""
        if self.dualImageView and self.dualImageView._is_linked:
            self.dualImageView._toggle_link()
        else:
            QtWidgets.QMessageBox.information(
                self, "Unlink Images", "No images are currently linked."
            )

    def closeDualImageView(self):
        """Close and cleanup dual image view"""
        if self.dualImageView:
            self.dualImageView.clear_images()

        if self.dualImageDock:
            self.dualImageDock.close()
            if self.dualImageDock in self.childWindows:
                self.childWindows.remove(self.dualImageDock)

        self.dualImageView = None
        self.dualImageDock = None

    def _onDualImagePrimaryChanged(self, index):
        """Handle primary image change in dual view"""
        logger.debug(f"Dual view primary image changed to {index}")
        # Could update UI state here if needed

    def _onDualImageSecondaryChanged(self, index):
        """Handle secondary image change in dual view"""
        logger.debug(f"Dual view secondary image changed to {index}")
        # Could update UI state here if needed

    def _onDualImageLinkToggled(self, is_linked):
        """Handle dual image link toggle"""
        if is_linked:
            logger.info("Images linked for dual view")
        else:
            logger.info("Images unlinked from dual view")

    def _apply_dual_image_config(self, config):
        """Apply configuration from dialog to dual view"""
        try:
            if (
                hasattr(self, "dual_view")
                and self.dual_view
                and self.dual_view.controller
            ):
                controller = self.dual_view.controller

                # Apply display mode
                controller.set_display_mode(config.mode)

                # Apply overlay settings
                if config.mode == DualImageMode.OVERLAY:
                    controller.set_overlay_opacity(config.overlay_opacity)

                # Apply blink settings
                if config.mode == DualImageMode.BLINK:
                    controller.set_blink_interval(config.blink_interval)

                # Apply sync settings
                if hasattr(self.dual_view, "sync_navigation_cb"):
                    self.dual_view.sync_navigation_cb.setChecked(config.sync_navigation)
                if hasattr(self.dual_view, "sync_rois_cb"):
                    self.dual_view.sync_rois_cb.setChecked(config.sync_rois)

                logger.debug("Applied dual image configuration")

        except Exception as e:
            logger.error(f"Error applying dual image config: {e}")

    def openProcessingMenu(self):
        """Open the image processing menu for the currently selected image."""
        if self.selectedImage is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Image Selected",
                "Please select an image before opening the processing menu.",
            )
            return

        # Create processing menu
        processingMenu = ProcessingMenu(self)

        def onProcessFinished():
            """Handle when an image process finishes - refresh the image list."""
            logger.info("Image processing completed!")

        # Connect menu actions to process execution
        def handle_process_action(action):
            # Find process class by action text
            process_class = action.data()
            if process_class is not None:
                # Create process dialog with proper parent and project context
                processDialog = ProcessDialog(self.selectedImage)
                processDialog.setParent(self)  # Ensure proper parent chain
                processDialog.project_context = self.proj  # Direct assignment
                processDialog.sigProcessFinished.connect(onProcessFinished)
                processDialog.openProcessControlMenu(process_class)

        processingMenu.triggered.connect(handle_process_action)

        # Show menu at cursor position
        cursor_pos = QCursor.pos()
        processingMenu.exec(cursor_pos)

    @pyqtSlot(int, ProjectContext.ChangeType, ProjectContext.ChangeModifier)
    def onProjectDataChanged(self, index, changeType, changeModifier):
        """Handle when project data changes (like new images being added)."""
        logger.debug(
            f"Project data changed: index={index}, type={changeType}, modifier={changeModifier}"
        )
        if (
            changeType == self.proj.ChangeType.IMAGE
            and changeModifier == self.proj.ChangeModifier.ADD
        ):
            image = self.proj.getImage(index)
            self.centralTabs.addTab(
                GeneralImageAnalysisWorkflow(image), image.metadata.name
            )

    def addTab(self, widget, title=None):
        """Add a new tab to the central tab widget."""
        self.childWindows.append(widget)
        self.centralTabs.addTab(widget, title)

    def closeAllChildWindows(self):
        """Close all child windows before shutting down."""
        # Close all tracked child windows
        for window in self.childWindows[
            :
        ]:  # Use a copy of the list since it will be modified during iteration
            if window and window.isVisible():
                window.close()

        # Clear tracking lists
        self.childWindows.clear()

        logger.info("All child windows closed")

    def closeEvent(self, event):
        """Handle the window close event to ensure proper cleanup."""
        logger.info("Main window close event triggered")

        # Close all child windows first
        self.closeAllChildWindows()

        # Accept the close event to allow the window to close
        event.accept()

    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.proj.loadNewImage(str(Path(event.mimeData().urls()[0].toLocalFile())))
