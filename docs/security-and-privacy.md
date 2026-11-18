# Security and privacy

| Question | Answer |
|---|---|
| Does any data leave my computer? | No. Analysis runs locally in the app, Python or MATLAB. There is no account, telemetry, cloud service or automatic update. |
| What files does the app read? | Its own runtime and demo data, and only the files you choose in file dialogs. It writes only where you save. |
| Does the app use the network? | No. It contains no web server, browser component or network code. The app's self-test records any attempt to open a network connection or browser and requires none. |
| How is each download built? | By GitHub Actions on its own operating system, from the tagged source. Each ZIP contains `build-manifest.json` with the source commit, Python, Tcl/Tk and library versions and the self-test results, and is published with a SHA-256 checksum. |
| Is it signed? | Not yet; see the [app guide](app-guide.md) for first launch. Institutional IT can review the source and build manifest. |

The interface code is in `multiplex_nbs/native_*.py`; the statistics in `core.py`; data
loading and exports in `io.py`; the packaged entry point in `packaging/native_entry.py`.
Bundled third-party licences are in each ZIP's `Third-party licenses` folder.
