#Requires AutoHotkey v2.0
Persistent

running := false
paused := false

F13:: {
    global running, paused
    if running
        return

    running := true
    paused := false

    centerX := A_ScreenWidth // 2
    centerY := A_ScreenHeight // 2

    MouseMove centerX, centerY

    ; Initial click in center
    Click

    Sleep 100

    ; Tap Shift (not held)
    Send "{Shift}"

    ; Hold left click
    Click "down"

    while running {
        ; Pause handling
        while paused && running {
            Sleep 100
        }

        if !running
            break

        Sleep 3000
        if paused || !running
            continue

        Send ","
        Sleep 50
        Send ","
    }

    ; Release click when stopping
    Click "up"
}

F14:: {
    global paused, running
    if !running
        return

    paused := !paused
}

F15:: {
    global running, paused
    running := false
    paused := false
    Click "up"
}