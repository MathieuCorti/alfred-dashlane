// Renders the workflow icons from SF Symbols.
// Usage: swift tools/make_icons.swift <workflow dir>
import AppKit

let workflowDir = URL(fileURLWithPath: CommandLine.arguments[1])
let iconsDir = workflowDir.appendingPathComponent("icons")
try FileManager.default.createDirectory(at: iconsDir, withIntermediateDirectories: true)

func hex(_ value: UInt32) -> NSColor {
    NSColor(
        srgbRed: CGFloat((value >> 16) & 0xFF) / 255,
        green: CGFloat((value >> 8) & 0xFF) / 255,
        blue: CGFloat(value & 0xFF) / 255,
        alpha: 1
    )
}

func symbol(_ name: String, pointSize: CGFloat, colors: [NSColor]) -> NSImage {
    let config = NSImage.SymbolConfiguration(pointSize: pointSize, weight: .semibold)
        .applying(NSImage.SymbolConfiguration(paletteColors: colors))
    guard let image = NSImage(systemSymbolName: name, accessibilityDescription: nil)?
        .withSymbolConfiguration(config) else {
        fatalError("Unknown SF Symbol: \(name)")
    }
    return image
}

func render(_ file: String, size: Int, draw: (NSRect) -> Void) {
    let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    )!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    draw(NSRect(x: 0, y: 0, width: size, height: size))
    NSGraphicsContext.restoreGraphicsState()
    let url = file == "icon" ? workflowDir.appendingPathComponent("icon.png") : iconsDir.appendingPathComponent("\(file).png")
    try! rep.representation(using: .png, properties: [:])!.write(to: url)
}

func drawCentered(_ image: NSImage, in rect: NSRect, offset: NSPoint = .zero) {
    let size = image.size
    image.draw(in: NSRect(
        x: rect.midX - size.width / 2 + offset.x,
        y: rect.midY - size.height / 2 + offset.y,
        width: size.width, height: size.height
    ))
}

// Workflow icon: white key on a deep teal rounded square.
render("icon", size: 512) { rect in
    let tile = rect.insetBy(dx: 24, dy: 24)
    let path = NSBezierPath(roundedRect: tile, xRadius: 104, yRadius: 104)
    NSGradient(starting: hex(0x1B9C8A), ending: hex(0x0B3B45))!.draw(in: path, angle: -90)
    drawCentered(symbol("key.horizontal.fill", pointSize: 230, colors: [.white]), in: tile)
}

// Result icons: a symbol on a soft tinted circle.
let resultIcons: [(String, String, UInt32)] = [
    ("credential", "key.fill", 0x14A38B),
    ("credential-otp", "key.fill", 0x14A38B),
    ("note", "note.text", 0xE0A100),
    ("sync", "arrow.triangle.2.circlepath", 0x2F7FE0),
    ("lock", "lock.fill", 0x7A6FE0),
    ("login", "person.badge.key.fill", 0x2F7FE0),
    ("warning", "exclamationmark.triangle.fill", 0xE8780C),
    ("search", "magnifyingglass", 0x8E8E93),
    ("field-login", "person.fill", 0x2F7FE0),
    ("field-url", "globe", 0x2F7FE0),
    ("field-type", "keyboard.fill", 0x8E8E93),
    ("field-card", "rectangle.stack.fill", 0x14A38B),
]

for (file, name, color) in resultIcons {
    render(file, size: 128) { rect in
        let circle = NSBezierPath(ovalIn: rect.insetBy(dx: 6, dy: 6))
        hex(color).withAlphaComponent(0.18).setFill()
        circle.fill()
        drawCentered(symbol(name, pointSize: 56, colors: [hex(color)]), in: rect)
        if file == "credential-otp" {
            // Small clock badge for items with a 2FA code.
            let badge = NSRect(x: rect.maxX - 52, y: rect.minY + 4, width: 48, height: 48)
            hex(color).setFill()
            NSBezierPath(ovalIn: badge).fill()
            drawCentered(symbol("clock.fill", pointSize: 24, colors: [.white]), in: badge)
        }
    }
}
print("Icons written to \(iconsDir.path)")
