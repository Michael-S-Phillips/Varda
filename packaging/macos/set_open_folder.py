"""Make Finder open a window on a disk image's volume when it is mounted.

Finder opens the folder named in the HFS+ volume header's Finder info
(word 2, a big-endian folder ID; TN1150). `bless --openfolder` no longer sets
it on Apple silicon and APFS has no such field, so build the image as
read-write HFS+, mount it, run this on the mount point, then compress it.

    python set_open_folder.py /path/to/mounted/volume
    python set_open_folder.py --check /path/to/mounted/volume   # set already?

Same approach as https://github.com/jwwalker/SetDmgOpenFolder.
"""

import ctypes
import os
import struct
import sys

ATTR_BIT_MAP_COUNT = 5
ATTR_CMN_FNDRINFO = 0x00004000
ATTR_VOL_INFO = 0x80000000  # the volume's own Finder info, not its root folder's
OPEN_FOLDER_OFFSET = 8  # finderInfo[2]


class AttrList(ctypes.Structure):
    _fields_ = [
        ("bitmapcount", ctypes.c_ushort),
        ("reserved", ctypes.c_ushort),
        ("commonattr", ctypes.c_uint32),
        ("volattr", ctypes.c_uint32),
        ("dirattr", ctypes.c_uint32),
        ("fileattr", ctypes.c_uint32),
        ("forkattr", ctypes.c_uint32),
    ]


libc = ctypes.CDLL(None, use_errno=True)
VOLUME_FINDER_INFO = AttrList(
    ATTR_BIT_MAP_COUNT, 0, ATTR_CMN_FNDRINFO, ATTR_VOL_INFO, 0, 0, 0
)


def _check(result: int, action: str) -> None:
    if result != 0:
        raise OSError(
            ctypes.get_errno(), f"{action}: {os.strerror(ctypes.get_errno())}"
        )


def readFinderInfo(volume: str) -> bytes:
    buffer = ctypes.create_string_buffer(4 + 32)  # length, then the 32 bytes
    _check(
        libc.getattrlist(
            volume.encode(), ctypes.byref(VOLUME_FINDER_INFO), buffer, 36, 0
        ),
        f"reading Finder info of {volume}",
    )
    return buffer.raw[4:36]


def openFolder(volume: str) -> int:
    """The folder ID Finder opens when the volume mounts (0 for none)."""
    info = readFinderInfo(volume)
    return struct.unpack_from(">I", info, OPEN_FOLDER_OFFSET)[0]


def setOpenFolder(volume: str) -> None:
    """Make Finder open the volume's root window on mount."""
    info = bytearray(readFinderInfo(volume))
    struct.pack_into(">I", info, OPEN_FOLDER_OFFSET, os.stat(volume).st_ino)
    buffer = ctypes.create_string_buffer(bytes(info), 32)
    _check(
        libc.setattrlist(
            volume.encode(), ctypes.byref(VOLUME_FINDER_INFO), buffer, 32, 0
        ),
        f"setting Finder info of {volume}",
    )


if __name__ == "__main__":
    check = sys.argv[1] == "--check"
    volume = sys.argv[-1]
    if not os.path.ismount(volume):
        sys.exit(f"{volume} is not a mounted volume")
    if not check:
        setOpenFolder(volume)
    folder = openFolder(volume)
    if folder != os.stat(volume).st_ino:
        sys.exit(
            f"{volume}: Finder won't open a window on mount (open folder {folder})"
        )
    print(f"{volume}: Finder opens folder {folder} on mount")
