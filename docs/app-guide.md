# Desktop app guide

The Multiplex-NBS app runs classic, layer-wise and multiplex network-based statistics
without any programming. Everything runs on your computer; nothing is uploaded.

## Install

| Computer | Download | Requires |
|---|---|---|
| Mac with Apple silicon (M1 or later) | `Multiplex-NBS-0.1.0-macOS-arm64.zip` | macOS 14 or later |
| Mac with an Intel processor | `Multiplex-NBS-0.1.0-macOS-x86_64.zip` | macOS 11 or later |
| Windows PC (64-bit) | `Multiplex-NBS-0.1.0-Windows-x86_64.zip` | Windows 10 or 11 |

Not sure which Mac you have? Choose **Apple menu → About This Mac** and look at
**Chip** or **Processor**.

### Mac: install from Terminal

The app is not yet signed by Apple, so macOS blocks it when it is downloaded with a web
browser, and recent versions of macOS may keep blocking it after **Open Anyway**. Install it
from **Terminal** instead (Applications → Utilities → Terminal): paste the command for your
Mac and press Return. It downloads the app, moves it to Applications, removes the download
and opens the app. Afterwards, open it from Applications or Launchpad like any other app.

Mac with Apple silicon (M1 or later):

```bash
cd ~/Downloads && \
curl -LO https://github.com/Minarose/multiplex-nbs/releases/download/v0.1.0/Multiplex-NBS-0.1.0-macOS-arm64.zip && \
ditto -x -k Multiplex-NBS-0.1.0-macOS-arm64.zip Multiplex-NBS && \
mv Multiplex-NBS/MultiplexNBS.app /Applications/ && \
rm -rf Multiplex-NBS Multiplex-NBS-0.1.0-macOS-arm64.zip && \
open /Applications/MultiplexNBS.app
```

Mac with an Intel processor:

```bash
cd ~/Downloads && \
curl -LO https://github.com/Minarose/multiplex-nbs/releases/download/v0.1.0/Multiplex-NBS-0.1.0-macOS-x86_64.zip && \
ditto -x -k Multiplex-NBS-0.1.0-macOS-x86_64.zip Multiplex-NBS && \
mv Multiplex-NBS/MultiplexNBS.app /Applications/ && \
rm -rf Multiplex-NBS Multiplex-NBS-0.1.0-macOS-x86_64.zip && \
open /Applications/MultiplexNBS.app
```

If MultiplexNBS is already in Applications, move the old copy to the Bin first.

### Windows

Download `Multiplex-NBS-0.1.0-Windows-x86_64.zip` from the
[release page](https://github.com/Minarose/multiplex-nbs/releases/tag/v0.1.0) and extract
the whole ZIP. Open `MultiplexNBS\MultiplexNBS.exe` and keep the `_internal` folder next to
it. If *Windows protected your PC* appears, choose **More info → Run anyway**.

### In a browser

[minarose.github.io/multiplex-nbs](https://minarose.github.io/multiplex-nbs/) runs the same
analysis code in a web browser, with nothing to install; files are read by the browser and
never uploaded. It suits trying the app and small to moderate datasets. A browser tab has
limited memory and uses one processor core, so large studies (many participants, regions or
layers, or many thousands of permutations) may run slowly or not load; use the desktop app
or the Python package for those.

Follow your institution's software policy. To check that a downloaded ZIP is intact,
compare its SHA-256 checksum with the `.sha256` file on the release page
(`shasum -a 256 -c <file>.sha256` on macOS, `Get-FileHash <file>` on Windows).

## Using the app

1. **Overview.** The figure shows the three methods on one network measured at four
   time points or frequencies. Choose **Try the demo** or **Start analysis**.
2. **Data.** Choose **Open my data** (one combined `.npz`/`.mat` file, or one ZIP of
   participant files per group; see [Data format](data-format.md)) or
   **Try a demo dataset**. After loading, check the summary, and add group labels, a
   design matrix, the layer axis or brain coordinates if needed. **Save dataset**
   writes everything to one `.npz` that opens directly next time.
3. **Statistical model.** Multiplex-NBS is selected for layered data; you can choose
   Layer-wise or Classic NBS instead. Set the study design, primary threshold, tail,
   component measure and number of permutations (9,999 by default; use at least 5000
   for results you report). Choose these before looking at results.
4. **Results.** The table lists components; click one to see it in the figures:
   - **Layer profile:** the distribution of suprathreshold edges and participating
     regions across layers, highlighting those belonging to the selected component.
     Point at a bar for exact values.
   - **Node × layer:** which regions belong to the component in which layers.
   - **Brain:** the component on a glass brain (left, right, axial and coronal views, or
     one large view), with playback through the layers. Needs MNI coordinates.
   - **All layers:** every layer the component spans; click one to open it in Brain.
   - **Null distribution:** how the extent or mass of the selected component compares
     with the maximum component statistic obtained in each permutation, with the
     critical value and a sentence explaining the corrected p-value.
5. **Save results.** Report (`.txt`), component table (`.csv`), full results (`.json`),
   MATLAB results (`.mat`) and the current figure (`.svg`). Results live only in the
   open app, so save what you need before closing it.

Light, Dark and Mono (black and white) modes are at the bottom of the sidebar.

## Troubleshooting

| Problem | What to do |
|---|---|
| The Brain tab shows a circle instead of a brain | Add coordinates (regions × 3, MNI mm) with **Node coordinates…** on the Data page. |
| "Matrices must be symmetric" | The app tests undirected networks; symmetrise directed matrices first, e.g. (A + Aᵀ)/2, if that suits your measure. |
| A `.mat` file will not open | Save it with `save(file, ..., '-v7')`; MATLAB `-v7.3` files are not supported. |
| Running is slow | Time grows with permutations × layers × regions². Try 999 permutations to explore, then the final number once. |

Report other problems on the [issue tracker](https://github.com/Minarose/multiplex-nbs/issues).
