# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

macOS menu bar app that displays your public IP's country flag, with a draggable floating bubble showing the flag, country code, and real-time network upload/download speed. Built with Python using `rumps` (menu bar framework) and PyObjC (native macOS AppKit bindings).

## Commands

```bash
# Run the app (requires macOS with GUI)
./start.sh
# Or directly:
source .venv/bin/activate && python3 ip_location.py

# Build .app bundle + DMG for distribution
./build_dmg.sh

# Regenerate the app icon (AppIcon.icns)
python3 gen_icon.py

# Set up venv (PyObjC is pulled in transitively by rumps; not listed in requirements.txt)
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

No tests exist in this project.

## Architecture

Single-file app (`ip_location.py`) with these key components:

- **IP providers**: 4 fallback providers (`ipinfo.io`, `ip-api.com`, `ifconfig.co`, `api.myip.com`) tried in order; each returns `(ip, cc, cn, region, city)`
- **Menu bar app**: `IPLocationApp(rumps.App)` — manages menu items, polling timer, and the bubble window
- **Floating bubble**: `CircleBubbleView(NSView)` — a circular NSPanel at `NSStatusWindowLevel` with flag emoji background, country code, and speed labels. Supports drag-to-reposition (saved to `config.json`) and right-click context menu
- **Network speed**: Background thread polls `netstat -ib` every 2 seconds, parses Ibytes/Obytes columns
- **Auto-start**: Manages a LaunchAgent plist (`com.chiyou.ip-location`) for login launch
- **Single instance**: File lock at `.ip_location.lock` with PID tracking; kills previous instance on start

All UI updates from background threads go through `AppHelper.callAfter()` to run on the main thread. Country changes trigger macOS notifications via `osascript`.

## Key Details

- Config stored in `config.json` (refresh interval, bubble position)
- China/HK/MO/TW get special display names with region detail for CN
- The app hides its Dock icon via `NSApplicationActivationPolicyAccessory`
- `build_dmg.sh` copies the entire `.venv` into the .app bundle — no PyInstaller/py2app needed; requires `.venv` to already exist
- Bubble position is validated against connected screens on launch; resets if off-screen
- LaunchAgent logs: `/tmp/ip-location.log` (stdout), `/tmp/ip-location.err` (stderr)
- The launcher script in the .app bundle must NOT use `exec` — it breaks LaunchServices' association, causing the menu bar icon to not appear
