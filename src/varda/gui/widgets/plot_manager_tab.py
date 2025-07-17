import logging
import numpy as np
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
    QGridLayout,
    QSplitter,
    QPushButton,
    QLabel,
    QMessageBox,
    QMenu,
    QApplication,
    QInputDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QDateTime, QSize
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QAction, QIcon

from varda.app.project import ProjectContext
from varda.features.components.controlpanel import DockableTab
from varda.gui.widgets.spectral_properties_panel import (
    SpectralPropertiesPanel,
    EnhancedImagePlotWidget,
)
from varda.utilities import WavelengthProcessor
from varda.utilities import BoundsValidator
from varda.utilities import (
    InvalidDataHandler,
    InvalidValueStrategy,
)

logger = logging.getLogger(__name__)


class DraggablePlotThumbnail(QWidget):
    """Draggable thumbnail widget for plot thumbnails with selection support."""

    thumbnailClicked = pyqtSignal(dict)  # plot_data
    thumbnailRightClicked = pyqtSignal(dict, QPoint)  # plot_data, position
    selectionChanged = pyqtSignal(str, bool)  # plot_id, is_selected
    thumbnailPressed = pyqtSignal(dict)  # plot_data for single clicks
    plotsMergeRequested = pyqtSignal(
        str, str
    )  # Add this new signal: source_plot_id, target_plot_id

    def __init__(self, plot_data: dict, thumbnail_widget: QWidget, parent=None):
        super().__init__(parent)
        self.plot_data = plot_data
        self.thumbnail_widget = thumbnail_widget
        self.is_selected = False
        self.is_pinned = False  # Add pin state

        # Set up drag and drop
        self.setAcceptDrops(True)

        # Create layout and add thumbnail
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(thumbnail_widget)

        # Style with selection support
        self._update_style()

    def set_pinned(self, pinned: bool):
        """Set pin state and update visual appearance."""
        if self.is_pinned != pinned:
            self.is_pinned = pinned
            self._update_style()
            self.repaint()
            self.update()

    def _update_style(self):
        """Update widget style based on selection state."""
        # Remove any existing selection overlay
        if hasattr(self, "selection_overlay"):
            self.selection_overlay.setParent(None)
            delattr(self, "selection_overlay")

        if self.is_selected:
            # Create a colored overlay widget
            from PyQt6.QtWidgets import QFrame

            self.selection_overlay = QFrame(self)
            self.selection_overlay.setStyleSheet(
                """
                QFrame {
                    border: 3px solid #2196F3;
                    border-radius: 4px;
                    background-color: rgba(33, 150, 243, 30);
                }
            """
            )
            self.selection_overlay.setGeometry(0, 0, self.width(), self.height())
            self.selection_overlay.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            self.selection_overlay.show()
            self.selection_overlay.raise_()

        self.update()

    def resizeEvent(self, event):
        """Handle resize events to update selection overlay."""
        super().resizeEvent(event)
        if hasattr(self, "selection_overlay"):
            self.selection_overlay.setGeometry(0, 0, self.width(), self.height())

    def set_selected(self, selected: bool):
        """Set selection state and update visual appearance."""
        if self.is_selected != selected:
            self.is_selected = selected
            self._update_style()
            self.selectionChanged.emit(self.plot_data["id"], selected)

    def mousePressEvent(self, event):
        """Handle mouse press for selection and drag initiation."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check for Shift modifier for multi-selection
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Toggle selection with Shift+Click
                self.set_selected(not self.is_selected)
            else:
                # Single click - emit signal for selection handling
                self.thumbnailPressed.emit(self.plot_data)
            self.drag_start_position = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self.thumbnailRightClicked.emit(
                self.plot_data, event.globalPosition().toPoint()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag operation."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if not hasattr(self, "drag_start_position"):
            return

        # Check if we've moved far enough to start a drag
        if (
            event.position().toPoint() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        # Start drag operation
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setData("application/x-varda-plot", self.plot_data["id"].encode())

        # Create drag pixmap (simplified thumbnail)
        pixmap = QPixmap(60, 45)
        pixmap.fill(Qt.GlobalColor.lightGray)
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "📊")
        painter.end()

        drag.setPixmap(pixmap)
        drag.setMimeData(mimeData)

        # Execute drag
        dropAction = drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open plot."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.thumbnailClicked.emit(self.plot_data)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasFormat("application/x-varda-plot"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop events for plot merging."""
        if event.mimeData().hasFormat("application/x-varda-plot"):
            source_plot_id = (
                event.mimeData().data("application/x-varda-plot").data().decode()
            )
            target_plot_id = self.plot_data["id"]

            if source_plot_id != target_plot_id:
                # Emit merge signal to be handled by parent
                self.plotsMergeRequested.emit(source_plot_id, target_plot_id)
                logger.debug(
                    f"Drop merge requested: {source_plot_id} -> {target_plot_id}"
                )

            event.acceptProposedAction()
        else:
            event.ignore()

    def paintEvent(self, event):
        """Custom paint event to show selection border and pin indicator."""
        super().paintEvent(event)

        from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont

        painter = QPainter(self)

        # Draw selection border
        if self.is_selected:
            pen = QPen(QColor(33, 150, 243), 3)  # Blue color, 3px width
            painter.setPen(pen)
            painter.drawRect(1, 1, self.width() - 3, self.height() - 3)

            # Optional: Add a semi-transparent background
            brush = QBrush(QColor(33, 150, 243, 30))  # Semi-transparent blue
            painter.setBrush(brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(2, 2, self.width() - 4, self.height() - 4)

        # Draw pin indicator
        if self.is_pinned:
            # Draw pin icon in top-right corner
            pin_size = 16
            pin_x = int(self.width() / 3) + 4
            pin_y = 4

            # Pin background circle
            painter.setBrush(QBrush(QColor(255, 193, 7)))  # Amber color
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawEllipse(pin_x, pin_y, pin_size, pin_size)

            # Pin icon (📌)
            painter.setPen(QPen(QColor(0, 0, 0)))
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(pin_x + 2, pin_y + 12, "📌")

        painter.end()


class PlotWindow(EnhancedImagePlotWidget):
    """Advanced plot window with drag-drop support and properties panel."""

    def __init__(self, plot_data: dict, project_context: ProjectContext, parent=None):
        super().__init__(
            proj=project_context,
            imageIndex=plot_data.get("image_index"),
            isWindow=True,
            show_properties_panel=True,
            parent=parent,
        )

        self.plot_data = plot_data
        self.setWindowTitle(f"Spectral Plot - {plot_data.get('title', 'Unknown')}")
        self.resize(1000, 700)

        # Override window flags to remove stay-on-top behavior and ensure proper independence
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowTitleHint
        )

        # Ensure window is not transparent
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setWindowOpacity(1.0)

        # Set up drag and drop
        self.setAcceptDrops(True)

        # Load initial spectrum
        self._load_initial_spectrum()

    def _load_initial_spectrum(self):
        """Load the initial spectrum(s) for this plot."""
        try:
            # Check if this is a merged plot
            if self.plot_data.get("is_merged", False):
                self._load_merged_spectra()
            else:
                # Load single spectrum
                x, y = self.plot_data["coords"]
                image_index = self.plot_data["image_index"]

                if hasattr(self, "showPixelSpectrum"):
                    self.showPixelSpectrum(x, y, image_index)

                logger.debug(f"Loaded spectrum for coordinates ({x}, {y})")

        except Exception as e:
            logger.error(f"Error loading initial spectrum: {e}")

    def _load_merged_spectra(self):
        """Load multiple spectra for merged plots."""
        try:
            merged_spectra = self.plot_data.get("merged_spectra", [])
            colors = [
                "blue",
                "red",
                "green",
                "orange",
                "purple",
                "brown",
                "pink",
                "gray",
                "olive",
                "cyan",
            ]

            # Clear any existing spectra first
            if hasattr(self, "clear_all_spectra"):
                self.clear_all_spectra()

            for i, plot_data in enumerate(merged_spectra):
                x, y = plot_data["coords"]
                image_index = plot_data["image_index"]
                color = colors[i % len(colors)]

                # Create spectrum label
                label = f"{plot_data['title']}"

                # Get the image and extract spectrum data
                image = self.proj.getImage(image_index)

                # Validate coordinates
                is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
                    x, y, image.raster.shape, allow_clipping=True
                )

                if not is_valid:
                    logger.warning(
                        f"Invalid coordinates ({x}, {y}) for merged spectrum {i}"
                    )
                    continue

                # Get wavelengths and spectrum data
                wavelengths, wavelength_type = (
                    WavelengthProcessor.process_wavelength_data(
                        image.metadata.wavelengths, image.raster.shape[2]
                    )
                )

                spectrum = BoundsValidator.safe_pixel_access(
                    image.raster, safe_x, safe_y
                )

                # Clean the data
                (
                    clean_wavelengths,
                    clean_spectrum,
                    cleaning_success,
                    cleaning_message,
                ) = InvalidDataHandler.handle_spectral_pair(
                    wavelengths,
                    spectrum,
                    strategy=InvalidValueStrategy.INTERPOLATE,
                    sync_removal=False,
                )

                if len(clean_spectrum) == 0:
                    logger.warning(f"No valid data for merged spectrum {i}")
                    continue

                # Add spectrum using the correct method
                spectrum_id = f"merged_{i}_{plot_data['id']}"
                if hasattr(self, "add_spectrum"):
                    self.add_spectrum(
                        wavelengths=clean_wavelengths,
                        values=clean_spectrum,
                        label=label,
                        color=color,
                        coords=(safe_x, safe_y),
                        image_index=image_index,
                        wavelength_type=wavelength_type,
                        spectrum_id=spectrum_id,
                    )
                    logger.debug(f"Added merged spectrum {spectrum_id}: {label}")
                else:
                    logger.error("add_spectrum method not available")
                    return

            logger.debug(
                f"Successfully loaded {len(merged_spectra)} spectra into merged plot"
            )

        except Exception as e:
            logger.error(f"Error loading merged spectra: {e}")
            # Fallback: show first spectrum
            if self.plot_data.get("merged_spectra"):
                first_plot = self.plot_data["merged_spectra"][0]
                x, y = first_plot["coords"]
                image_index = first_plot["image_index"]
                if hasattr(self, "showPixelSpectrum"):
                    self.showPixelSpectrum(x, y, image_index)

    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasFormat("application/x-varda-plot"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop events to add spectra from other plots."""
        if not event.mimeData().hasFormat("application/x-varda-plot"):
            event.ignore()
            return

        try:
            import json

            dropped_plot_data = json.loads(
                event.mimeData().data("application/x-varda-plot").data().decode()
            )

            # Add spectrum from dropped plot
            self._add_spectrum_from_plot_data(dropped_plot_data)

            event.acceptProposedAction()

        except Exception as e:
            logger.error(f"Error handling drop: {e}")
            event.ignore()

    def _add_spectrum_from_plot_data(self, plot_data: dict):
        """Add a spectrum from dropped plot data with comprehensive data validation."""
        coords = plot_data.get("coords")
        image_index = plot_data.get("image_index")

        if not coords or image_index is None:
            return

        try:
            # Get spectral data
            image = self.proj.getImage(image_index)
            x, y = coords

            # Validate coordinates before accessing pixel data
            is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
                x, y, image.raster.shape, allow_clipping=True
            )

            if not is_valid:
                logger.error(
                    f"Invalid coordinates ({x}, {y}) for image with shape {image.raster.shape}"
                )
                QMessageBox.warning(
                    self, "Error", f"Coordinates ({x}, {y}) are outside image bounds"
                )
                return

            # Use centralized wavelength processing
            wavelengths, wavelength_type = WavelengthProcessor.process_wavelength_data(
                image.metadata.wavelengths, image.raster.shape[2]
            )

            # Get spectrum using safe pixel access
            spectrum = BoundsValidator.safe_pixel_access(image.raster, safe_x, safe_y)

            # Handle invalid values in the spectral pair
            clean_wavelengths, clean_spectrum, cleaning_success, cleaning_message = (
                InvalidDataHandler.handle_spectral_pair(
                    wavelengths,
                    spectrum,
                    strategy=InvalidValueStrategy.INTERPOLATE,
                    sync_removal=False,
                )
            )

            # Validate data quality
            is_good_quality, quality_report = (
                InvalidDataHandler.validate_spectral_data_quality(
                    clean_wavelengths, clean_spectrum, min_valid_percentage=30.0
                )
            )

            # Handle data quality issues
            if not cleaning_success:
                logger.warning(f"Invalid data handling issues: {cleaning_message}")

            if not is_good_quality:
                logger.warning(
                    f"Data quality issues: {quality_report.get('quality_issues', [])}"
                )
                QMessageBox.information(
                    self,
                    "Data Quality Warning",
                    f"Data quality issues detected for pixel ({safe_x}, {safe_y}):\n"
                    + "\n".join(quality_report.get("quality_issues", []))
                    + f"\n\nContinuing with processed data...",
                )

            # Final validation
            if len(clean_spectrum) == 0:
                logger.error(
                    f"No valid spectral data available for pixel ({safe_x}, {safe_y})"
                )
                QMessageBox.warning(
                    self,
                    "No Data",
                    f"No valid spectral data available for pixel ({safe_x}, {safe_y})",
                )
                return

            # Create label with quality indicators
            base_label = plot_data.get("title", f"Pixel ({safe_x}, {safe_y})")
            if not cleaning_success or not is_good_quality:
                base_label += " ⚠"

            # Add to plot
            spectrum_id = self.add_spectrum(
                wavelengths=clean_wavelengths,
                values=clean_spectrum,
                label=base_label,
                coords=(safe_x, safe_y),
                image_index=image_index,
                wavelength_type=wavelength_type,
            )

            logger.info(
                f"Added spectrum {spectrum_id} from dropped plot (quality: {'good' if is_good_quality else 'issues'})"
            )

        except Exception as e:
            logger.error(f"Error adding spectrum from plot data: {e}")
            QMessageBox.warning(self, "Error", f"Could not add spectrum: {str(e)}")


class ResponsiveButton(QPushButton):
    """Button that changes text based on available width."""

    def __init__(self, full_text: str, short_text: str, parent=None):
        super().__init__(full_text, parent)
        self.full_text = full_text
        self.short_text = short_text
        self.threshold_width = 80  # Width below which to use short text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() < self.threshold_width:
            self.setText(self.short_text)
        else:
            self.setText(self.full_text)


class PlotManagerTab(DockableTab):
    """Advanced Plot Manager Tab with spectral control integration."""

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Plot Manager", parent)
        self.project_context = proj
        self.imageIndex = imageIndex

        # Track popup windows
        self.popup_windows = {}  # Dict to track popup windows by plot ID
        self.selected_plots = set()
        self.pinned_plot_id = None
        self.lastPixelCoords = (0, 0)

        # Plot storage and settings
        self.stored_plots = []  # List of stored plot data
        self.plot_counter = 0  # Counter for unique plot IDs

        # Settings
        self.context_enabled = False
        self.main_enabled = False
        self.zoom_enabled = True
        self.update_existing = True

        # Track the "active" plot for update mode
        self.active_plot_id = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the UI."""
        print("DEBUG: Loading NEW plot manager UI with selection controls")
        layout = QVBoxLayout(self)

        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section - Settings and plot management
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        # Settings Section
        settings_group = QGroupBox("Plot Settings")
        settings_layout = QVBoxLayout(settings_group)

        # View settings
        view_layout = QHBoxLayout()
        self.context_checkbox = QCheckBox("Context View")
        self.main_checkbox = QCheckBox("Main View")
        self.zoom_checkbox = QCheckBox("Zoom View")

        self.context_checkbox.setChecked(self.context_enabled)
        self.main_checkbox.setChecked(self.main_enabled)
        self.zoom_checkbox.setChecked(self.zoom_enabled)

        view_layout.addWidget(self.context_checkbox)
        view_layout.addWidget(self.main_checkbox)
        view_layout.addWidget(self.zoom_checkbox)

        # Update behavior settings
        behavior_layout = QVBoxLayout()
        self.update_radio = QRadioButton("Update existing plots")
        self.create_radio = QRadioButton("Create new plots")

        self.behavior_group = QButtonGroup()
        self.behavior_group.addButton(self.update_radio)
        self.behavior_group.addButton(self.create_radio)

        self.update_radio.setChecked(self.update_existing)
        self.create_radio.setChecked(not self.update_existing)

        behavior_layout.addWidget(self.update_radio)
        behavior_layout.addWidget(self.create_radio)

        settings_layout.addLayout(view_layout)
        settings_layout.addLayout(behavior_layout)

        # Plot type settings
        top_layout.addWidget(settings_group)

        # Stored Plots Section with drag-drop support
        plots_group = QGroupBox("Stored Plots (Drag to combine)")
        plots_layout = QVBoxLayout(plots_group)

        # Plot controls
        plot_controls = QHBoxLayout()

        # Selection controls
        selection_controls = QHBoxLayout()
        self.select_all_button = ResponsiveButton("☑ All", "☑")
        self.select_all_button.setToolTip("Select all plots")
        self.clear_selection_button = ResponsiveButton("☐ Clear", "☐")
        self.clear_selection_button.setToolTip("Clear current selection")

        selection_controls.addWidget(self.select_all_button)
        selection_controls.addWidget(self.clear_selection_button)

        # Action controls
        action_controls = QHBoxLayout()
        self.merge_button = ResponsiveButton("⚡ Merge", "⚡")
        self.merge_button.setToolTip("Merge selected plots into one plot")
        self.merge_button.setEnabled(False)

        self.delete_selected_button = ResponsiveButton("🗑 Delete", "🗑")
        self.delete_selected_button.setToolTip("Delete selected plots")
        self.delete_selected_button.setEnabled(False)

        self.export_selected_button = ResponsiveButton("📤 Export", "📤")
        self.export_selected_button.setToolTip("Export selected plots")
        self.export_selected_button.setEnabled(False)

        # Pin controls
        self.pin_selected_button = ResponsiveButton("📌 Pin", "📌")
        self.pin_selected_button.setToolTip(
            "Pin selected plot for updates (update mode only)"
        )
        self.pin_selected_button.setEnabled(False)

        self.unpin_all_button = ResponsiveButton("📌❌ Unpin", "📌❌")
        self.unpin_all_button.setToolTip("Unpin all plots")
        self.unpin_all_button.setEnabled(False)

        action_controls.addWidget(self.merge_button)
        action_controls.addWidget(self.delete_selected_button)
        action_controls.addWidget(self.export_selected_button)
        action_controls.addWidget(QLabel("|"))  # Visual separator
        action_controls.addWidget(self.pin_selected_button)
        action_controls.addWidget(self.unpin_all_button)

        # basic controls
        basic_controls = QHBoxLayout()
        self.clear_all_button = QPushButton("🗑 All")
        self.clear_all_button.setToolTip("Remove all stored plots")
        self.export_all_button = QPushButton("📤 All")
        self.export_all_button.setToolTip("Export all plots")

        basic_controls.addWidget(self.clear_all_button)
        basic_controls.addWidget(self.export_all_button)

        # Add all control groups to main layout
        plot_controls.addLayout(selection_controls)
        plot_controls.addWidget(QLabel("|"))  # Visual separator
        plot_controls.addLayout(action_controls)
        plot_controls.addWidget(QLabel("|"))  # Visual separator
        plot_controls.addLayout(basic_controls)
        plot_controls.addStretch()  # Push controls to the right
        plots_layout.addLayout(plot_controls)

        # Scroll area for plot thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.plots_widget = QWidget()
        self.plots_layout = QGridLayout(self.plots_widget)
        self.plots_layout.setSpacing(5)

        self.scroll_area.setWidget(self.plots_widget)
        plots_layout.addWidget(self.scroll_area)

        top_layout.addWidget(plots_group)

        # Bottom section - Current plot with properties
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # Current plot section
        current_group = QGroupBox("Current Plot Preview")
        current_layout = QVBoxLayout(current_group)

        # Create embedded plot
        self.current_plot = EnhancedImagePlotWidget(
            self.project_context,
            self.imageIndex,
            show_properties_panel=False,  # Keep compact for preview
            parent=self,
        )
        self.current_plot.setMaximumHeight(200)
        current_layout.addWidget(self.current_plot)

        # Quick actions for current plot
        current_actions = QHBoxLayout()
        self.open_advanced_button = QPushButton("Open Advanced")
        self.open_advanced_button.setToolTip("Open current plot in advanced window")
        self.properties_button = QPushButton("Properties")
        self.properties_button.setToolTip("Show properties panel for current plot")

        current_actions.addWidget(self.open_advanced_button)
        current_actions.addWidget(self.properties_button)
        current_actions.addStretch()

        current_layout.addLayout(current_actions)
        bottom_layout.addWidget(current_group)

        # Add to main splitter
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([300, 250])

        layout.addWidget(main_splitter)

    def _connect_signals(self):
        """Connect all widget signals."""
        # Settings signals
        self.context_checkbox.toggled.connect(self._on_context_toggled)
        self.main_checkbox.toggled.connect(self._on_main_toggled)
        self.zoom_checkbox.toggled.connect(self._on_zoom_toggled)
        self.update_radio.toggled.connect(self._on_behavior_changed)

        # Control signals
        self.clear_all_button.clicked.connect(self._clear_all_plots)
        self.export_all_button.clicked.connect(self._export_all_plots)

        # Pin control signals
        self.pin_selected_button.clicked.connect(self._pin_selected_plot)
        self.unpin_all_button.clicked.connect(self._unpin_all_plots)

        # Selection control signals
        self.select_all_button.clicked.connect(self._select_all_thumbnails)
        self.clear_selection_button.clicked.connect(self._clear_all_selections)

        # Action control signals
        self.merge_button.clicked.connect(self._merge_selected_plots)
        self.delete_selected_button.clicked.connect(self._delete_selected_plots)
        self.export_selected_button.clicked.connect(self._export_selected_plots)

        self.open_advanced_button.clicked.connect(self._open_current_advanced)
        self.properties_button.clicked.connect(self._show_current_properties)

        # Current plot signals
        if hasattr(self.current_plot, "sigClicked"):
            self.current_plot.sigClicked.connect(self.handlePixelPlotClicked)

    def _on_context_toggled(self, checked):
        """Handle context view checkbox toggle."""
        self.context_enabled = checked

    def _on_main_toggled(self, checked):
        """Handle main view checkbox toggle."""
        self.main_enabled = checked

    def _on_zoom_toggled(self, checked):
        """Handle zoom view checkbox toggle."""
        self.zoom_enabled = checked

    def _on_behavior_changed(self, checked):
        """Handle update behavior radio button change."""
        old_update_existing = self.update_existing

        if checked:  # update_radio was checked
            self.update_existing = True
        else:
            self.update_existing = False

        # When switching modes, manage the active plot
        if old_update_existing != self.update_existing:
            if self.update_existing:
                # Switching to "update existing" mode
                if self.pinned_plot_id is not None:
                    # If there's a pinned plot, use it as the active plot
                    self.active_plot_id = self.pinned_plot_id
                    logger.debug(
                        f"Switched to update mode. Using pinned plot as active: {self.active_plot_id}"
                    )
                elif self.stored_plots:
                    # No pinned plot, use the most recent plot as active
                    self.active_plot_id = self.stored_plots[-1]["id"]
                    logger.debug(
                        f"Switched to update mode. Using most recent plot as active: {self.active_plot_id}"
                    )
                else:
                    # No plots at all
                    self.active_plot_id = None
                    logger.debug("Switched to update mode but no plots available")
            else:
                # Switching to "create new" - clear active plot
                self.active_plot_id = None
                logger.debug("Switched to create new mode. Cleared active plot.")

            # Update pin button states since update mode affects pin availability
            self._update_pin_buttons()

    def should_update_plot(self) -> bool:
        """Check if plot updates should be processed."""
        return self.context_enabled or self.main_enabled or self.zoom_enabled

    def showPixelSpectrum(self, x: int, y: int):
        """Update plot with new coordinates and potentially store it."""
        self.lastPixelCoords = (x, y)

        # Update current embedded plot
        if hasattr(self.current_plot, "showPixelSpectrum"):
            self.current_plot.showPixelSpectrum(x, y)

        # Store plot if enabled for any view
        if self.context_enabled or self.main_enabled or self.zoom_enabled:
            self._store_plot_data(x, y)

    def _pin_selected_plot(self):
        """Pin the selected plot."""
        if len(self.selected_plots) != 1:
            QMessageBox.information(
                self, "Pin Plot", "Please select exactly one plot to pin."
            )
            return

        if not self.update_existing:
            QMessageBox.information(
                self,
                "Pin Plot",
                "Plot pinning is only available in 'Update existing plots' mode.",
            )
            return

        plot_id = list(self.selected_plots)[0]
        self._pin_plot(plot_id)

    def _store_plot_data(self, x: int, y: int):
        """Store plot data and create thumbnail."""
        plot_data = {
            "coords": (x, y),
            "image_index": self.imageIndex,
            "title": f"Pixel ({x}, {y})",
            "timestamp": str(QDateTime.currentDateTime().toString()),
        }

        if self.update_existing and self.active_plot_id is not None:
            # Update the active plot only
            for i, stored_plot in enumerate(self.stored_plots):
                if stored_plot["id"] == self.active_plot_id:
                    # Update the existing plot data but keep the same ID
                    plot_data["id"] = self.active_plot_id
                    self.stored_plots[i] = plot_data

                    # Store pin state before refresh
                    was_pinned = self.active_plot_id == self.pinned_plot_id

                    # Refresh thumbnails
                    self._refresh_thumbnails()

                    # Restore pin state if it was pinned
                    if was_pinned:
                        thumb = self._get_thumbnail_widget(self.active_plot_id)
                        if thumb:
                            thumb.set_pinned(True)

                    # Update existing popup if open
                    if self.active_plot_id in self.popup_windows:
                        existing_popup = self.popup_windows[self.active_plot_id]
                        if existing_popup and existing_popup.isVisible():
                            existing_popup.showPixelSpectrum(x, y, self.imageIndex)
                            existing_popup.setWindowTitle(
                                f"Spectral Plot - {plot_data['title']}"
                            )

                    logger.debug(
                        f"Updated active plot {self.active_plot_id} with coords ({x}, {y})"
                    )
                    return

            # If we get here, the active plot wasn't found - create new
            logger.debug(
                f"Active plot {self.active_plot_id} not found, creating new plot"
            )
            self.active_plot_id = None

        # Create new plot entry
        plot_id = f"plot_{self.plot_counter}"
        self.plot_counter += 1
        plot_data["id"] = plot_id

        self.stored_plots.append(plot_data)
        self._add_plot_thumbnail(plot_data)

        # If we're in update mode, make this the new active plot
        if self.update_existing:
            self.active_plot_id = plot_id
            logger.debug(f"Created new plot {plot_id} and made it active")
        else:
            logger.debug(f"Created new plot {plot_id} in create mode")

    def _add_plot_thumbnail(self, plot_data: dict):
        """Add a draggable thumbnail for the stored plot."""
        # Create basic thumbnail widget
        thumb_widget = self._create_basic_thumbnail_widget(plot_data)

        # Wrap in draggable container
        draggable_thumb = DraggablePlotThumbnail(plot_data, thumb_widget)
        draggable_thumb.thumbnailClicked.connect(self._on_thumbnail_double_clicked)
        draggable_thumb.thumbnailRightClicked.connect(self._show_thumbnail_context_menu)
        draggable_thumb.selectionChanged.connect(self._on_thumbnail_selection_changed)
        draggable_thumb.thumbnailPressed.connect(self._on_thumbnail_single_clicked)
        draggable_thumb.plotsMergeRequested.connect(
            self._on_drag_merge_requested
        )  # Add this line

        # Calculate grid position
        current_count = self.plots_layout.count()
        row = current_count // 3
        col = current_count % 3
        self.plots_layout.addWidget(draggable_thumb, row, col)

        logger.debug(
            f"Added draggable thumbnail for {plot_data['id']} at position ({row}, {col})"
        )

    def _on_thumbnail_single_clicked(self, plot_data: dict):
        """Handle single click on thumbnail for selection."""
        modifiers = QApplication.keyboardModifiers()

        if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            # Clear other selections for single click without Shift
            self._clear_all_selections()

        # Find and select the clicked thumbnail
        thumb = self._get_thumbnail_widget(plot_data["id"])
        if thumb:
            thumb.set_selected(True)

    def _on_thumbnail_selection_changed(self, plot_id: str, is_selected: bool):
        """Handle thumbnail selection changes."""
        if is_selected:
            self.selected_plots.add(plot_id)
        else:
            self.selected_plots.discard(plot_id)

        # Update button states
        self._update_selection_buttons()
        logger.debug(
            f"Plot {plot_id} {'selected' if is_selected else 'deselected'}. Total selected: {len(self.selected_plots)}"
        )

    def _on_thumbnail_double_clicked(self, plot_data: dict):
        """Handle double-click to open plot (unchanged behavior)."""
        self._open_plot_popup(plot_data)

    def _on_thumbnail_clicked(self, plot_data: dict):
        """Handle single click on thumbnail for selection."""
        modifiers = QApplication.keyboardModifiers()

        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            # Clear other selections for single click
            self._clear_all_selections()

        # Find and toggle the clicked thumbnail
        for i in range(self.plots_layout.count()):
            item = self.plots_layout.itemAt(i)
            if item and item.widget():
                thumb = item.widget()
                if (
                    hasattr(thumb, "plot_data")
                    and thumb.plot_data["id"] == plot_data["id"]
                ):
                    if modifiers & Qt.KeyboardModifier.ControlModifier:
                        thumb.set_selected(not thumb.is_selected)
                    else:
                        thumb.set_selected(True)
                    break

    def _clear_all_selections(self):
        """Clear all thumbnail selections."""
        for i in range(self.plots_layout.count()):
            item = self.plots_layout.itemAt(i)
            if item and item.widget():
                thumb = item.widget()
                if hasattr(thumb, "set_selected"):
                    thumb.set_selected(False)

        self.selected_plots.clear()
        self._update_selection_buttons()

    def _select_all_thumbnails(self):
        """Select all thumbnails."""
        for i in range(self.plots_layout.count()):
            item = self.plots_layout.itemAt(i)
            if item and item.widget():
                thumb = item.widget()
                if hasattr(thumb, "set_selected"):
                    thumb.set_selected(True)

    def _update_selection_buttons(self):
        """Update button states based on current selection."""
        has_selection = len(self.selected_plots) > 0
        single_selected = len(self.selected_plots) == 1
        multiple_selected = len(self.selected_plots) > 1

        # Update button states
        if hasattr(self, "merge_button"):
            self.merge_button.setEnabled(multiple_selected)
        if hasattr(self, "delete_selected_button"):
            self.delete_selected_button.setEnabled(has_selection)
        if hasattr(self, "export_selected_button"):
            self.export_selected_button.setEnabled(has_selection)

        # Pin buttons
        self._update_pin_buttons()

    def _create_basic_thumbnail_widget(self, plot_data: dict) -> QWidget:
        """Create basic thumbnail widget."""
        thumb_widget = QWidget()
        thumb_layout = QVBoxLayout(thumb_widget)
        thumb_layout.setSpacing(2)  # Small fixed spacing
        thumb_layout.setContentsMargins(1, 1, 1, 1)  # Remove margins

        # Try to generate plot thumbnail
        plot_pixmap = self._create_plot_thumbnail(plot_data)

        if plot_pixmap:
            thumb_button = QPushButton()
            thumb_button.setIcon(QIcon(plot_pixmap))
            thumb_button.setIconSize(QSize(80, 60))
            thumb_button.setFixedSize(80, 60)
            thumb_button.setFlat(True)
            thumb_button.setStyleSheet("QPushButton { border: 1px solid gray; }")
        else:
            thumb_button = QPushButton("📊")
            thumb_button.setFixedSize(80, 60)

        thumb_button.setToolTip(f"Double-click to open {plot_data['title']}")

        # Make the button transparent to mouse events so parent can handle double-clicks
        thumb_button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Create title label
        title_label = QLabel(plot_data["title"])
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setMaximumWidth(80)
        title_label.setStyleSheet("font-size: 10px;")

        thumb_layout.addWidget(thumb_button)
        thumb_layout.addWidget(title_label)

        # Set fixed size policy to prevent expansion
        thumb_widget.setSizePolicy(
            thumb_widget.sizePolicy().horizontalPolicy(),
            thumb_widget.sizePolicy().Policy.Fixed,
        )
        thumb_widget.setFixedHeight(
            90
        )  # Fixed height: 60px button + ~20px for label + spacing
        thumb_layout.addStretch()  # Add stretch at the end to push content to top

        return thumb_widget

    def _create_plot_thumbnail(
        self, plot_data: dict, size=(120, 80)
    ) -> Optional[QPixmap]:
        """Create a thumbnail representation of the plot data with invalid data handling."""
        if not self.project_context:
            return None

        try:
            # Get the spectral data
            x, y = plot_data["coords"]
            image = self.project_context.getImage(plot_data["image_index"])

            # Validate coordinates before accessing pixel data
            is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
                x, y, image.raster.shape, allow_clipping=True
            )

            if not is_valid:
                logger.warning(
                    f"Invalid coordinates ({x}, {y}) for thumbnail generation"
                )
                return None

            # Use centralized wavelength processing
            wavelengths, wavelength_type = WavelengthProcessor.process_wavelength_data(
                image.metadata.wavelengths, image.raster.shape[2]
            )

            # Get spectrum data using safe pixel access
            spectrum = BoundsValidator.safe_pixel_access(image.raster, safe_x, safe_y)

            # Handle invalid values in the spectral pair
            clean_wavelengths, clean_spectrum, cleaning_success, cleaning_message = (
                InvalidDataHandler.handle_spectral_pair(
                    wavelengths,
                    spectrum,
                    strategy=InvalidValueStrategy.INTERPOLATE,
                    sync_removal=False,
                )
            )

            # Validate spectrum data for thumbnail generation
            if len(clean_spectrum) == 0 or np.all(clean_spectrum == 0):
                # Generate placeholder data if no valid spectrum
                clean_spectrum = np.random.random(len(clean_wavelengths)) * 100
                logger.debug("Generated placeholder data for thumbnail")

            # Create thumbnail plot
            import pyqtgraph as pg

            thumb_plot = pg.PlotWidget()
            thumb_plot.setFixedSize(size[0], size[1])
            thumb_plot.hideAxis("left")
            thumb_plot.hideAxis("bottom")
            thumb_plot.setMenuEnabled(False)
            thumb_plot.setMouseEnabled(x=False, y=False)
            thumb_plot.hideButtons()
            thumb_plot.setBackground("white")

            # Choose color based on data quality
            plot_color = "blue"
            if not cleaning_success:
                plot_color = "orange"  # Orange for data that needed cleaning

            # Plot the data
            thumb_plot.plot(
                clean_wavelengths,
                clean_spectrum,
                pen=pg.mkPen(color=plot_color, width=1),
            )

            # Render to pixmap
            thumb_plot.resize(size[0], size[1])
            thumb_plot.updateGeometry()

            pixmap = QPixmap(size[0], size[1])
            pixmap.fill()

            painter = QPainter(pixmap)
            thumb_plot.render(painter)
            painter.end()

            thumb_plot.close()
            thumb_plot.deleteLater()

            return pixmap

        except Exception as e:
            logger.warning(f"Error generating thumbnail: {e}")
            return None

    def _refresh_thumbnails(self):
        """Refresh all thumbnails while preserving selections and pin state."""
        logger.debug(f"Refreshing thumbnails for {len(self.stored_plots)} plots")

        # Store current selections and pin state
        current_selections = self.selected_plots.copy()
        current_pinned = self.pinned_plot_id

        # Clear existing thumbnails
        for i in reversed(range(self.plots_layout.count())):
            item = self.plots_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)

        # Clear selection tracking (will be restored)
        self.selected_plots.clear()

        # Re-add all thumbnails
        for i, plot_data in enumerate(self.stored_plots):
            self._add_plot_thumbnail(plot_data)

            # Restore selection if it was previously selected
            if plot_data["id"] in current_selections:
                thumb = self._get_thumbnail_widget(plot_data["id"])
                if thumb:
                    thumb.set_selected(True)

            # Restore pin state if this plot was pinned
            if plot_data["id"] == current_pinned:
                thumb = self._get_thumbnail_widget(plot_data["id"])
                if thumb:
                    thumb.set_pinned(True)

        # Update button states
        self._update_selection_buttons()

        logger.debug(
            f"Refreshed {len(self.stored_plots)} thumbnails with {len(self.selected_plots)} selections and pin state restored"
        )

    def _get_thumbnail_widget(self, plot_id: str):
        """Get the thumbnail widget for a given plot ID."""
        for i in range(self.plots_layout.count()):
            item = self.plots_layout.itemAt(i)
            if item and item.widget():
                thumb = item.widget()
                if hasattr(thumb, "plot_data") and thumb.plot_data["id"] == plot_id:
                    return thumb
        return None

    def _open_plot_popup(self, plot_data: dict):
        """Open advanced popup window for the selected plot."""
        plot_id = plot_data["id"]

        # Check if window already exists
        if plot_id in self.popup_windows:
            existing_popup = self.popup_windows[plot_id]
            if existing_popup and not existing_popup.isVisible():
                del self.popup_windows[plot_id]
            elif existing_popup:
                existing_popup.show()
                existing_popup.raise_()
                existing_popup.activateWindow()
                return

        # Always create advanced popup window
        popup = PlotWindow(plot_data, self.project_context, self)

        # Set up cleanup
        def cleanup_popup():
            if plot_id in self.popup_windows:
                del self.popup_windows[plot_id]

        popup.destroyed.connect(cleanup_popup)

        # Store reference and show
        self.popup_windows[plot_id] = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def _show_thumbnail_context_menu(self, plot_data: dict, position: QPoint):
        """Show context menu for thumbnail."""
        menu = QMenu(self)

        # Selection actions
        thumb = self._get_thumbnail_widget(plot_data["id"])
        if thumb and thumb.is_selected:
            select_action = QAction("Deselect", self)
            select_action.triggered.connect(lambda: thumb.set_selected(False))
        else:
            select_action = QAction("Select", self)
            select_action.triggered.connect(lambda: thumb.set_selected(True))
        menu.addAction(select_action)

        # Pin actions (only in update mode)
        if self.update_existing:
            menu.addSeparator()
            if thumb and thumb.is_pinned:
                unpin_action = QAction("Unpin Plot", self)
                unpin_action.triggered.connect(
                    lambda: self._unpin_plot(plot_data["id"])
                )
                menu.addAction(unpin_action)
            else:
                pin_action = QAction("Pin Plot", self)
                pin_action.triggered.connect(lambda: self._pin_plot(plot_data["id"]))
                menu.addAction(pin_action)

        if len(self.selected_plots) > 1:
            merge_action = QAction(
                f"Merge {len(self.selected_plots)} Selected Plots", self
            )
            merge_action.triggered.connect(self._merge_selected_plots)
            menu.addAction(merge_action)

        menu.addSeparator()

        # Open action
        open_action = QAction("Open Plot", self)
        open_action.triggered.connect(lambda: self._open_plot_popup(plot_data))
        menu.addAction(open_action)

        menu.addSeparator()

        # Management actions
        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(lambda: self._duplicate_plot(plot_data))
        menu.addAction(duplicate_action)

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_plot(plot_data))
        menu.addAction(rename_action)

        menu.addSeparator()

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_plot(plot_data))
        menu.addAction(remove_action)

        menu.exec(position)

    def _duplicate_plot(self, plot_data: dict):
        """Duplicate a plot."""
        new_plot_data = plot_data.copy()
        new_plot_data["id"] = f"plot_{self.plot_counter}"
        new_plot_data["title"] = f"{plot_data['title']} (Copy)"
        self.plot_counter += 1

        self.stored_plots.append(new_plot_data)
        self._add_plot_thumbnail(new_plot_data)

    def _rename_plot(self, plot_data: dict):
        """Rename a plot."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Plot", "Enter new name:", text=plot_data["title"]
        )

        if ok and new_name:
            # Update plot data
            for plot in self.stored_plots:
                if plot["id"] == plot_data["id"]:
                    plot["title"] = new_name
                    break

            # Refresh thumbnails
            self._refresh_thumbnails()

            # Update popup window title if open
            if plot_data["id"] in self.popup_windows:
                popup = self.popup_windows[plot_data["id"]]
                if popup:
                    popup.setWindowTitle(f"Spectral Plot - {new_name}")

    def _remove_plot(self, plot_data: dict):
        """Remove a plot."""
        reply = QMessageBox.question(
            self,
            "Remove Plot",
            f"Remove plot '{plot_data['title']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Close popup if open
            if plot_data["id"] in self.popup_windows:
                popup = self.popup_windows[plot_data["id"]]
                if popup:
                    popup.close()

            # Remove from stored plots
            self.stored_plots = [
                p for p in self.stored_plots if p["id"] != plot_data["id"]
            ]

            # Update active plot if this was it
            if self.active_plot_id == plot_data["id"]:
                self.active_plot_id = None

            # Refresh thumbnails
            self._refresh_thumbnails()

    def _clear_all_plots(self):
        """Clear all stored plots."""
        if not self.stored_plots:
            return

        reply = QMessageBox.question(
            self,
            "Clear All Plots",
            f"Remove all {len(self.stored_plots)} plots?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Close all popups
            for popup in list(self.popup_windows.values()):
                if popup:
                    popup.close()
            self.popup_windows.clear()

            # Clear data
            self.stored_plots.clear()
            self.active_plot_id = None

            # Refresh UI
            self._refresh_thumbnails()

    def _export_plots(self):
        """Export plot data."""
        QMessageBox.information(
            self,
            "Export Plots",
            "Plot export functionality will be implemented here.\n"
            "Will support CSV, JSON, and image export formats.",
        )

    def _export_all_plots(self):
        """Export all plot data."""
        if not self.stored_plots:
            QMessageBox.information(self, "No Plots", "No plots to export.")
            return

        QMessageBox.information(
            self,
            "Export All Plots",
            f"Export functionality for all {len(self.stored_plots)} plots will be implemented here.\n"
            "Will support CSV, JSON, and image export formats.",
        )

    def _merge_selected_plots(self):
        """Merge selected plots into a single plot window and create merged thumbnail."""
        if len(self.selected_plots) < 2:
            QMessageBox.information(
                self, "Merge Plots", "Please select at least 2 plots to merge."
            )
            return

        # Get selected plot data
        selected_plot_data = [
            plot for plot in self.stored_plots if plot["id"] in self.selected_plots
        ]

        if not selected_plot_data:
            return

        # Create merged plot data with multiple spectra info
        merged_plot_data = {
            "id": f"merged_{self.plot_counter}",
            "title": f"Merged Plot ({len(selected_plot_data)} spectra)",
            "coords": selected_plot_data[0][
                "coords"
            ],  # Use first plot's coords as reference
            "image_index": selected_plot_data[0]["image_index"],
            "timestamp": str(QDateTime.currentDateTime().toString()),
            "is_merged": True,
            "merged_spectra": selected_plot_data,  # Store all plot data for loading
        }
        self.plot_counter += 1

        # Option 1: Open plot window with merged data (existing behavior)
        popup = PlotWindow(merged_plot_data, self.project_context, self)
        popup.show()
        popup.raise_()
        popup.activateWindow()

        # Option 2: Also create a merged thumbnail in the manager (NEW)
        # Ask user if they want to create a merged thumbnail
        reply = QMessageBox.question(
            self,
            "Create Merged Thumbnail",
            f"Would you like to create a merged thumbnail in the Plot Manager?\n\n"
            f"This will create a single thumbnail representing all {len(selected_plot_data)} selected spectra.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Add merged plot to stored plots
            self.stored_plots.append(merged_plot_data)
            self._add_plot_thumbnail(merged_plot_data)

            # Clear the selection since we've created a new merged plot
            self._clear_all_selections()

        logger.debug(f"Created merged plot with {len(selected_plot_data)} spectra")

    def _on_drag_merge_requested(self, source_plot_id: str, target_plot_id: str):
        """Handle drag-and-drop merge request between two plots."""
        # Find the source and target plot data
        source_plot = None
        target_plot = None

        for plot in self.stored_plots:
            if plot["id"] == source_plot_id:
                source_plot = plot
            elif plot["id"] == target_plot_id:
                target_plot = plot

        if not source_plot or not target_plot:
            logger.error(
                f"Could not find plots for merge: source={source_plot_id}, target={target_plot_id}"
            )
            return

        # Ask user for confirmation
        reply = QMessageBox.question(
            self,
            "Merge Plots",
            f"Merge '{source_plot['title']}' into '{target_plot['title']}'?\n\n"
            f"This will create a new merged plot with both spectra.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Create merged plot data
        merged_plot_data = {
            "id": f"merged_{self.plot_counter}",
            "title": f"Merged: {target_plot['title']} + {source_plot['title']}",
            "coords": target_plot["coords"],  # Use target plot's coords as reference
            "image_index": target_plot["image_index"],
            "timestamp": str(QDateTime.currentDateTime().toString()),
            "is_merged": True,
            "merged_spectra": [target_plot, source_plot],  # Target first, then source
        }
        self.plot_counter += 1

        # Add merged plot to stored plots and create thumbnail
        self.stored_plots.append(merged_plot_data)
        self._add_plot_thumbnail(merged_plot_data)

        # Option: Also open the merged plot window
        popup = PlotWindow(merged_plot_data, self.project_context, self)
        popup.show()
        popup.raise_()
        popup.activateWindow()

        logger.info(
            f"Created drag-merged plot: {source_plot['title']} + {target_plot['title']}"
        )

        # Optional: Remove the original plots
        remove_originals = QMessageBox.question(
            self,
            "Remove Original Plots",
            f"Would you like to remove the original plots?\n\n"
            f"• {source_plot['title']}\n"
            f"• {target_plot['title']}\n\n"
            f"The merged plot will remain.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if remove_originals == QMessageBox.StandardButton.Yes:
            # Remove original plots
            self.stored_plots = [
                plot
                for plot in self.stored_plots
                if plot["id"] not in [source_plot_id, target_plot_id]
            ]

            # Close any open popups for the removed plots
            for plot_id in [source_plot_id, target_plot_id]:
                if plot_id in self.popup_windows:
                    popup = self.popup_windows[plot_id]
                    if popup:
                        popup.close()
                    del self.popup_windows[plot_id]

            # Refresh thumbnails
            self._refresh_thumbnails()

            logger.info(f"Removed original plots after merge")

    def _pin_plot(self, plot_id: str):
        """Pin a plot to make it the active plot for updates."""
        # Unpin any currently pinned plot
        if self.pinned_plot_id:
            self._unpin_plot(self.pinned_plot_id)

        # Pin the new plot
        self.pinned_plot_id = plot_id

        # If we're in update mode, this becomes the active plot immediately
        if self.update_existing:
            self.active_plot_id = plot_id
            logger.debug(f"Pinned plot {plot_id} as active plot (update mode)")
        else:
            # In create mode, just pin it for when we switch to update mode
            logger.debug(
                f"Pinned plot {plot_id} (will be active when switching to update mode)"
            )

        # Update visual indicator
        thumb = self._get_thumbnail_widget(plot_id)
        if thumb:
            thumb.set_pinned(True)

        # Update UI state
        self._update_pin_buttons()

    def _unpin_plot(self, plot_id: str):
        """Unpin a plot."""
        if plot_id == self.pinned_plot_id:
            self.pinned_plot_id = None

            # If we're in update mode, keep this as active but unpinned
            if self.update_existing:
                self.active_plot_id = plot_id
            else:
                self.active_plot_id = None

        # Update visual indicator
        thumb = self._get_thumbnail_widget(plot_id)
        if thumb:
            thumb.set_pinned(False)

        # Update UI state
        self._update_pin_buttons()

        logger.debug(f"Unpinned plot {plot_id}")

    def _unpin_all_plots(self):
        """Unpin all plots."""
        if self.pinned_plot_id:
            self._unpin_plot(self.pinned_plot_id)

    def _update_pin_buttons(self):
        """Update pin button states based on current selection and pin state."""
        has_selection = len(self.selected_plots) > 0
        single_selected = len(self.selected_plots) == 1
        has_pinned = self.pinned_plot_id is not None

        # Update button states (buttons will be created next)
        if hasattr(self, "pin_selected_button"):
            self.pin_selected_button.setEnabled(
                single_selected and self.update_existing
            )
        if hasattr(self, "unpin_all_button"):
            self.unpin_all_button.setEnabled(has_pinned)

    def _delete_selected_plots(self):
        """Delete selected plots."""
        if not self.selected_plots:
            QMessageBox.information(
                self, "No Selection", "No plots selected for deletion."
            )
            return

        # Get selected plot titles for confirmation
        selected_titles = [
            plot["title"]
            for plot in self.stored_plots
            if plot["id"] in self.selected_plots
        ]

        reply = QMessageBox.question(
            self,
            "Delete Selected Plots",
            f"Delete {len(selected_titles)} selected plots?\n\n"
            + "\n".join(f"• {title}" for title in selected_titles[:5])
            + (
                f"\n... and {len(selected_titles) - 5} more"
                if len(selected_titles) > 5
                else ""
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Close any open popups for selected plots
            for plot_id in self.selected_plots:
                if plot_id in self.popup_windows:
                    popup = self.popup_windows[plot_id]
                    if popup:
                        popup.close()
                    del self.popup_windows[plot_id]

            # Remove selected plots from stored plots
            self.stored_plots = [
                plot
                for plot in self.stored_plots
                if plot["id"] not in self.selected_plots
            ]

            # Update active plot if it was deleted
            if self.active_plot_id in self.selected_plots:
                self.active_plot_id = None

            # Clear selection and refresh
            self.selected_plots.clear()
            self._refresh_thumbnails()
            self._update_selection_buttons()

            logger.debug(f"Deleted {len(selected_titles)} plots")

    def _export_selected_plots(self):
        """Export selected plots."""
        if not self.selected_plots:
            QMessageBox.information(
                self, "No Selection", "No plots selected for export."
            )
            return

        selected_titles = [
            plot["title"]
            for plot in self.stored_plots
            if plot["id"] in self.selected_plots
        ]

        QMessageBox.information(
            self,
            "Export Selected Plots",
            f"Export functionality for {len(selected_titles)} selected plots will be implemented here.\n"
            "Will support CSV, JSON, and image export formats.\n\n"
            "Selected plots:\n"
            + "\n".join(f"• {title}" for title in selected_titles[:5])
            + (
                f"\n... and {len(selected_titles) - 5} more"
                if len(selected_titles) > 5
                else ""
            ),
        )

    def _open_current_advanced(self):
        """Open current plot in advanced window."""
        if not self.lastPixelCoords:
            QMessageBox.information(self, "No Plot", "No current plot to open.")
            return

        # Create temporary plot data
        x, y = self.lastPixelCoords
        temp_plot_data = {
            "id": "current_temp",
            "coords": (x, y),
            "image_index": self.imageIndex,
            "title": f"Current Pixel ({x}, {y})",
        }

        # Open advanced popup
        popup = PlotWindow(temp_plot_data, self.project_context, self)
        popup.show()

    def _show_current_properties(self):
        """Show properties panel for current plot."""
        if not hasattr(self.current_plot, "properties_panel"):
            # Add properties panel to current plot
            properties_panel = SpectralPropertiesPanel(self.current_plot, self)
            self.current_plot.properties_panel = properties_panel

        # Create popup window for properties
        properties_window = QWidget()
        properties_window.setWindowTitle("Current Plot Properties")
        properties_layout = QVBoxLayout(properties_window)
        properties_layout.addWidget(self.current_plot.properties_panel)
        properties_window.resize(400, 600)
        properties_window.show()

    def handlePixelPlotClicked(self):
        """Handle pixel plot click - delegate to parent control panel."""
        if hasattr(self.parent_control_panel, "handlePixelPlotClicked"):
            self.parent_control_panel.handlePixelPlotClicked()

    def setup_view_click_handlers(self, raster_view):
        """Set up click handlers for different views."""
        self.raster_view = raster_view

        # Store original click handlers
        self._original_zoom_click = getattr(
            raster_view.zoomImage, "mouseClickEvent", None
        )

        # Set up custom click handlers for each view
        if hasattr(raster_view, "contextImage"):
            raster_view.contextImage.mouseClickEvent = (
                lambda event: self._handle_context_click(event, raster_view)
            )

        if hasattr(raster_view, "mainImage"):
            raster_view.mainImage.mouseClickEvent = (
                lambda event: self._handle_main_click(event, raster_view)
            )

        if hasattr(raster_view, "zoomImage"):
            raster_view.zoomImage.mouseClickEvent = (
                lambda event: self._handle_zoom_click(event, raster_view)
            )

    def _handle_context_click(self, event, raster_view):
        """Handle clicks on context view."""
        if not self.context_enabled:
            return

        # Call original handling logic similar to zoom click
        self._process_click_event(event, raster_view, "context")

    def _handle_main_click(self, event, raster_view):
        """Handle clicks on main view."""
        if not self.main_enabled:
            return

        self._process_click_event(event, raster_view, "main")

    def _handle_zoom_click(self, event, raster_view):
        """Handle clicks on zoom view."""
        if not self.zoom_enabled:
            return

        # Call original zoom click logic
        if self._original_zoom_click:
            self._original_zoom_click(event)
        else:
            self._process_click_event(event, raster_view, "zoom")

    def _process_click_event(self, event, raster_view, view_type):
        """Process click event for any view type."""
        from PyQt6.QtCore import Qt

        if event.button() == Qt.MouseButton.LeftButton:
            if view_type == "zoom":
                # Use existing zoom logic
                pos = raster_view.zoomImage.mapFromScene(event.scenePos())
                x, y = int(pos.x()), int(pos.y())
                final_x, final_y = raster_view._zoomCoordsToAbsolute(x, y)
            else:
                # For context and main views, we need different coordinate mapping
                if view_type == "context":
                    pos = raster_view.contextImage.mapFromScene(event.scenePos())
                    # Context coordinates are already in absolute image space
                    final_x, final_y = int(pos.x()), int(pos.y())
                elif view_type == "main":
                    pos = raster_view.mainImage.mapFromScene(event.scenePos())
                    # Main coordinates need to be converted to absolute
                    final_x = int(raster_view.contextROI.pos().x() + pos.x())
                    final_y = int(raster_view.contextROI.pos().y() + pos.y())

            # Update crosshair if it's zoom view
            if view_type == "zoom" and hasattr(raster_view, "_updateCrosshair"):
                raster_view._updateCrosshair(x, y)

            # Emit the click signal
            raster_view.sigImageClicked.emit(final_x, final_y)

        event.accept()

    def closeEvent(self, event):
        """Clean up all popup windows when the tab is closed."""
        for popup in list(self.popup_windows.values()):
            if popup and popup.isVisible():
                popup.close()

        self.popup_windows.clear()
        super().closeEvent(event)
