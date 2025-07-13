from pathlib import Path
import logging
from typing import Dict, Optional

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, pyqtSlot

from varda.core.data import ProjectContext

# from varda.core.ui import ControlPanel
from varda.features.image_view_raster.raster_view import RasterView
from varda.features.workspaces import GeneralImageAnalysisWorkflow
from varda.gui.widgets import StatusBar, MainMenuBar
from varda.app.process_controls.processingmenu import ProcessingMenu
from varda.app.process_controls.processdialog import ProcessDialog
from varda.features.dual_image_view.dual_image_view import DualImageView
from varda.features.dual_image_view.dual_image_types import DualImageMode
from varda.features import (
    image_view_raster,
    image_view_roi,
    all_images_view_list,
)
import varda.core.utilities.debug as debug
from varda.gui.widgets.detachable_tab_widget import DetachableTabWidget

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self, proj: ProjectContext):
        super().__init__()

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("img/logo.svg"))

        self.proj = proj
        self.selectedImage = None
        self.imageList = None
        # self.currControlPanel = None
        # self.controlPanels: Dict[int, ControlPanel] = {}  # image index -> ControlPanel
        self.rasterViews: Dict[int, RasterView] = {}  # image index -> RasterView
        self.roiViews = {}

        # Track all open windows
        self.childWindows = []  # List of all child windows/widgets we need to track
        self.pixelPlotWindows = []  # Track all pixel plot windows specifically

        #  Dual image view support
        self.dualImageView: Optional[DualImageView] = None
        self.dualImageDock: Optional[QtWidgets.QDockWidget] = None
        self.initUI()
        self.connectSignals()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setMenuBar(MainMenuBar())
        self.setStatusBar(StatusBar(self.proj))

        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = all_images_view_list.newList(self.proj, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        # Raster container
        self.rasterContainer = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.rasterContainer)

        self.centralTabs = DetachableTabWidget(self)
        self.setCentralWidget(self.centralTabs)
        # Starting screen label
        self.startingScreen = self.getStartingScreenWidget()
        self.rasterContainer.addWidget(self.startingScreen)

    def getStartingScreenWidget(self):
        label = QtWidgets.QLabel(
            "Go to File->Import to open your first image!", parent=self
        )
        label.setStyleSheet("font-size: 20px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def newDock(self, title, widget, dockArea):
        dock = QtWidgets.QDockWidget(title, self)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)
        self.addDockWidget(dockArea, dock)
        return dock

    def connectSignals(self):
        self.menuBar().sigImportFile.connect(self.proj.loadNewImage)
        self.menuBar().sigExitApp.connect(self.exitApp)
        self.menuBar().sigSaveProject.connect(self.proj.saveProject)
        self.menuBar().sigOpenProject.connect(self.proj.loadProject)
        self.menuBar().sigDumpProjectData.connect(
            lambda: debug.ProjectContextDataTable(self.proj, self)
        )

        # TODO: Make this less hacky lol
        self.menuBar().sigLoadDebugProject.connect(
            lambda: self.proj.loadProject(Path("../../debugProj.varda").resolve())
        )

        self.menuBar().sigOpenProcessingMenu.connect(self.openProcessingMenu)

        # NEW: Connect dual image signals
        self.menuBar().sigOpenDualImageView.connect(self.openDualImageView)
        self.menuBar().sigLinkSelectedImages.connect(self.linkSelectedImages)
        self.menuBar().sigUnlinkSelectedImages.connect(self.unlinkSelectedImages)

        self.imageList.itemClicked.connect(self.onSelectedImageChanged)

        self.proj.sigDataChanged[
            int, ProjectContext.ChangeType, ProjectContext.ChangeModifier
        ].connect(self.onProjectDataChanged)

    def onSelectedImageChanged(self, item):
        if item is None:
            self.selectedImage = None
            return

        index = self.imageList.row(item)

        self.selectedImage = self.proj.getImage(index)

        print(
            f"[DEBUG] Selected new image: {self.selectedImage.metadata.name} (index {self.selectedImage.index})"
        )

        # Raster View
        # rasterView = self.showRasterView(index)

        # Control Panel
        # if self.currControlPanel:
        #     self.currControlPanel.tabsDock.hide()

        # if index not in self.controlPanels:
        #     panel = ControlPanel(self.proj, index, rasterView)
        #     # panel.updateActiveImage(self.selectedImage.index)
        #     self.controlPanels[index] = panel
        #     self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, panel.tabsDock)
        # else:
        #     panel = self.controlPanels[index]
        #
        # # Update the active image display
        # panel.updateActiveImage(index)
        #
        # self.currControlPanel = panel
        # panel.tabsDock.show()

        # Update any open ROI views
        self.updateAllROIViews(index)

    def showRasterView(self, index):
        print(f"[DEBUG] Showing RasterView for image {index}")
        for view in self.rasterViews.values():
            view.hide()

        if index not in self.rasterViews:
            view = image_view_raster.getRasterView(self.proj, index, self)
            logger.debug("New RasterView created!")
            self.rasterContainer.addWidget(view)
            self.rasterViews[index] = view
        else:
            view = self.rasterViews[index]

        self.rasterContainer.setCurrentWidget(view)
        view.show()

        return view

    # DUAL IMAGE METHODS
    def openDualImageView(self):
        """Open the dual image view dialog/dock"""
        if len(self.proj.getAllImages()) < 2:
            QtWidgets.QMessageBox.information(
                self,
                "Dual Image View",
                "You need at least 2 images loaded to use dual image view.",
            )
            return

        # Create dual view if it doesn't exist
        if not hasattr(self, "dual_view") or self.dual_view is None:
            # from features.dual_image_analysis.dual_image_analysis import DualImageView
            self.dual_view = DualImageView(self.proj)

            # Create and configure dock widget
            self.dual_view_dock = QtWidgets.QDockWidget("Dual Image View", self)
            self.dual_view_dock.setWidget(self.dual_view)
            self.dual_view_dock.setMinimumSize(800, 600)  # Ensure adequate size
            self.dual_view_dock.setFloating(False)  # Dock it properly

            # Add to right dock area
            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.dual_view_dock
            )

            # Store reference for cleanup
            if not hasattr(self, "childWindows"):
                self.childWindows = []
            self.childWindows.append(self.dual_view_dock)

            # Connect close event to cleanup
            self.dual_view_dock.destroyed.connect(
                lambda: (
                    self.removeChildWindow(self.dual_view_dock)
                    if hasattr(self, "removeChildWindow")
                    else None
                )
            )

        # Make sure everything is visible
        self.dual_view_dock.setVisible(True)
        self.dual_view_dock.show()
        self.dual_view_dock.raise_()  # Bring to front
        self.dual_view_dock.activateWindow()  # Give it focus

        # Ensure the dual view widget itself is visible
        self.dual_view.setVisible(True)
        self.dual_view.show()

        # Force updates to ensure proper display
        self.dual_view_dock.update()
        self.dual_view.update()

        # Process events to ensure visibility changes take effect
        from PyQt6.QtCore import QCoreApplication

        QCoreApplication.processEvents()

        # NOW: Open image selection dialog
        self.showDualImageSelectionDialog()

        logger.debug("Dual image view opened and made visible")

        return self.dual_view

    def showDualImageSelectionDialog(self):
        """Show dialog to select images for dual view"""
        try:
            from varda.features.dual_image_view.dual_image_selection_dialog import (
                DualImageSelectionDialog,
            )

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

        # Import here to avoid circular import
        from varda.features.dual_image_view.dual_image_view import DualImageView
        from varda.features.dual_image_view.dual_image_selection_dialog import (
            DualImageSelectionDialog,
        )

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

    # Add cleanup to exitApp method
    def exitApp(self):
        """Clean up and exit the application."""
        # Close dual image view
        if self.dualImageView:
            self.closeDualImageView()

        # Close all child windows
        for window in self.childWindows[
            :
        ]:  # Copy list to avoid modification during iteration
            try:
                window.close()
            except Exception as e:
                logger.warning(f"Error closing child window: {e}")

        # Close all pixel plot windows
        for window in self.pixelPlotWindows[:]:
            try:
                window.close()
            except Exception as e:
                logger.warning(f"Error closing pixel plot window: {e}")

        self.close()

    # TODO: Delete?
    def openROIView(self, image_index):
        """Open ROI view and properly connect it to RasterView"""
        print(f"[DEBUG] openROIView called with index: {image_index}")
        view = image_view_roi.getROIView(self.proj, image_index, self)

        # Set raster view reference if available
        if image_index in self.rasterViews:
            raster_view = self.rasterViews[image_index]
            view.viewModel.setRasterView(raster_view)

            # Connect signals/slots for updates in both directions
            if hasattr(view, "roiSelectionChanged"):
                view.roiSelectionChanged.connect(
                    lambda roi_index: (
                        raster_view.highlightROI(roi_index)
                        if hasattr(raster_view, "highlightROI")
                        else None
                    )
                )

        dock = QtWidgets.QDockWidget("ROI Table", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

        # Store the view and track the dock widget
        self.childWindows.append(dock)
        if not hasattr(self, "roiViews"):
            self.roiViews = {}
        self.roiViews[image_index] = view

        # Connect close event to remove from tracking when dock is closed
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

        return view

    def removeChildWindow(self, window):
        """Remove a window from tracking when it's closed."""
        if window in self.childWindows:
            self.childWindows.remove(window)
            logger.debug(
                f"Removed window from tracking. Remaining windows: {len(self.childWindows)}"
            )

    def updateAllROIViews(self, current_image_index):
        """Update all open ROI views to show data for the current image."""
        for window in self.childWindows:
            if hasattr(window, "widget") and window.widget():
                widget = window.widget()
                if hasattr(widget, "viewModel") and hasattr(
                    widget.viewModel, "updateImageIndex"
                ):
                    widget.viewModel.updateImageIndex(current_image_index)

                    # Update raster view reference if available
                    if (
                        hasattr(widget.viewModel, "setRasterView")
                        and current_image_index in self.rasterViews
                    ):
                        widget.viewModel.setRasterView(
                            self.rasterViews[current_image_index]
                        )

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

        # Connect menu actions to process execution
        def handle_process_action(action):
            # Find process class by action text
            process_class = action.data()
            if process_class is not None:
                # Create process dialog with proper parent and project context
                processDialog = ProcessDialog(self.selectedImage)
                processDialog.setParent(self)  # Ensure proper parent chain
                processDialog.project_context = self.proj  # Direct assignment
                processDialog.sigProcessFinished.connect(self.onProcessFinished)
                processDialog.openProcessControlMenu(process_class)

        processingMenu.triggered.connect(handle_process_action)

        # Show menu at cursor position
        cursor_pos = QCursor.pos()
        processingMenu.exec(cursor_pos)

    def onProcessFinished(self):
        """Handle when an image process finishes - refresh the image list."""
        print("Image processing completed!")

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
                GeneralImageAnalysisWorkflow(index), image.metadata.name
            )

        # if not hasattr(self, "testWorkflow"):
        #
        #     self.testWorkflow = varda.features.workspaces.GeneralImageAnalysisWorkflow(
        #         parent=self
        #     )
        #     self.centralTabs.addTab(self.testWorkflow, "Test Workflow")
        #     # self.setCentralWidget(self.centralTabs)
        #     # self.testWorkflow.show()

    # TODO: Delete?
    def trackPixelPlotWindow(self, window):
        """Track a pixel plot window."""
        if window not in self.pixelPlotWindows:
            self.pixelPlotWindows.append(window)
            # Connect close event to remove from tracking
            window.destroyed.connect(lambda: self.removePixelPlotWindow(window))

    # TODO: Delete?
    def removePixelPlotWindow(self, window):
        """Remove a pixel plot window from tracking."""
        if window in self.pixelPlotWindows:
            self.pixelPlotWindows.remove(window)

    def closeAllChildWindows(self):
        """Close all child windows before shutting down."""
        # Close all tracked child windows
        for window in self.childWindows[
            :
        ]:  # Use a copy of the list since it will be modified during iteration
            if window and window.isVisible():
                window.close()

        # Close all pixel plot windows
        for window in self.pixelPlotWindows[:]:
            if window and window.isVisible():
                window.close()

        # Close any control panels
        # for panel in self.controlPanels.values():
        #     if hasattr(panel, "pixelPlotPopup") and panel.pixelPlotPopup:
        #         panel.pixelPlotPopup.close()

        # Clear tracking lists
        self.childWindows.clear()
        self.pixelPlotWindows.clear()

        logger.info("All child windows closed")

    def exitApp(self):
        """Properly shut down the application by closing all windows."""
        logger.info("Exiting application...")

        # Close all child windows first
        self.closeAllChildWindows()

        # Then close the main window
        self.close()

        # Force application to quit after a short delay if it hasn't already
        QtCore.QTimer.singleShot(500, lambda: QtWidgets.QApplication.quit())

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
