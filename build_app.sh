#!/bin/sh
# Builds "LAN Scanner.app" and installs it in ~/Applications. It asks for an admin password
# and runs main.py, which keeps only the scan helper as root.
# The project path is stored in the app, so rebuild after moving this folder.
set -e
cd "$(dirname "$0")"
dir=$(pwd)
app="LAN Scanner.app"
rm -rf "$app"
osacompile -o "$app" -e "do shell script quoted form of \"$dir/.venv/bin/python\" & \" \" & quoted form of \"$dir/main.py\" with administrator privileges"

cp assets/AppIcon.icns "$app/Contents/Resources/applet.icns"
rm -f "$app/Contents/Resources/Assets.car"
plist="$app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string work.nomonkey.lanscanner" "$plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleName LAN Scanner" "$plist" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleName string LAN Scanner" "$plist"
# This launcher only starts the real window, which has its own Dock icon.
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$plist"
codesign --force --deep --sign - "$app"

mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/$app"
ditto "$app" "$HOME/Applications/$app"
touch "$HOME/Applications/$app"
echo "Installed: $HOME/Applications/$app"
