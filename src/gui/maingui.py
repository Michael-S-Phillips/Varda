from pathlib import Path
import logging
import sys
import asyncio
from typing import Dict, Optional

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, QObject
from qasync import QEventLoop, QApplication


from core.data import ProjectContext
from core.ui import ControlPanel
from features.image_view_raster.raster_view import RasterView
from features.image_process.process_controls.processingmenu import ProcessingMenu
from features.image_process.process_controls.processdialog import ProcessDialog
from features.image_process.processes.imageprocess import ImageProcess
from features.dual_image_view.dual_image_view import DualImageView
from gui.widgets import StatusBar, MainMenuBar
from features import (
    image_view_raster,
    image_view_stretch,
    image_view_band,
    image_view_roi,
    all_images_view_list,
    image_view_histogram,
)
import core.utilities.debug as debug

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self, proj: ProjectContext):
        super().__init__()

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("img/logo.svg"))

        self.proj = proj
        self.selectedImage = None
        self.imageList = None
        self.currControlPanel = None
        self.controlPanels: Dict[int, ControlPanel] = {}  # image index -> ControlPanel
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

        self.menuBar().sigOpenProcessingMenu.connect(self.openProcessingMenu)
        
        # NEW: Connect dual image signals
        self.menuBar().sigOpenDualImageView.connect(self.openDualImageView)
        self.menuBar().sigLinkSelectedImages.connect(self.linkSelectedImages)
        self.menuBar().sigUnlinkSelectedImages.connect(self.unlinkSelectedImages)

        self.imageList.itemClicked.connect(self.onSelectedImageChanged)

        self.proj.sigDataChanged.connect(self.onProjectDataChanged)

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
        rasterView = self.showRasterView(index)

        # Control Panel
        if self.currControlPanel:
            self.currControlPanel.tabsDock.hide()

        if index not in self.controlPanels:
            panel = ControlPanel(self.proj, index, rasterView)
            # panel.updateActiveImage(self.selectedImage.index)
            self.controlPanels[index] = panel
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, panel.tabsDock)
        else:
            panel = self.controlPanels[index]

        self.currControlPanel = panel
        panel.tabsDock.show()

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
    # def openDualImageView(self):
    #     """Open the dual image view dialog/dock"""
    #     if len(self.proj.getAllImages()) < 2:
    #         QtWidgets.QMessageBox.information(
    #             self,
    #             "Dual Image View",
    #             "You need at least 2 images loaded to use dual image view."
    #         )
    #         return
        
    #     # Create or show the dual view
    #     if not hasattr(self, 'dual_view') or self.dual_view is None:
    #         from features.dual_image_view.dual_image_view import DualImageView
    #         self.dual_view = DualImageView(self.proj)
            
    #         # Create dock widget
    #         dock = QtWidgets.QDockWidget("Dual Image View", self)
    #         dock.setWidget(self.dual_view)
    #         self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            
    #         # Store dock reference
    #         self.dual_view_dock = dock
        
    #     # CRITICAL: Ensure the dock and dual view are visible
    #     self.dual_view_dock.setVisible(True)
    #     self.dual_view_dock.show()
    #     self.dual_view.setVisible(True)
    #     self.dual_view.show()
        
    #     # Force updates
    #     self.dual_view_dock.update()
    #     self.dual_view.update()
        
    #     logger.debug("Dual image view opened and made visible")
    def openDualImageView(self):
        """Open the dual image view dialog/dock"""
        if len(self.proj.getAllImages()) < 2:
            QtWidgets.QMessageBox.information(
                self,
                "Dual Image View",
                "You need at least 2 images loaded to use dual image view."
            )
            return
        
        # Import here to avoid circular import
        from features.dual_image_view.dual_image_view import DualImageView
        from features.dual_image_view.dual_image_selection_dialog import DualImageSelectionDialog
        
        # Show selection dialog first
        dialog = DualImageSelectionDialog(self.proj, self)
        
        # Set current image as default primary if one is selected
        if self.selectedImage is not None:
            dialog.set_default_images(primary_index=self.selectedImage.index)
        
        # Show dialog to select primary and secondary images
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            primary_index, secondary_index = dialog.get_selected_images()
            config = dialog.get_configuration()
            
            if primary_index is not None and secondary_index is not None:
                # Create dual image view if it doesn't exist
                if self.dualImageView is None:
                    self.dualImageView = DualImageView(self.proj, self)
                    
                    # Create dock widget
                    self.dualImageDock = QtWidgets.QDockWidget("Dual Image View", self)
                    self.dualImageDock.setWidget(self.dualImageView)
                    self.dualImageDock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
                    
                    # Add to bottom area by default
                    self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dualImageDock)
                    
                    # Connect dual image view signals
                    self.dualImageView.primary_image_changed.connect(self._onDualImagePrimaryChanged)
                    self.dualImageView.secondary_image_changed.connect(self._onDualImageSecondaryChanged)
                    self.dualImageView.link_toggled.connect(self._onDualImageLinkToggled)
                    
                    # Track the dock
                    self.childWindows.append(self.dualImageDock)
                
                # Set up the dual view with selected images and configuration
                self.dualImageView.set_primary_image(primary_index)
                self.dualImageView.set_secondary_image(secondary_index)
                
                # Apply configuration by updating the UI controls
                self._apply_dual_image_config(config)
                
                # Auto-link the images
                if not self.dualImageView._is_linked:
                    self.dualImageView._toggle_link()
                

                self.dualImageDock.setVisible(True)
                self.dualImageDock.show()
                self.dualImageView.setVisible(True)
                self.dualImageView.show()
                
                # Force updates
                self.dualImageDock.update()
                self.dualImageView.update()

                # Show the dock
                self.dualImageDock.show()
                self.dualImageDock.raise_()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "Please select valid primary and secondary images."
                )
    
    def linkSelectedImages(self):
        """Link two selected images for dual view"""
        selected_items = self.imageList.selectedItems()
        
        if len(selected_items) != 2:
            QtWidgets.QMessageBox.information(
                self,
                "Link Images",
                "Please select exactly 2 images in the image list to link."
            )
            return
        
        # Get indices of selected images
        indices = []
        for item in selected_items:
            index = self.imageList.row(item)
            indices.append(index)
        
        # Import here to avoid circular import
        from features.dual_image_view.dual_image_view import DualImageView
        from features.dual_image_view.dual_image_selection_dialog import DualImageSelectionDialog
        
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
                self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dualImageDock)
                
                # Connect dual image view signals
                self.dualImageView.primary_image_changed.connect(self._onDualImagePrimaryChanged)
                self.dualImageView.secondary_image_changed.connect(self._onDualImageSecondaryChanged)
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
                self,
                "Unlink Images",
                "No images are currently linked."
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
        """Apply configuration to the dual image view"""
        if not self.dualImageView:
            return
        
        # Update display mode
        for i in range(self.dualImageView.mode_combo.count()):
            if self.dualImageView.mode_combo.itemData(i) == config.mode:
                self.dualImageView.mode_combo.setCurrentIndex(i)
                break
        
        # Update opacity
        opacity_value = int(config.overlay_opacity * 100)
        self.dualImageView.opacity_slider.setValue(opacity_value)
        
        # Update blink interval
        self.dualImageView.blink_interval_spin.setValue(config.blink_interval)
        
        # Update sync settings
        self.dualImageView.sync_navigation_cb.setChecked(config.sync_navigation)
        self.dualImageView.sync_rois_cb.setChecked(config.sync_rois)

    # Add cleanup to exitApp method
    def exitApp(self):
        """Clean up and exit the application."""
        # Close dual image view
        if self.dualImageView:
            self.closeDualImageView()
        
        # Close all child windows
        for window in self.childWindows[:]:  # Copy list to avoid modification during iteration
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

    # TODO: I think we can delete the context menu stuff since we have the control panel. Relevant methods tagged below

    # TODO: Delete?
    def contextMenuEvent(self, event):
        localPos = self.imageList.mapFromGlobal(event.globalPos())
        item = self.imageList.itemAt(localPos)
        index = self.imageList.indexFromItem(item)
        if index.isValid():
            contextMenu = self.createContextMenu(index)
            contextMenu.exec(event.globalPos())
        else:
            print("No item selected")

    # TODO: Delete?
    def createContextMenu(self, index):
        contextMenu = QtWidgets.QMenu(self)
        openView = contextMenu.addMenu("Open View")
        rasterView = openView.addAction("RasterData View")
        bandView = openView.addAction("Band View")
        roiView = openView.addAction("ROI Table View")
        histogramView = openView.addAction("Histogram View")

        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        logger.debug(type(image))
        imageIndex = image.index

        rasterView.triggered.connect(lambda: self.showRasterView(imageIndex))
        bandView.triggered.connect(lambda: self.openBandView(imageIndex))
        roiView.triggered.connect(lambda: self.openROIView(imageIndex))
        histogramView.triggered.connect(lambda: self.openHistogramView(imageIndex))
        return contextMenu

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

    # TODO: Delete?
    def openBandView(self, image_index):
        from features.image_view_band import BandManager

        view = BandManager(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Band View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # Track the dock widget
        self.childWindows.append(dock)
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

    # TODO: Delete?
    def openHistogramView(self, image_index):
        from features.image_view_histogram import getHistogramView

        view = getHistogramView(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Histogram View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # Track the dock widget
        self.childWindows.append(dock)
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

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

    def onProjectDataChanged(self, index, changeType, changeModifier=None):
        """Handle when project data changes (like new images being added)."""
        if (
            changeType == self.proj.ChangeType.IMAGE
            and changeModifier == self.proj.ChangeModifier.ADD
        ):
            print(f"New image added at index {index}")

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
        for panel in self.controlPanels.values():
            if hasattr(panel, "pixelPlotPopup") and panel.pixelPlotPopup:
                panel.pixelPlotPopup.close()

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


def startGui(proj: ProjectContext):
    app = QApplication(sys.argv)

    # Set the application name and organization
    app.setApplicationName("Varda")
    app.setOrganizationName("Varda")

    # Set up a signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}. Shutting down...")
        app.quit()

    # Set up the event loop
    eventLoop = QEventLoop(app)
    asyncio.set_event_loop(eventLoop)

    # Create and show the main window
    window = MainGUI(proj)
    window.showMaximized()
    window.show()

    # Register the cleanup handler for when the application is about to quit
    app.aboutToQuit.connect(lambda: logger.info("Application is about to quit"))

    # Run the event loop until it's stopped
    with eventLoop:
        eventLoop.run_forever()
