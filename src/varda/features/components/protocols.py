import logging
from typing import Protocol

import pyqtgraph as pg
from PyQt6.QtCore import QObject, QPointF, pyqtSignal, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent, QIcon, QAction, QCursor
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from varda.common.entities import Image
from varda.image_rendering.raster_view import VardaImageItem

logger = logging.getLogger(__name__)





