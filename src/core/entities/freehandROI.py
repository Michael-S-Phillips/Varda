from dataclasses import dataclass

@dataclass(frozen=True)
class FreeHandROI:
    """Data container holding an ROI for an image."""
    """Will hold a list of points that can be transformed into an ROI object"""
    
    points : None
    color : None
    
    def toList(self):
        return [ x for x in self.points ]
    
    def getColor(self):
        return self.color