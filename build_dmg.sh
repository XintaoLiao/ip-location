#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export MACOSX_DEPLOYMENT_TARGET=12.0
APP_NAME="IP Location"
APP_BUNDLE="$SCRIPT_DIR/dist/${APP_NAME}.app"
DMG_NAME="IP-Location"
DMG_PATH="$SCRIPT_DIR/dist/${DMG_NAME}.dmg"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "==> Cleaning previous build..."
rm -rf "$SCRIPT_DIR/dist"
mkdir -p "$SCRIPT_DIR/dist"

echo "==> Creating .app bundle..."
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# --- Info.plist ---
cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>IP Location</string>
    <key>CFBundleDisplayName</key>
    <string>IP Location</string>
    <key>CFBundleIdentifier</key>
    <string>com.chiyou.ip-location</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSUIElement</key>
    <false/>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# --- Copy icon ---
if [ -f "$SCRIPT_DIR/AppIcon.icns" ]; then
    cp "$SCRIPT_DIR/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/"
fi

# --- Copy Python app and config ---
cp "$SCRIPT_DIR/ip_location.py" "$APP_BUNDLE/Contents/Resources/"
cp "$SCRIPT_DIR/config.json" "$APP_BUNDLE/Contents/Resources/"

# --- Rebuild venv with macOS 12 deployment target ---
echo "==> Creating clean venv with MACOSX_DEPLOYMENT_TARGET=12.0..."
BUNDLE_VENV="$APP_BUNDLE/Contents/Resources/.venv"
python3 -m venv "$BUNDLE_VENV"
MACOSX_DEPLOYMENT_TARGET=12.0 "$BUNDLE_VENV/bin/pip" install --upgrade pip
MACOSX_DEPLOYMENT_TARGET=12.0 "$BUNDLE_VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# --- Create launcher script ---
# Must use Python.app (GUI-capable) for NSStatusItem to work on macOS
cat > "$APP_BUNDLE/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
VENV="$DIR/.venv"
cd "$DIR"

# Check macOS version (require 12.0+)
macos_ver=$(sw_vers -productVersion)
major=$(echo "$macos_ver" | cut -d. -f1)
if [ "$major" -lt 12 ]; then
    osascript -e "display dialog \"IP Location requires macOS 12.0 or later. Current version: $macos_ver\" buttons {\"OK\"} default button \"OK\" with icon stop with title \"IP Location\""
    exit 1
fi

# Use venv's python3 directly — homebrew python auto-reexecs to Python.app (GUI-capable)
# Do NOT use exec — it breaks LaunchServices' association with the .app bundle,
# causing NSStatusItem (menu bar icon) to not appear.
"$VENV/bin/python3" -u "$DIR/ip_location.py"
LAUNCHER
chmod +x "$APP_BUNDLE/Contents/MacOS/launcher"

echo "==> App bundle created: $APP_BUNDLE"

# --- Create DMG ---
echo "==> Creating DMG..."

DMG_TEMP="$SCRIPT_DIR/dist/dmg_temp"
rm -rf "$DMG_TEMP" "$DMG_PATH"
mkdir -p "$DMG_TEMP"
cp -a "$APP_BUNDLE" "$DMG_TEMP/"
ln -s /Applications "$DMG_TEMP/Applications"

# Use hdiutil directly (simple, reliable)
hdiutil create -volname "$DMG_NAME" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDZO \
    -fs HFS+ \
    "$DMG_PATH"

rm -rf "$DMG_TEMP"

echo "==> Done! DMG created at: $DMG_PATH"
echo "==> Size: $(du -h "$DMG_PATH" | cut -f1)"
