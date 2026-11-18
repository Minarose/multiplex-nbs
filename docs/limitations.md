# Limitations and assumptions

- **Inference is at component level.** A significant component does not make any
  single edge, region or layer significant, and its first and last layers are not
  corrected estimates of effect onset or offset (Sassenhagen & Draschkow, 2019).
- **Exchangeability.** Label and row shuffles assume observations are exchangeable
  under the null within any exchange blocks. Sign flips (paired, one-sample) assume
  differences are symmetric about zero.
- **GLMs with covariates.** Freedman–Lane permutation is approximate when nuisance
  regressors are present.
- **Thresholds.** Results depend on the primary threshold; choose it in advance. Low
  thresholds let components chain together, which reduces specificity.
- **One ordered axis.** Layers form one axis (time *or* frequency). A joint time ×
  frequency graph is not supported. Neighbouring layers are linked by array order, not
  by the numerical spacing of the axis values.
- **Undirected networks only.** Matrices must be symmetric.
- **Memory.** All region pairs are stored for every layer; memory grows with regions².
  The app limits single files to 512 MiB expanded; the Python API can raise this for
  trusted data.
- **MATLAB.** Classic NBS and one-sample tests are available in Python and the app, not
  in the MATLAB toolbox. MATLAB results have not yet been verified in automated tests.
- **Unsigned apps.** The desktop apps are not signed by Apple or Microsoft, so a first
  launch needs confirmation (see the [app guide](app-guide.md)).
