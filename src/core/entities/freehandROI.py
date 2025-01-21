from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class FreeHandROI:
    """Data container holding an ROI for an image."""
    """Will hold a list of points that can be transformed into an ROI object"""
    
    points : None
    color : str
    imageIndex : int
    arraySlice : np.ndarray
    
    def toList(self):
        return [ x for x in self.points ]
    
    def getColor(self):
        return self.color
    
    def getArraySlice(self):
        return self.arraySlice
    
    def toStr(self):
        return self.color + " ROI for image " + str(self.imageIndex) + " with points " + \
                self.points