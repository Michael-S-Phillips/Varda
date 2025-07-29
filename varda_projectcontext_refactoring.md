# ProjectContext Refactoring Plan

## Current State Analysis

The `ProjectContext` class in Varda is becoming a "god object" with too many responsibilities:

1. **Project Management**: Loading, saving, and managing project data
2. **Image Management**: Adding, removing, and retrieving images
3. **Metadata Management**: Updating image metadata
4. **Band Management**: Adding, removing, and updating band configurations
5. **Stretch Management**: Adding, removing, and updating stretch configurations
6. **Plot Management**: Adding and retrieving plots
7. **Change Notification**: Emitting signals when data changes
8. **ROI Management**: Delegating to ROIManager (already extracted)

## Proposed Refactoring

### 1. Service Extraction Strategy

The refactoring will follow these principles:
- Each service should have a single responsibility
- Services should be loosely coupled
- Services should communicate through well-defined interfaces
- The ProjectContext should coordinate between services but not implement their functionality

### 2. Services to Extract

#### 2.1. ImageService

**Responsibilities**:
- Loading images from files
- Creating Image objects
- Retrieving images by index
- Adding and removing images

**Key Methods**:
- `loadImage(path)`: Load an image from a file
- `createImage(raster, metadata, ...)`: Create a new Image object
- `getImage(index)`: Get an image by index
- `getAllImages()`: Get all images
- `addImage(image)`: Add an image to the collection
- `removeImage(index)`: Remove an image

#### 2.2. BandService

**Responsibilities**:
- Managing band configurations for images
- Creating default bands
- Adding, removing, and updating bands

**Key Methods**:
- `addBand(imageIndex, band)`: Add a band to an image
- `removeBand(imageIndex, bandIndex)`: Remove a band
- `updateBand(imageIndex, bandIndex, ...)`: Update band parameters
- `createDefaultBand()`: Create a default band configuration

#### 2.3. StretchService

**Responsibilities**:
- Managing stretch configurations for images
- Creating default and preset stretches
- Adding, removing, and updating stretches

**Key Methods**:
- `addStretch(imageIndex, stretch)`: Add a stretch to an image
- `removeStretch(imageIndex, stretchIndex)`: Remove a stretch
- `updateStretch(imageIndex, stretchIndex, ...)`: Update stretch parameters
- `createDefaultStretch()`: Create a default stretch
- `createPresetStretches(raster, band)`: Create preset stretches for an image

#### 2.4. PlotService

**Responsibilities**:
- Creating and managing plots
- Associating plots with ROIs and images

**Key Methods**:
- `addPlot(roi)`: Create a plot from an ROI
- `getPlots(imageIndex)`: Get all plots for an image
- `removePlot(imageIndex, plotIndex)`: Remove a plot

#### 2.5. ProjectPersistenceService

**Responsibilities**:
- Saving and loading projects
- Managing project metadata
- Handling file dialogs and user interactions related to project files

**Key Methods**:
- `saveProject(project, saveAs)`: Save a project to disk
- `loadProject(path)`: Load a project from disk
- `getProjectName()`: Get the name of the current project

### 3. Revised ProjectContext

The refactored ProjectContext will:
1. Hold references to all services
2. Coordinate between services
3. Maintain the project state
4. Emit signals when data changes
5. Provide a facade for common operations

## Implementation Example

### Example 1: ImageService

