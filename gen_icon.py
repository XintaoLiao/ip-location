"""Generate app icon: globe bottom-left + pin touching it top-right, rotated 45deg CW."""
import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def gen_png(size, path):
    subprocess.run(["python3", "-c", f"""
import AppKit
import Cocoa
import math

size = {size}
img = AppKit.NSImage.alloc().initWithSize_((size, size))
img.lockFocus()

s = size

# --- Rounded rect clip + gradient bg ---
pad = s * 0.08
radius = s * 0.22
rect = Cocoa.NSMakeRect(pad, pad, s - pad*2, s - pad*2)
bg = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)
bg.addClip()

c1 = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.35, 0.52, 0.55, 1.0)
c2 = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.50, 0.40, 0.48, 1.0)
grad = AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(c1, c2)
grad.drawInRect_angle_(rect, 270)

# --- Apply 45-degree clockwise rotation around center ---
xf = AppKit.NSAffineTransform.transform()
xf.translateXBy_yBy_(s * 0.5, s * 0.5)
xf.rotateByDegrees_(-45)  # negative = clockwise
xf.translateXBy_yBy_(-s * 0.5, -s * 0.5)
xf.concat()

# --- Large globe at bottom ---
cx = s * 0.5
cy = s * -0.08
gr = s * 0.72

globe_rect = Cocoa.NSMakeRect(cx - gr, cy - gr, gr*2, gr*2)
globe_path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(globe_rect)

# Globe fill
AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.88, 0.92, 0.94, 0.2).setFill()
globe_path.fill()

# Globe outline
lw = s * 0.016
AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.85).setStroke()
globe_path.setLineWidth_(lw)
globe_path.stroke()

# --- Globe grid: latitude lines ---
AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.4).setStroke()
glw = s * 0.010

for lat in [-0.65, -0.33, 0.0, 0.33, 0.65]:
    y = cy + lat * gr
    half_w = math.sqrt(max(0, gr*gr - (lat*gr)**2))
    line = AppKit.NSBezierPath.bezierPath()
    line.setLineWidth_(glw)
    line.moveToPoint_((cx - half_w, y))
    curve_amt = lat * gr * 0.12
    line.curveToPoint_controlPoint1_controlPoint2_(
        (cx + half_w, y),
        (cx - half_w * 0.3, y + curve_amt),
        (cx + half_w * 0.3, y + curve_amt),
    )
    AppKit.NSGraphicsContext.currentContext().saveGraphicsState()
    globe_path.addClip()
    line.stroke()
    AppKit.NSGraphicsContext.currentContext().restoreGraphicsState()

# Longitude ellipses
for lon in [-0.5, -0.15, 0.15, 0.5]:
    ew = abs(gr * lon * 0.7)
    if ew < s * 0.01:
        ew = s * 0.01
    meridian_rect = Cocoa.NSMakeRect(cx - ew + lon * gr * 0.7, cy - gr, ew * 2, gr * 2)
    meridian = AppKit.NSBezierPath.bezierPathWithOvalInRect_(meridian_rect)
    meridian.setLineWidth_(glw)
    AppKit.NSGraphicsContext.currentContext().saveGraphicsState()
    globe_path.addClip()
    meridian.stroke()
    AppKit.NSGraphicsContext.currentContext().restoreGraphicsState()

# Center meridian
center_m = AppKit.NSBezierPath.bezierPath()
center_m.moveToPoint_((cx, cy - gr))
center_m.lineToPoint_((cx, cy + gr))
center_m.setLineWidth_(glw)
AppKit.NSGraphicsContext.currentContext().saveGraphicsState()
globe_path.addClip()
center_m.stroke()
AppKit.NSGraphicsContext.currentContext().restoreGraphicsState()

# --- Location pin: tip touches the globe top ---
pin_cx = s * 0.5
pin_r = s * 0.085
pin_h = s * 0.26

# Pin tip sits right on the globe edge
globe_top = cy + gr
pin_bottom = globe_top       # tip touches globe
pin_cy = pin_bottom + pin_h - pin_r  # center of pin head circle

# Shadow
shadow = AppKit.NSShadow.alloc().init()
shadow.setShadowOffset_((0, -s*0.008))
shadow.setShadowBlurRadius_(s * 0.035)
shadow.setShadowColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, 0.5))
shadow.set()

# Teardrop pin shape
pin = AppKit.NSBezierPath.bezierPath()
pin.moveToPoint_((pin_cx, pin_bottom))
pin.curveToPoint_controlPoint1_controlPoint2_(
    (pin_cx - pin_r * 1.05, pin_cy),
    (pin_cx - pin_r * 0.35, pin_bottom + pin_h * 0.18),
    (pin_cx - pin_r * 1.05, pin_cy - pin_r * 0.6),
)
pin.curveToPoint_controlPoint1_controlPoint2_(
    (pin_cx + pin_r * 1.05, pin_cy),
    (pin_cx - pin_r * 1.05, pin_cy + pin_r * 0.85),
    (pin_cx + pin_r * 1.05, pin_cy + pin_r * 0.85),
)
pin.curveToPoint_controlPoint1_controlPoint2_(
    (pin_cx, pin_bottom),
    (pin_cx + pin_r * 1.05, pin_cy - pin_r * 0.6),
    (pin_cx + pin_r * 0.35, pin_bottom + pin_h * 0.18),
)
pin.closePath()

AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.88, 0.35, 0.32, 1.0).setFill()
pin.fill()
AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.55, 0.50, 0.5).setStroke()
pin.setLineWidth_(s * 0.008)
pin.stroke()

# Inner white dot
dot_r = pin_r * 0.38
dot_rect = Cocoa.NSMakeRect(pin_cx - dot_r, pin_cy - dot_r, dot_r * 2, dot_r * 2)
dot = AppKit.NSBezierPath.bezierPathWithOvalInRect_(dot_rect)
AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.95).setFill()
dot.fill()

AppKit.NSShadow.alloc().init().set()

img.unlockFocus()

tiff = img.TIFFRepresentation()
bitmap = AppKit.NSBitmapImageRep.alloc().initWithData_(tiff)
png_data = bitmap.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {{}})
png_data.writeToFile_atomically_("{path}", True)
"""], capture_output=True, text=True)


def main():
    iconset = os.path.join(SCRIPT_DIR, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)

    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for name, sz in sizes.items():
        print(f"  Rendering {name} ({sz}px)...")
        gen_png(sz, os.path.join(iconset, name))

    icns_path = os.path.join(SCRIPT_DIR, "AppIcon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path])
    subprocess.run(["rm", "-rf", iconset])
    print(f"Created {icns_path}")


if __name__ == "__main__":
    main()
