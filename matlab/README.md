# Multiplex-NBS MATLAB toolbox

Needs base MATLAB R2021a or newer and no other toolbox (optional `useParallel=true`
uses the Parallel Computing Toolbox). From the repository folder:

```matlab
addpath('matlab')        % do not use genpath: legacy/ holds the original prototype
mnbs_selftest            % run once to check the installation
help Contents            % list the functions (or: doc mnbs_analyze)
mnbs_gui                 % optional interactive window
```

Every function has full help text (`help mnbs_analyze`), also collected in
[docs/matlab-api.md](../docs/matlab-api.md). Worked scripts are in
[examples/matlab](../examples/matlab).

## Quick example

```matlab
d = mnbs_load_demo('brain-network');           % same data as Python and the app
opts = struct('t0', 3, 'nPerm', 999, 'rngSeed', 1, ...
              'axisName', d.axisName, 'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
result = mnbs_analyze(d.W, d.group, opts);      % Multiplex-NBS
disp(result.significant)

opts.layerAdjacency = 'independent';            % Layer-wise NBS
result = mnbs_analyze(d.W, d.group, opts);

% GLM with a covariate (Freedman-Lane permutation by default)
g = mnbs_load_demo('glm');
result = mnbs_analyze(g.W, g.model, struct('nPerm', 999));
```

Classic NBS on a single network and one-sample tests are provided by the Python
package and the desktop app.


`W` is normally a cell array, with one N × N × F matrix per observation. Matrices must be real, finite, symmetric, and equally sized. Diagonals are ignored. Single-layer N × N matrices work. The API also accepts explicit S × N × N × F numeric arrays. Files imported through the GUI follow the shared MAT convention: numeric `W` is N × N × F × S; alternatively, a numeric variable named `connectivity` is S × N × N × F. Cell `W` is identical in the API and file formats.

MAT files contain `group` (numeric labels) or `model` (`X`, `C`, `statType`). Top-level `X`, `C`, `stat_type` are also accepted. Optional `exchange_blocks` or `exchangeBlocks` restrict row shuffles within each block. `axis_name`, `axis_unit`, and `axis_values` supply axis metadata; `frequencies` remains a legacy alias. The native GUI has editable axis-name, unit, and layer-adjacency controls and a dark theme. The GUI uses all bins in file order. The API's legacy `freqMask` must select increasing indices; consecutive adjacency additionally requires a contiguous selection. Independent layers may use an ordered noncontiguous subset.

## Options and interpretation

| Field | Default | Meaning |
|---|---|---|
| `t0` | 3 | Strict primary threshold: t > t0 or t < −t0 |
| `nPerm` | 9999 | Number of sampled permutations |
| `tail` | `right` | `right`, `left`, or `both`; F requires `right` |
| `clusterMetric` | `extent` | Number of node-layer sites, `mass` (summed edge statistics) or `intensity` (mass with the threshold subtracted from each edge, as in NBS) |
| `rngSeed` | 1 | Repeatable random sampling; caller RNG is restored |
| `test` | `two-sample` | Independent Welch or `paired` |
| `method` | `auto` | GLM: `auto`/`freedman-lane`, or explicit `rowshuffle` |
| `exchangeBlocks` | empty | Numeric row-permutation blocks for independent/GLM designs |
| `pairs` | empty | Optional nPairs × 2 observation indices for paired tests |
| `useAbs` | false | Apply absolute value before statistics |
| `alpha` | 0.05 | Cluster summary significance level |
| `useParallel` | false | Use parfor when licensed |
| `freqMask` | empty | Selected layer indices (contiguous for consecutive adjacency) |
| `axisName`, `axisUnit` | Layer, empty | Meaning of the third network dimension |
| `axisValues` | 1…L | Finite, strictly increasing numeric values |
| `layerAdjacency` | consecutive | Consecutive or independent layers; shared maximum correction in both |
| `progress` | empty | Serial progress callback `(completed,total)` |

Independent t statistics are lower numeric label minus higher label; a right-tailed test therefore selects positive differences in that direction. Paired tests use the first observation minus the second within each pair ID. GLM direction is determined by Cβ. Statistical validity depends on exchangeability or sign symmetry, not on the GUI selection. A Welch statistic does not make unrestricted label permutation exact under unequal variances. Freedman–Lane with nuisance covariates is generally an approximate permutation procedure. Blocks support within-block row shuffling; they are not a complete framework for every hierarchical design.

Extent counts active node-layer sites. Mass divides each suprathreshold edge statistic between its endpoints and sums the site contributions. Intensity is mass minus `t0` for each kept edge, the NBS toolbox definition; in the GUI, choose Mass and tick *Subtract the threshold from each edge*. Both tails keep positive and negative components separate and calibrate against one maximum across signs. Cluster p-values are `(1 + count(nullMax >= observed))/(nPerm + 1)`. A significant cluster does not establish significance of its individual edges, nodes, or layers. A zero-error nonzero effect is rejected rather than silently assigned a statistic of zero. Select the threshold and inferential metric before inspecting results.

## Utilities and checks

- `mnbs_edgestat_group`: Welch/paired edge statistics and mirrored maps.
- `mnbs_edgestat_glm`: GLM t/F statistics.
- `mnbs_components`: clusters a supplied edge × frequency statistic map.
- `mnbs_permute`, `mnbs_permute_glm`: permutation distributions.
- `mnbs_summarize`: corrected p-values and cluster tables.
- `golden_fixture.json`: fixed 8-observation input and expected observed Welch/GLM t/F statistics, with hand-specified two-tail cluster sites. Python has checked this fixture against independent formulas; MATLAB still needs execution.
- `mnbs_selftest`: golden-fixture, regressor-scaling, and regression checks for clustering, CDF, symmetry, deterministic permutations, t²=F, and input rejection.

Use `mnbs_analyze` as the validated public entry point. Low-level utilities retain much of the original API; they do not duplicate all wrapper validation. Run `mnbs_selftest` in MATLAB before using this release for research.

## Version 0.2 axis example

```matlab
opts.axisName = 'Time';
opts.axisUnit = 'ms';
opts.axisValues = 0:50:350; % Match the eight layers in this example.
opts.layerAdjacency = 'consecutive'; % Or 'independent' to disconnect slices.
result = mnbs_analyze(W, group, opts);
disp(result.axis)
```

Legacy frequency-named fields remain for compatibility; `result.axis` and `clusters.layerBins` provide neutral aliases. Native MATLAB axis/adjacency changes have regression checks but remain unexecuted in this environment. The published-template guided example is currently included in the downloadable Python app; the native MATLAB demo remains synthetic.

The **Original NBS** button opens the official NBS Connectome GUI when that toolbox is installed on the MATLAB path. Install it separately from the [authors’ NITRC project](https://www.nitrc.org/projects/nbs/). The downloadable Python application also supplies a classic single-layer component analysis.
