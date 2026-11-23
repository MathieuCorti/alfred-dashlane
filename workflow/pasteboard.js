#!/usr/bin/osascript -l JavaScript
// Clipboard helper.
//   copy <concealed:0|1>        Copy stdin to the clipboard, print the change count.
//   clear <changeCount> <delay>  After <delay> seconds, clear the clipboard if it
//                                still holds what we copied (change count unchanged).
// Secrets are read from stdin so they never appear in a process argument list.

ObjC.import("AppKit")
ObjC.import("Foundation")

function readStdin() {
  const data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile
  return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding)
}

function run(argv) {
  const pasteboard = $.NSPasteboard.generalPasteboard
  const mode = argv[0]

  if (mode === "copy") {
    const text = readStdin()
    pasteboard.clearContents
    if (argv[1] === "1") {
      // nspasteboard.org markers: clipboard managers (Alfred included) skip these.
      pasteboard.setStringForType("", "org.nspasteboard.ConcealedType")
      pasteboard.setStringForType("", "org.nspasteboard.TransientType")
    }
    pasteboard.setStringForType(text, "public.utf8-plain-text")
    return String(pasteboard.changeCount)
  }

  if (mode === "clear") {
    delay(Number(argv[2]))
    if (String(pasteboard.changeCount) === argv[1]) pasteboard.clearContents
    return ""
  }

  throw new Error(`Unknown mode: ${mode}`)
}
