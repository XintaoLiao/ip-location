#!/usr/bin/env python3
"""
IP Location Menu Bar App
Shows your public IP's country flag in the macOS menu bar
with a circular Morandi-style floating bubble + network speed.
"""

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time

import requests
import rumps

import objc
from AppKit import (
    NSWindow,
    NSPanel,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSWindowStyleMaskUtilityWindow,
    NSBackingStoreBuffered,
    NSColor,
    NSTextField,
    NSFont,
    NSTextAlignmentCenter,
    NSFloatingWindowLevel,
    NSStatusWindowLevel,
    NSScreen,
    NSView,
    NSMakeRect,
    NSBezierPath,
    NSGradient,
    NSMakePoint,
    NSFontWeightMedium,
    NSFontWeightSemibold,
    NSApp,
)
from PyObjCTools import AppHelper


def run_on_main_thread(func):
    """Schedule a no-arg callable on the main thread."""
    AppHelper.callAfter(func)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Morandi palette gradient colors (muted, elegant)
MORANDI_TOP = (0.565, 0.537, 0.522, 0.92)     # warm taupe
MORANDI_BOTTOM = (0.424, 0.416, 0.435, 0.92)   # dusty mauve


# --- Region display names for China & special regions ---
# HK, MO, TW have their own country codes from APIs.
# For CN, we further detect region/city to show province-level detail.
REGION_DISPLAY = {
    "CN": ("🇨🇳", "CN", "中国大陆"),
    "HK": ("🇭🇰", "HK", "中国香港"),
    "MO": ("🇲🇴", "MO", "中国澳门"),
    "TW": ("🇹🇼", "TW", "中国台湾"),
}


def country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def get_display_info(cc, cn, region="", city=""):
    """Return (flag, display_code, display_name) with China/HK/MO/TW awareness."""
    cc = cc.upper()
    if cc in REGION_DISPLAY:
        flag, code, name = REGION_DISPLAY[cc]
        # For CN, append region/city for more detail
        if cc == "CN" and (region or city):
            detail = region or city
            name = f"中国大陆 · {detail}"
        return flag, code, name
    return country_flag(cc), cc, cn


# --- IP providers --- each returns (ip, cc, cn, region, city)
def _fetch_ipinfo():
    r = requests.get("https://ipinfo.io/json", timeout=5)
    r.raise_for_status()
    d = r.json()
    return (d.get("ip", "?"), d.get("country", ""),
            d.get("country", ""), d.get("region", ""), d.get("city", ""))


def _fetch_ipapi():
    r = requests.get("http://ip-api.com/json/?fields=query,countryCode,country,regionName,city",
                     timeout=5)
    r.raise_for_status()
    d = r.json()
    return (d.get("query", "?"), d.get("countryCode", ""),
            d.get("country", ""), d.get("regionName", ""), d.get("city", ""))


def _fetch_ifconfig():
    r = requests.get("https://ifconfig.co/json", timeout=5)
    r.raise_for_status()
    d = r.json()
    return (d.get("ip", "?"), d.get("country_iso", ""),
            d.get("country", ""), d.get("region_name", ""), d.get("city", ""))


def _fetch_myip():
    r = requests.get("https://api.myip.com", timeout=5)
    r.raise_for_status()
    d = r.json()
    return (d.get("ip", "?"), d.get("cc", ""),
            d.get("country", ""), "", "")


PROVIDERS = [
    ("ipinfo.io", _fetch_ipinfo),
    ("ip-api.com", _fetch_ipapi),
    ("ifconfig.co", _fetch_ifconfig),
    ("api.myip.com", _fetch_myip),
]


def fetch_ip_location():
    """Returns (ip, cc, cn, region, city, provider)."""
    errors = []
    for name, fn in PROVIDERS:
        try:
            ip, cc, cn, region, city = fn()
            if cc:
                return ip, cc, cn, region, city, name
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError("All providers failed:\n" + "\n".join(errors))


