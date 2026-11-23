#!/usr/bin/osascript -l JavaScript
// Clipboard helper. Text always comes from stdin so secrets never appear in a
// process argument list.
//
//   copy <secret:0|1>            Copy stdin to the clipboard, print the change count.
//   clear <changeCount> <delay>  After <delay> seconds, clear the clipboard if it
//                                still holds what we copied (change count unchanged).
//   paste <secret:0|1>           Save the clipboard, put stdin on it, press ⌘V in the
//                                frontmost app, then restore the previous clipboard.

ObjC.import("AppKit")
ObjC.import("Foundation")

const CURRENT_HOST_ONLY = 1 // NSPasteboardContentsCurrentHostOnly: no Universal Clipboard
const pasteboard = $.NSPasteboard.generalPasteboard

function readStdin() {
  const data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile
  return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding)
}

function write(text, secret) {
  if (secret) {
    pasteboard.prepareForNewContentsWithOptions(CURRENT_HOST_ONLY)
    // nspasteboard.org markers: clipboard managers (Alfred included) skip these.
    pasteboard.setStringForType("", "org.nspasteboard.ConcealedType")
    pasteboard.setStringForType("", "org.nspasteboard.TransientType")
  } else {
    pasteboard.clearContents
  }
  pasteboard.setStringForType(text, "public.utf8-plain-text")
  return pasteboard.changeCount
}

function snapshot() {
  const saved = []
  const items = pasteboard.pasteboardItems
  for (let i = 0; i < items.count; i++) {
    const item = items.objectAtIndex(i)
    const types = item.types
    const entries = []
    for (let j = 0; j < types.count; j++) {
      const type = types.objectAtIndex(j)
      const data = item.dataForType(type)
      if (data && !data.isNil()) entries.push([type, data])
    }
    if (entries.length) saved.push(entries)
  }
  return saved
}

function restore(saved) {
  pasteboard.clearContents
  if (!saved.length) return
  const objects = $.NSMutableArray.array
  for (const entries of saved) {
    const item = $.NSPasteboardItem.alloc.init
    for (const [type, data] of entries) item.setDataForType(data, type)
    objects.addObject(item)
  }
  pasteboard.writeObjects(objects)
}

function run(argv) {
  const mode = argv[0]

  if (mode === "copy") {
    return String(write(readStdin(), argv[1] === "1"))
  }

  if (mode === "clear") {
    delay(Number(argv[2]))
    if (String(pasteboard.changeCount) === argv[1]) pasteboard.clearContents
    return ""
  }

  if (mode === "paste") {
    const text = readStdin()
    const saved = snapshot()
    const ours = write(text, argv[1] === "1")
    // Let Alfred's window close and focus return to the previous app.
    delay(0.25)
    try {
      Application("System Events").keystroke("v", { using: "command down" })
    } catch (error) {
      restore(saved)
      throw error
    }
    // Give the app time to read the clipboard, then put the user's content back,
    // unless something else was copied meanwhile.
    delay(1)
    if (pasteboard.changeCount === ours) restore(saved)
    return ""
  }

  throw new Error(`Unknown mode: ${mode}`)
}
