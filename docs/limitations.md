# Limitations and assumptions

- **Inference is at component level.** A significant component does not make any
  single edge, region or layer significant, and its first and last layers are not
  corrected estimates of effect onset or offset (Sassenhagen & Draschkow, 2019).
- **Exchangeability.** Unrestricted label permutation requires observations to be
  exchangeable under the null hypothesis (within any exchange blocks). One-sample sign
  flips assume each map is symmetric about zero under the null.
- **Paired designs.** Paired comparisons require permutations that preserve subject
  pairing, such as within-subject condition swaps or sign-flipping paired differences.
- **GLMs with covariates.** Freedman–Lane permutation accommodates nuisance regressors
  by permuting residuals from a reduced GLM. Validity depends on the error structure
  and exchangeability assumptions.
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