```python
# varda/app/image/image_service.py
import logging
import os
from typing import List, Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from varda.core.entities import Image, Metadata, Band, Stretch
from varda.app.image import ImageLoadingService

logger = logging.getLogger(__name__)

class ImageService(QObject):
    """Service for managing images in the application."""
    
    sigImageAdded = pyqtSignal(int)  # Image index
    sigImageRemoved = pyqtSignal(int)  # Image index
    sigImageUpdated = pyqtSignal(int)  # Image index
    
    def __init__(self, imageLoadingService: ImageLoadingService):
        super().__init__()
        self._images: List[Image] = []
        self._imageLoadingService = imageLoadingService
        
    def loadImage(self, path: Optional[str] = None, callback=None):
        """
        Load an image from the given path.
        
        Args:
            path: Optional path to the image file. If None, a file dialog will be shown.
            callback: Optional callback function to call with the created image index.
        """
        self._imageLoadingService.loadImageData(path, 
            lambda raster, metadata, **kwargs: 
                callback(self.createImage(raster, metadata, **kwargs)) if callback else 
                self.createImage(raster, metadata, **kwargs)
        )
    
    def createImage(
        self,
        raster: np.ndarray,
        metadata: Metadata,
        stretch: List[Stretch] = None,
        band: List[Band] = None,
        **kwargs
    ) -> int:
        """
        Creates a new image with the given parameters.
        
        Args:
            raster: The image raster data.
            metadata: The image metadata.
            stretch: Optional list of stretch configurations.
            band: Optional list of band configurations.
            **kwargs: Additional parameters for the Image constructor.
            
        Returns:
            int: The index of the created image.
        """
        # Set a unique name for the image
        if metadata.filePath:
            base_name = os.path.basename(metadata.filePath)
            metadata.name = os.path.splitext(base_name)[0]
        elif not metadata.name:
            metadata.name = f"Image {len(self._images)}"
            
        # Create default bands if not provided
        if not band:
            if metadata.defaultBand:
                band = [metadata.defaultBand]
            else:
                band = [Band.createDefault()]
                
        # Create the image
        image = Image(
            raster=raster,
            metadata=metadata,
            stretch=stretch if stretch else [],
            band=band,
            rois=[],
            plots=[],
            index=len(self._images),
            **kwargs
        )
        
        return self.addImage(image)
    
    def addImage(self, image: Image) -> int:
        """
        Add an image to the collection.
        
        Args:
            image: The image to add.
            
        Returns:
            int: The index of the added image.
        """
        index = len(self._images)
        self._images.append(image)
        self.sigImageAdded.emit(index)
        return index
        
    def removeImage(self, index: int) -> bool:
        """
        Remove an image by index.
        
        Args:
            index: The index of the image to remove.
            
        Returns:
            bool: True if the image was removed, False otherwise.
        """
        if index < 0 or index >= len(self._images):
            logger.warning(f"Invalid image index: {index}")
            return False
            
        self._images.pop(index)
        self.sigImageRemoved.emit(index)
        return True
        
    def getImage(self, index: int) -> Optional[Image]:
        """
        Get an image by index.
        
        Args:
            index: The index of the image.
            
        Returns:
            Image: The image, or None if not found.
        """
        if index < 0 or index >= len(self._images):
            logger.warning(f"Invalid image index: {index}")
            return None
            
        return self._images[index]
        
    def getAllImages(self) -> List[Image]:
        """
        Get all images.
        
        Returns:
            List[Image]: List of all images.
        """
        return self._images
```

### Example 2: Refactored ProjectContext

```python
# varda/app/project/project_context.py
import logging
from typing import List, Optional, Any
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from varda.core.entities import Project, Image, Metadata, Band, Stretch, Plot
from varda.app.image import ImageService
from varda.app.project.roi_manager import ROIManager
from varda.app.project.band_service import BandService
from varda.app.project.stretch_service import StretchService
from varda.app.project.plot_service import PlotService
from varda.app.project.project_persistence_service import ProjectPersistenceService

logger = logging.getLogger(__name__)

class ProjectContext(QObject):
    """
    Coordinates the services that manage project data.
    
    Acts as a facade for the underlying services and maintains the overall project state.
    """
    
    class ChangeType(Enum):
        """Enumerator to represent the types of data that may be changed"""
        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"
        PLOT = "plot"
        
    class ChangeModifier(Enum):
        """Enumerator to represent the ways in which data may be changed"""
        ADD = "add"
        REMOVE = "remove"
        UPDATE = "update"
        
    # Signal that emits when something changes in the project
    sigDataChanged = pyqtSignal([int, ChangeType], [int, ChangeType, ChangeModifier])
    sigProjectChanged = pyqtSignal()
    
    def __init__(
        self,
        imageService: ImageService,
        roiManager: ROIManager,
        bandService: BandService,
        stretchService: StretchService,
        plotService: PlotService,
        projectPersistenceService: ProjectPersistenceService
    ):
        super().__init__()
        self._projectData = Project()
        self.isSaved = True
        
        # Services
        self._imageService = imageService
        self.roiManager = roiManager
        self._bandService = bandService
        self._stretchService = stretchService
        self._plotService = plotService
        self._projectPersistenceService = projectPersistenceService
        
        # Connect signals from services to our change notification system
        self._connectServiceSignals()
        
    def _connectServiceSignals(self):
        """Connect signals from services to our change notification system."""
        # Image service signals
        self._imageService.sigImageAdded.connect(
            lambda index: self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.ADD)
        )
        self._imageService.sigImageRemoved.connect(
            lambda index: self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.REMOVE)
        )
        self._imageService.sigImageUpdated.connect(
            lambda index: self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.UPDATE)
        )
        
        # Similar connections for other services...
        
    # Project operations (delegated to ProjectPersistenceService)
    def getProjectName(self):
        """Get the name of the current project."""
        return self._projectPersistenceService.getProjectName()
        
    def saveProject(self, saveAs=False):
        """Save the current project."""
        # Update project data with current state
        self._projectData.images = self._imageService.getAllImages()
        self._projectData.roiManager = self.roiManager
        
        success = self._projectPersistenceService.saveProject(self._projectData, saveAs)
        if success:
            self.isSaved = True
            self.sigProjectChanged.emit()
        return success
        
    def loadProject(self, loadPath=None):
        """Load a project from a file."""
        # Handle unsaved changes
        if not self.isSaved:
            if not self._handleUnsavedChanges():
                return False
                
        # Load the project
        success, project = self._projectPersistenceService.loadProject(loadPath)
        if not success:
            return False
            
        # Update the application state with the loaded project
        self._projectData = project
        
        # Clear current state
        self._imageService.clear()
        self.roiManager.clear()
        
        # Load images
        for image in project.images:
            self._imageService.addImage(image)
            
        # Load ROI manager if available
        if hasattr(project, "roiManager"):
            self.roiManager = project.roiManager
            
        self.sigProjectChanged.emit()
        return True
        
    # Image operations (delegated to ImageService)
    def getImage(self, index):
        """Get an image by index."""
        return self._imageService.getImage(index)
        
    def getAllImages(self):
        """Get all images."""
        return self._imageService.getAllImages()
        
    def loadNewImage(self, path=None):
        """Load a new image from a file."""
        self._imageService.loadImage(path)
        
    def createImage(self, raster, metadata, **kwargs):
        """Create a new image."""
        return self._imageService.createImage(raster, metadata, **kwargs)
        
    def removeImage(self, index):
        """Remove an image by index."""
        # First remove all ROIs associated with this image
        rois = self.roiManager.getROIsForImage(index)
        for roi in rois:
            self.roiManager.removeROI(roi.id)
            
        # Then remove the image
        self._imageService.removeImage(index)
        
    # Metadata operations
    def updateMetadata(self, index, key, value):
        """Update image metadata."""
        image = self._imageService.getImage(index)
        if not image:
            return False
            
        metadata = image.metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
            
        self._emitChange(index, self.ChangeType.METADATA, self.ChangeModifier.UPDATE)
        return True
        
    # Other operations delegated to respective services...
    
    # Helper methods
    def _emitChange(self, index, changeType, changeModifier=None):
        """Emit a data change signal."""
        self.isSaved = False
        
        if changeModifier is not None:
            self.sigDataChanged[int, self.ChangeType, self.ChangeModifier].emit(
                index, changeType, changeModifier
            )
        self.sigDataChanged[int, self.ChangeType].emit(index, changeType)
        
    def _handleUnsavedChanges(self):
        """Handle unsaved changes before loading a new project."""
        # Implementation of dialog to ask user about saving changes
        # Returns True if it's OK to proceed, False to cancel
        return True
```

