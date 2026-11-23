#!/usr/bin/osascript -l JavaScript
// Types a login and password into the frontmost app.
// Reads {"login": "...", "password": "...", "submit": bool} from stdin.

ObjC.import("Foundation")

function readStdin() {
  const data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile
  return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js
}

function run() {
  const { login, password, submit } = JSON.parse(readStdin())
  const systemEvents = Application("System Events")

  // Let Alfred's window close and focus return to the previous app.
  delay(0.35)

  if (login) {
    systemEvents.keystroke(login)
    systemEvents.keyCode(48) // Tab
    delay(0.1)
  }
  systemEvents.keystroke(password)
  if (submit) systemEvents.keyCode(36) // Return
  return ""
}
