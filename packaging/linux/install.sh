#!/bin/sh
# Add Varda to your applications menu (for your user only; no root needed).
# Run it from the unpacked Varda folder:   ./install.sh
# If you move the folder later, run it again from the new place.
# To undo: rm ~/.local/share/applications/varda.desktop
set -e
here="$(cd "$(dirname "$0")" && pwd)"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
apps="$data/applications"
icons="$data/icons/hicolor/scalable/apps"
mkdir -p "$apps" "$icons"
cp "$here/_internal/resources/brand/icon/varda-icon.svg" "$icons/varda.svg"
cat > "$apps/varda.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Varda
GenericName=Raster Image Analysis
Comment=Visualization and analysis of raster data
Exec="$here/Varda" %F
Icon=varda
Terminal=false
Categories=Science;Education;Graphics;
StartupWMClass=Varda
EOF
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$apps" || true
fi
echo "Varda is now in your applications menu."
