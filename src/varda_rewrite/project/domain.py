import os
import tempfile
from dataclasses import dataclass
from typing import List
import zipfile

from pydantic import BaseModel

from varda_rewrite.common.protocols import Savable


class Project(BaseModel):
    name: str
    dataStores: List[Savable]

    def save(self):
        tmpDir = tempfile.mkdtemp(prefix="varda_save_")
        tmpZip = os.path.join(tmpDir, "project.zip")

        with zipfile.ZipFile(tmpZip, "w", compression=zipfile.ZIP_DEFLATED) as zipObj:


    def load(self):
        pass