# --- Network speed monitor ---
def get_network_bytes():
    """Get total bytes in/out via netstat on macOS."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ib"], text=True, timeout=3
        )
        total_in = 0
        total_out = 0
        lines = out.strip().split("\n")
        header = lines[0].split()
        # Find column indices for Ibytes and Obytes
        ibytes_idx = None
        obytes_idx = None
        for i, h in enumerate(header):
            if h == "Ibytes":
                ibytes_idx = i
            elif h == "Obytes":
                obytes_idx = i
        if ibytes_idx is None or obytes_idx is None:
            return 0, 0
        for line in lines[1:]:
            parts = line.split()
            if len(parts) <= max(ibytes_idx, obytes_idx):
                continue
            name = parts[0]
            if name.startswith("lo"):
                continue
            try:
                total_in += int(parts[ibytes_idx])
                total_out += int(parts[obytes_idx])
            except (ValueError, IndexError):
                continue
        return total_in, total_out
    except Exception:
        return 0, 0


def format_speed(bytes_per_sec: float) -> str:
    """Format bytes/sec into human readable string."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    elif bytes_per_sec < 1024 * 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"interval_seconds": 30}


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def notify(title, message):
    """Send macOS notification via osascript (more reliable than rumps.notification)."""
    try:
        # Escape double quotes for AppleScript
        t = title.replace('"', '\\"')
        m = message.replace('"', '\\"')
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{m}" with title "{t}" sound name "Glass"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# --- Circular Bubble with Flag-filled Background ---
class CircleBubbleView(NSView):
    """Circular clipped view with drag support. Children are clipped to circle."""

    def initWithFrame_(self, frame):
        self = objc.super(CircleBubbleView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._drag_origin = None
        # Enable layer for circular mask
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(frame.size.width / 2.0)
        self.layer().setMasksToBounds_(True)
        return self

    def drawRect_(self, rect):
        # Morandi gradient base (visible behind/around flag)
        color_top = NSColor.colorWithCalibratedRed_green_blue_alpha_(*MORANDI_TOP)
        color_bottom = NSColor.colorWithCalibratedRed_green_blue_alpha_(*MORANDI_BOTTOM)
        gradient = NSGradient.alloc().initWithStartingColor_endingColor_(color_top, color_bottom)
        gradient.drawInRect_angle_(rect, 270)

    def acceptsFirstMouse_(self, event):
        return True

    def mouseDown_(self, event):
        self._drag_origin = event.locationInWindow()

    def mouseDragged_(self, event):
        if self._drag_origin is None:
            return
        win = self.window()
        screen_loc = event.locationInWindow()
        origin = win.frame().origin
        new_x = origin.x + (screen_loc.x - self._drag_origin.x)
        new_y = origin.y + (screen_loc.y - self._drag_origin.y)
        win.setFrameOrigin_((new_x, new_y))


def _make_label(frame, text, size, color=None, weight=None, alpha=1.0):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    if weight:
        label.setFont_(NSFont.systemFontOfSize_weight_(size, weight))
    else:
        label.setFont_(NSFont.systemFontOfSize_(size))
    label.setAlignment_(NSTextAlignmentCenter)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setTextColor_(color or NSColor.whiteColor())
    if alpha < 1.0:
        label.setAlphaValue_(alpha)
    return label


def create_bubble_window():
    """Compact circle bubble: flag emoji fills background, info overlaid."""
    screen = NSScreen.mainScreen().frame()
    size = 76
    x = screen.size.width - size - 20
    y = screen.size.height - size - 60
    frame = NSMakeRect(x, y, size, size)

    style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskUtilityWindow
    window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, style, NSBackingStoreBuffered, False,
    )
    window.setFloatingPanel_(True)
    window.setWorksWhenModal_(True)
    window.setLevel_(NSStatusWindowLevel)  # higher than floating, stays above everything
    window.setOpaque_(False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setHasShadow_(True)
    window.setMovableByWindowBackground_(True)
    window.setIgnoresMouseEvents_(False)
    window.setHidesOnDeactivate_(False)  # don't hide when app loses focus
    # NSWindowCollectionBehaviorCanJoinAllSpaces (1)
    # | NSWindowCollectionBehaviorFullScreenAuxiliary (256)
    # | NSWindowCollectionBehaviorIgnoresCycle (64) - don't appear in Cmd+Tab / Mission Control
    window.setCollectionBehavior_(1 | 64 | 256)

    content = CircleBubbleView.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    window.setContentView_(content)

    # Giant flag emoji filling the circle (oversized so it crops to flag detail)
    # Offset to center the flag portion within the circular clip
    flag_size = 150
    flag_offset = (size - flag_size) / 2
    flag_label = _make_label(
        NSMakeRect(flag_offset, flag_offset, flag_size, flag_size),
        "🌐", 120,
    )
    content.addSubview_(flag_label)

    # Dark overlay for text readability (semi-transparent)
    from AppKit import NSBoxCustom, NSBox
    overlay = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    overlay.setBoxType_(NSBoxCustom)
    overlay.setFillColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.0, 0.0, 0.35))
    overlay.setBorderWidth_(0)
    overlay.setTitlePosition_(0)  # NSNoTitle
    content.addSubview_(overlay)

    # Country code - upper half
    shadow_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.0, 0.0, 0.6)
    from AppKit import NSShadow
    text_shadow = NSShadow.alloc().init()
    text_shadow.setShadowOffset_((0, -1))
    text_shadow.setShadowBlurRadius_(3.0)
    text_shadow.setShadowColor_(shadow_color)

    cc_label = _make_label(
        NSMakeRect(0, 38, size, 26), "--", 18,
        NSColor.whiteColor(), NSFontWeightSemibold,
    )
    cc_label.setShadow_(text_shadow)
    content.addSubview_(cc_label)

    # Speed labels - lower half
    speed_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.95, 0.95, 0.95, 0.95)

    up_label = _make_label(
        NSMakeRect(0, 18, size, 16), "↑ --", 10, speed_color, NSFontWeightMedium,
    )
    up_label.setShadow_(text_shadow)
    content.addSubview_(up_label)

    down_label = _make_label(
        NSMakeRect(0, 6, size, 16), "↓ --", 10, speed_color, NSFontWeightMedium,
    )
    down_label.setShadow_(text_shadow)
    content.addSubview_(down_label)

    window.orderFrontRegardless()

    return window, flag_label, cc_label, up_label, down_label


