# Changes from the supplied MATLAB implementation

The six `legacy/*.m` files are byte-for-byte copies of the supplied utility sources, including original attribution. They are retained for provenance, not included on the runtime path. The working script containing participant covariates and local paths is deliberately excluded from this repository.

Maintained top-level utilities and the validated wrapper change the following behavior:

- Accept one-frequency connectivity matrices (MATLAB omits trailing singleton dimensions).
- Correct mirrored p-value maps: the previous lower triangle included an additional 1.
- Provide two-sided clustering as separate positive and negative components with one shared maximum across both signs.
- Add paired condition swaps, seeded independent-label shuffles, and optional within-block independent shuffles.
- Reject contrasts/group labels that cannot vary under their permitted within-block shuffles.
- Make serial operation the default. GLM `auto` now consistently resolves to Freedman–Lane.
- Reject a nonzero effect with zero standard error/residual variance, in observed and permuted data; retain zero statistics for constant zero-effect data. This avoids silently turning deterministic effects into zeros.
- Validate complete finite symmetric data, full-rank designs, independent nonzero contrast rows, positive residual degrees of freedom, F/right-tail compatibility, permutation count, and contiguous selected bins through `mnbs_analyze`.
- Replace Statistics Toolbox CDF calls with base-MATLAB incomplete-beta functions. Replace summary percentile calls with the same midpoint-rank interpolation convention.
- Compute GLM contrast covariance from `C*pinv(X)` instead of `pinv(X'*X)`, avoiding squared conditioning. Observed/null exact-fit handling uses matching tolerances; arbitrary nonfinite statistics are rejected instead of zeroed.
- Preserve the caller's random stream and record options, contrast/design, null distribution, corrected p-values, and resolved permutation method.
- Add serial progress callbacks, GUI cancellation, and result invalidation when controls or datasets change.

These are deliberate extensions and correctness fixes. Identical seeds in MATLAB and Python do not imply identical permutation samples, since their random generators differ. Synthetic examples in the two languages also use different generators. Cross-language numerical agreement must be assessed on shared data and fixed permutations/observed statistics, not by comparing seeded demo p-values.

Validation status: MATLAB and Octave were unavailable on the development host. Native syntax was reviewed statically; `mnbs_selftest` is supplied but has not been executed there. GUI rendering, MATLAB numerical outputs, and any parallel execution must be verified in MATLAB before a research release.
