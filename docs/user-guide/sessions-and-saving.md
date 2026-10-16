# Sessions and saving results

## Workspace tabs

Workspaces open as tabs, which work like a web browser's: drag a tab to
reorder it, drag it out of the tab bar (or double-click it) to open it in a
window of its own, and close it with its × or a middle click. Closing a
workspace's own window puts it back in the tabs. Sessions reopen the
workspaces in the tabs' order.

## Sessions

**File → Save Session…** (⌘S) writes a `.varda` file recording the open
images (by path), the open workspaces and their ROIs. **File → Open Session…**
(⌘O) loads the images and reopens the workspaces alongside whatever is already
open. Images that exist only in memory (analysis results you have not
exported) are left out, so export them first, or package the project.

Varda also autosaves the session every three minutes and on quit (to
`autosave.varda` in its app-data folder, next to the logs). After a crash,
**File → Restore Last Session** brings it back.

## Sharing a project

**File → Package Project…** puts the whole project into one `.varda.zip`
that anyone with Varda can open on their own computer (**File → Open
Session…**), as a packaged Illustrator document can be:

- the session: workspaces, their settings, ROIs and lines;
- every image file, with the files that belong to it (an ENVI header, a PDS
  label, GDAL's `.aux.xml`, world files), under their own names, so the
  pointers inside them still work;
- the other files workspaces use, such as a 3D Terrain workspace's line
  files;
- analysis results that exist only in memory, as ENVI files;
- `manifest.json`: the Varda version, the date, where each image came from,
  and every file's size and SHA-256 checksum, so a reader of your paper can
  check they're working with the same data.

Varda works out the size first. A package over 1 GB asks before it's
written, since it takes a while to write and many services limit how
large a shared file can be; it won't start if the disk lacks the room.
Files a workspace uses that can no longer be found are listed and left out.
Writing happens in the background, with its progress shown. The files are
compressed lightly: the four MISE example products (352 MB) package to
166 MB in a few seconds.

## Saving results

Every Processing result joins the project's image list. Tick **Save result to
file** in the analysis dialog to also write it to disk (ENVI `.img`/`.hdr` or
GeoTIFF), or export any image later with **File → Export Image…** or by
right-clicking an image → **Export Image…**.

Results record how they were made (the analysis, its settings, the input
images and the Varda version), and exported files keep that record in their
description.