# --- Main App ---
class IPLocationApp(rumps.App):
    def __init__(self):
        super().__init__("🌐", quit_button=None)

        self.current_ip = ""
        self.current_country_code = ""
        self.current_country_name = ""
        self.current_provider = ""
        self.error_notified = False
        self.bubble_visible = True

        # Network speed state
        self._last_bytes_in = 0
        self._last_bytes_out = 0
        self._last_speed_time = 0
        self._up_speed = 0.0
        self._down_speed = 0.0

        config = load_config()
        self.interval = config.get("interval_seconds", 30)

        # Create bubble
        (self.bubble_window, self.bubble_flag, self.bubble_cc,
         self.bubble_up, self.bubble_down) = create_bubble_window()

        # Menu items
        self.ip_item = rumps.MenuItem("IP: fetching...")
        self.country_item = rumps.MenuItem("Country: fetching...")
        self.provider_item = rumps.MenuItem("Provider: -")
        self.speed_item = rumps.MenuItem("Speed: --")
        self.interval_item = rumps.MenuItem(f"Interval: {self.interval}s")
        self.bubble_toggle = rumps.MenuItem("Hide Bubble", callback=self.toggle_bubble)
        autostart_title = "✓ Launch at Login" if is_autostart_enabled() else "Launch at Login"
        self.autostart_item = rumps.MenuItem(autostart_title, callback=self.toggle_autostart)

        self.menu = [
            self.ip_item,
            self.country_item,
            self.provider_item,
            self.speed_item,
            None,
            self.interval_item,
            rumps.MenuItem("Set Interval...", callback=self.set_interval),
            rumps.MenuItem("Refresh Now", callback=self.refresh_now),
            None,
            self.bubble_toggle,
            self.autostart_item,
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Init network baseline
        self._last_bytes_in, self._last_bytes_out = get_network_bytes()
        self._last_speed_time = time.time()

        self._start_timer()
        self._start_speed_timer()

    def _start_timer(self):
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _start_speed_timer(self):
        """Update network speed every 2 seconds."""
        self._speed_stop = threading.Event()
        self._speed_thread = threading.Thread(target=self._speed_loop, daemon=True)
        self._speed_thread.start()

    def _speed_loop(self):
        while not self._speed_stop.is_set():
            self._speed_stop.wait(2)
            if self._speed_stop.is_set():
                break
            self._update_speed()

    def _update_speed(self):
        now = time.time()
        bytes_in, bytes_out = get_network_bytes()
        dt = now - self._last_speed_time
        if dt > 0 and self._last_bytes_in > 0:
            self._down_speed = max(0, (bytes_in - self._last_bytes_in) / dt)
            self._up_speed = max(0, (bytes_out - self._last_bytes_out) / dt)
        self._last_bytes_in = bytes_in
        self._last_bytes_out = bytes_out
        self._last_speed_time = now

        up_str = format_speed(self._up_speed)
        down_str = format_speed(self._down_speed)

        def _apply():
            self.bubble_up.setStringValue_(f"↑ {up_str}")
            self.bubble_down.setStringValue_(f"↓ {down_str}")
            self.speed_item.title = f"Speed: ↑ {up_str}  ↓ {down_str}"

        run_on_main_thread(_apply)

    def _poll_loop(self):
        while not self._stop_event.is_set():
            self._update()
            self._stop_event.wait(self.interval)

    def _update(self):
        try:
            ip, cc, cn, region, city, provider = fetch_ip_location()
            old_cc = self.current_country_code

            self.current_ip = ip
            self.current_country_code = cc
            self.current_country_name = cn
            self.current_provider = provider

            flag, display_code, display_name = get_display_info(cc, cn, region, city)

            def _apply():
                self.title = f"{flag} {display_code}"
                self.ip_item.title = f"IP: {ip}"
                self.country_item.title = f"Country: {display_name} ({display_code})"
                self.provider_item.title = f"Provider: {provider}"
                self.bubble_flag.setStringValue_(flag)
                self.bubble_cc.setStringValue_(display_code)

            run_on_main_thread(_apply)

            if old_cc and old_cc != cc:
                old_flag, old_code, old_name = get_display_info(old_cc, old_cc)
                notify(
                    "IP Location Changed",
                    f"{old_flag} {old_name} → {flag} {display_name}\nIP: {ip}",
                )

            self.error_notified = False

        except Exception as e:
            err_msg = str(e)

            def _apply_err():
                self.title = "⚠️"
                self.ip_item.title = "IP: error"
                self.country_item.title = "Country: error"
                self.provider_item.title = f"Error: {err_msg}"
                self.bubble_flag.setStringValue_("⚠️")
                self.bubble_cc.setStringValue_("ERR")

            run_on_main_thread(_apply_err)

            if not self.error_notified:
                notify("IP Location Error", f"All providers failed\n{e}")
                self.error_notified = True

    def toggle_bubble(self, sender):
        if self.bubble_visible:
            self.bubble_window.orderOut_(None)
            sender.title = "Show Bubble"
        else:
            self.bubble_window.orderFrontRegardless()
            sender.title = "Hide Bubble"
        self.bubble_visible = not self.bubble_visible

    def refresh_now(self, _):
        threading.Thread(target=self._update, daemon=True).start()

    def set_interval(self, _):
        window = rumps.Window(
            message="Enter refresh interval in seconds:",
            title="Set Interval",
            default_text=str(self.interval),
            dimensions=(200, 24),
        )
        response = window.run()
        if response.clicked:
            try:
                val = int(response.text.strip())
                if val < 5:
                    val = 5
                self.interval = val
                self.interval_item.title = f"Interval: {self.interval}s"
                config = load_config()
                config["interval_seconds"] = val
                save_config(config)
                self._stop_event.set()
                self._start_timer()
            except ValueError:
                rumps.alert("Invalid input", "Please enter a number.")

    def toggle_autostart(self, sender):
        if is_autostart_enabled():
            disable_autostart()
            sender.title = "Launch at Login"
            notify("IP Location", "Disabled launch at login")
        else:
            enable_autostart()
            sender.title = "✓ Launch at Login"
            notify("IP Location", "Enabled launch at login")

    def quit_app(self, _):
        self._stop_event.set()
        self._speed_stop.set()
        self.bubble_window.orderOut_(None)
        rumps.quit_application()


# --- Launch Agent (auto-start) management ---
PLIST_LABEL = "com.chiyou.ip-location"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "bin", "python3")
SCRIPT_PATH = os.path.abspath(__file__)

