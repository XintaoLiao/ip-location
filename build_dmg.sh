#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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

# --- Copy entire venv ---
echo "==> Copying Python virtual environment..."
cp -a "$VENV_DIR" "$APP_BUNDLE/Contents/Resources/.venv"

# --- Create launcher script ---
cat > "$APP_BUNDLE/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
source "$DIR/.venv/bin/activate"
cd "$DIR"
exec python3 -u "$DIR/ip_location.py"
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
