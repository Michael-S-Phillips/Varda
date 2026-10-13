# Sessions and saving results

## Sessions

**File → Save Session…** (⌘S) writes a `.varda` file recording the open
images (by path), the open workspaces and their ROIs. **File → Open Session…**
(⌘O) loads the images and reopens the workspaces alongside whatever is already
open. Images that exist only in memory (analysis results you have not
exported) are left out, so export them first, or save a session bundle
(`.varda.zip`), which carries them along.

Varda also autosaves the session every three minutes and on quit (to
`autosave.varda` in its app-data folder, next to the logs). After a crash,
**File → Restore Last Session** brings it back.

## Saving results

Every Processing result joins the project's image list. Tick **Save result to
file** in the analysis dialog to also write it to disk (ENVI `.img`/`.hdr` or
GeoTIFF), or export any image later with **File → Export Image…** or by
right-clicking an image → **Export Image…**.

Results record how they were made (the analysis, its settings, the input
images and the Varda version), and exported files keep that record in their
description.