PLIST_TEMPLATE = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{VENV_PYTHON}</string>
        <string>{SCRIPT_PATH}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ip-location.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ip-location.err</string>
</dict>
</plist>
"""


def is_autostart_enabled():
    return os.path.exists(PLIST_PATH)


def enable_autostart():
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    with open(PLIST_PATH, "w") as f:
        f.write(PLIST_TEMPLATE)
    subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True)


def disable_autostart():
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
        os.unlink(PLIST_PATH)


LOCK_PATH = os.path.join(SCRIPT_DIR, ".ip_location.lock")
_lock_file = None


def ensure_single_instance():
    """Use file lock to ensure only one instance is running.
    If another instance exists, kill it first then take over."""
    global _lock_file

    # Check if lock file exists and has a PID
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH) as f:
                old_pid = int(f.read().strip())
            # Try to kill the old process
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(0.5)
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    _lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another instance is already running. Exiting.")
        sys.exit(1)

    _lock_file.write(str(os.getpid()))
    _lock_file.flush()


def cleanup_lock():
    global _lock_file
    if _lock_file:
        try:
            fcntl.flock(_lock_file, fcntl.LOCK_UN)
            _lock_file.close()
            os.unlink(LOCK_PATH)
        except Exception:
            pass


if __name__ == "__main__":
    ensure_single_instance()
    import atexit
    atexit.register(cleanup_lock)
    IPLocationApp().run()
