#!/bin/sh
# Builds "Freds LAN.app" in ~/Applications. It runs main.py from this folder through
# the venv, so rebuild after moving this folder.
set -eu
cd "$(dirname "$0")"
dir=$(pwd)
app="Freds LAN.app"
rm -rf "./$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp assets/AppIcon.icns "$app/Contents/Resources/AppIcon.icns"

cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>Freds LAN</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleIdentifier</key><string>work.nomonkey.fredslan</string>
  <key>CFBundleName</key><string>Freds LAN</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSLocalNetworkUsageDescription</key><string>Freds LAN scans your network to show the devices on it.</string>
  <key>NSLocationWhenInUseUsageDescription</key><string>macOS only shows Wi-Fi network names to apps allowed to use Location. Freds LAN doesn't use your location.</string>
</dict></plist>
PLIST

# The window runs this Python so the Dock shows this app instead of Python.app.
# It links through Homebrew's opt path so it survives Python patch upgrades.
base=$(.venv/bin/python -c 'import sys; print(sys.base_prefix)')
python="$app/Contents/MacOS/Freds LAN Python"
cp "$base/Resources/Python.app/Contents/MacOS/Python" "$python"
linked=$(otool -L "$python" | awk '/Python.framework/ {print $1}')
install_name_tool -change "$linked" "$(printf %s "$linked" | sed -E 's#Cellar/(python@[^/]+)/[^/]+#opt/\1#')" "$python" 2>/dev/null

launcher="$app/Contents/MacOS/Freds LAN"
{
  echo '#!/bin/sh'
  echo '# __PYVENV_LAUNCHER__ makes the bundled Python use the venv packages.'
  echo "export __PYVENV_LAUNCHER__=\"$dir/.venv/bin/python\""
  echo "exec \"\$(dirname \"\$0\")/Freds LAN Python\" \"$dir/main.py\""
} > "$launcher"
chmod +x "$launcher"
codesign --force --deep --sign - "$app"

mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/$app"
mv "$app" "$HOME/Applications/$app"
touch "$HOME/Applications/$app"
echo "Installed: $HOME/Applications/$app"
