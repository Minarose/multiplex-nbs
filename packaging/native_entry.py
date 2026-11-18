"""Standalone Tk application entry point."""
import json
from pathlib import Path
import sys
import traceback


def self_test(output, trace):
    import faulthandler
    from tkinter import messagebox

    events = []

    def observe(event, args):
        if event in {"socket.bind", "socket.connect", "socket.getaddrinfo", "webbrowser.open"}:
            events.append(event)

    sys.addaudithook(observe)
    def progress(message):
        print(message, file=trace, flush=True)

    def fail_dialog(dialog):
        raise RuntimeError(f"Unexpected GUI dialog during self-test: {dialog.options}")

    messagebox.Message.show = fail_dialog
    faulthandler.dump_traceback_later(45, repeat=True, file=trace)
    try:
        progress("Loading the native application")
        from multiplex_nbs.native_app import native_self_test

        report = native_self_test(progress=progress)
        report["network_or_browser_events"] = events
        if events or not report.get("ok") or report.get("web_modules_loaded") is not False:
            raise RuntimeError(f"Native application self-test failed: {report}")
    except Exception:
        output.write_text(json.dumps({"ok": False, "error": traceback.format_exc()}, indent=2), encoding="utf-8")
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        output = Path(sys.argv[2])
        with output.with_suffix(".trace.txt").open("w", encoding="utf-8") as trace:
            sys.exit(self_test(output, trace))
    from multiplex_nbs.native_app import main

    main()