## Implementation Strategy

### 1. Phased Approach

The refactoring should be done incrementally to minimize disruption:

1. **Phase 1: Extract ROIManager** (already done)
   - ROI management has already been extracted to a separate class

2. **Phase 2: Extract ImageService**
   - Move image loading, creation, and management to a separate service
   - Update ProjectContext to use the new service
   - This is a good first step as image management is a core functionality

3. **Phase 3: Extract BandService and StretchService**
   - Move band and stretch management to separate services
   - These are closely related to images but have distinct responsibilities

4. **Phase 4: Extract PlotService**
   - Move plot creation and management to a separate service

5. **Phase 5: Extract ProjectPersistenceService**
   - Move project loading and saving to a separate service
   - This can be done last as it's more isolated from other functionality

### 2. Dependency Injection

- Use constructor injection to provide services to ProjectContext
- This makes dependencies explicit and improves testability
- Update the composition root (bootstrap.py) to create and wire services

### 3. Signal Coordination

- Each service should emit its own signals for specific events
- ProjectContext should connect to these signals and translate them to its own signals
- This maintains backward compatibility with existing code

### 4. Backward Compatibility

- ProjectContext should maintain its current public API
- It should delegate to the appropriate services internally
- This allows for gradual migration without breaking existing code

## Benefits of This Approach

1. **Improved Maintainability**: Each service has a single responsibility
2. **Better Testability**: Services can be tested in isolation
3. **Reduced Complexity**: ProjectContext becomes a coordinator rather than implementing everything
4. **Easier Extension**: New functionality can be added by creating new services
5. **Better Separation of Concerns**: Clear boundaries between different parts of the system

## Potential Challenges

1. **Circular Dependencies**: Be careful to avoid circular dependencies between services
2. **Signal Handling**: Ensure signals are properly connected and don't cause infinite loops
3. **State Synchronization**: Maintain consistent state across services
4. **Migration Complexity**: Gradual migration requires careful planning and testing

## Conclusion

Refactoring ProjectContext into smaller, focused services will significantly improve the maintainability and extensibility of the Varda application. The ROIManager is already a good example of this approach, and similar patterns can be applied to other responsibilities of ProjectContext.

By following a phased approach and maintaining backward compatibility, the refactoring can be done incrementally with minimal disruption to the existing codebase.