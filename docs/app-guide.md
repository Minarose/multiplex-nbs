# Desktop app guide

The Multiplex-NBS app runs classic, layer-wise and multiplex network-based statistics
without any programming. Everything runs on your computer; nothing is uploaded.

## Download

Download the ZIP for your computer from the
[latest release](https://github.com/Minarose/multiplex-nbs/releases/latest):

| Computer | File | Requires |
|---|---|---|
| Mac with Apple silicon (M1 or later) | `Multiplex-NBS-<version>-macOS-arm64.zip` | macOS 14 or later |
| Mac with an Intel processor | `Multiplex-NBS-<version>-macOS-x86_64.zip` | macOS 11 or later |
| Windows PC (64-bit) | `Multiplex-NBS-<version>-Windows-x86_64.zip` | Windows 10 or 11 |

Not sure which Mac you have? Choose **Apple menu → About This Mac** and look at
**Chip** or **Processor**. The exact minimum macOS version of each download is in its
`START-HERE.txt`.

Extract the whole ZIP. On a Mac, open `MultiplexNBS.app`. On Windows, open
`MultiplexNBS\MultiplexNBS.exe` and keep the `_internal` folder next to it.

## Opening the app for the first time

The app is not yet signed by Apple or Microsoft, so the system asks you to confirm it
the first time:

- **macOS:** Control-click the app and choose **Open**, then **Open** again. Or open
  **System Settings → Privacy & Security** and choose **Open Anyway**
  (on older macOS: **System Preferences → Security & Privacy**).
- **Windows:** if *Windows protected your PC* appears, choose **More info → Run anyway**.

Follow your institution's software policy. To check that a download is intact, compare
its SHA-256 checksum with the `.sha256` file on the release page
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
   component measure and number of permutations (use at least 5000 for results you
   report). Choose these before looking at results.
4. **Results.** The table lists components; click one to see it in the figures:
   - **Layer profile:** how much of the network passes the threshold in each layer, and
     how much belongs to the component. Point at a bar for exact values.
   - **Node × layer:** which regions belong to the component in which layers.
   - **Brain:** the component on a glass brain (left, right, axial and coronal views, or
     one large view), with playback through the layers. Needs MNI coordinates.
   - **All layers:** every layer the component spans; click one to open it in Brain.
   - **Null distribution:** the observed size against the largest component in each
     permutation, with the critical value.
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
