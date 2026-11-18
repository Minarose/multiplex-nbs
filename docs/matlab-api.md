# MATLAB API

Generated from each function's help text by `tools/build_api_docs.py`; the same text is shown by `help <function>` in MATLAB. Add the toolbox with `addpath('multiplex-nbs/matlab')`. Needs base MATLAB R2021a or newer; no other toolbox.

- [`mnbs_analyze`](#mnbs_analyze)
- [`mnbs_load_demo`](#mnbs_load_demo)
- [`mnbs_gui`](#mnbs_gui)
- [`mnbs_demo`](#mnbs_demo)
- [`mnbs_edgestat_group`](#mnbs_edgestat_group)
- [`mnbs_edgestat_glm`](#mnbs_edgestat_glm)
- [`mnbs_components`](#mnbs_components)
- [`mnbs_permute`](#mnbs_permute)
- [`mnbs_permute_glm`](#mnbs_permute_glm)
- [`mnbs_summarize`](#mnbs_summarize)
- [`mnbs_selftest`](#mnbs_selftest)
- [`mnbs_tcdf`](#mnbs_tcdf)

## mnbs_analyze

```matlab
result = mnbs_analyze(W, design, opts)
```

```text
MNBS_ANALYZE Network-based statistic for a stack of networks (Multiplex-NBS).

  result = mnbs_analyze(W, group)
  result = mnbs_analyze(W, group, opts)
  result = mnbs_analyze(W, model, opts)

  Tests an effect at every edge in every layer, keeps the edges whose
  statistic exceeds a primary threshold, joins them into connected
  components of region-layer sites, and gives each component a family-wise
  corrected p-value from the permutation distribution of the largest
  component. Layers are successive time points, frequency bins or another
  ordered measurement of the same network.

  Inputs
    W      Connectivity. A cell array with one N-by-N-by-L matrix per
           observation (N regions, L layers), or a numeric S-by-N-by-N-by-L
           array (S observations). Matrices must be real, finite and
           symmetric, with the same regions in the same order throughout.
    group  Numeric vector with one entry per observation:
           - two group labels (default): Welch t, first sorted label minus
             the second; or
           - pair IDs, each appearing twice, with opts.test = 'paired': the
             first observation of each pair minus the second.
    model  A GLM instead of group: struct with fields
             .X         S-by-p design matrix (include an intercept column)
             .C         contrast, 1-by-p for a t test or k-by-p for an F test
             .statType  't' or 'F'
    opts   Optional struct with any of these fields (default in brackets):
             .t0             primary threshold                          [3]
             .tail           'right', 'left' or 'both'                  ['right']
             .clusterMetric  'extent' (region-layer sites) or 'mass'    ['extent']
             .layerAdjacency 'consecutive' = Multiplex-NBS              ['consecutive']
                             'independent' = Layer-wise NBS (components
                             stay in their layer; one correction for all)
             .nPerm          random permutations; use >= 5000 to report [1000]
             .rngSeed        random seed                                [1]
             .alpha          reporting cutoff for result.significant    [0.05]
             .test           'two-sample' or 'paired'                   ['two-sample']
             .pairs          nPairs-by-2 observation indices (paired)   []
             .method         GLM resampling: 'auto' (Freedman-Lane),
                             'freedman-lane' or 'rowshuffle'            ['auto']
             .exchangeBlocks S-by-1 labels; permute only within blocks  []
             .axisName, .axisUnit, .axisValues   label the layers,
                             e.g. 'Frequency', 'Hz', 4:2:18             ['Layer','',1:L]
             .freqMask       layers to analyse (logical or indices)     [all]
             .useAbs         use absolute connectivity values           [false]
             .useParallel    permutations in parfor (Parallel Toolbox)  [false]
             .progress       function handle, progress(done, total)     []
             .verbose        print a summary                            [false]

  Output
    result  struct with fields
      .clusters     one element per observed component, with .nodes
                    (regions), .layerBins (layers), .extent, .mass, .tail,
                    .p_FWE and .nodeFreqIdx (sites)
      .pvalues      corrected p-value of each component
      .significant  table of components with p_FWE <= opts.alpha (id,
                    nNodes, nFreqBins, freqMin, freqMax as layer indices,
                    extent, mass, testStat, p_FWE, nodeList)
      .report       summary (counts, null distribution percentiles)
      .nullMax      largest component in each permutation
      .stats        edge statistics (.Tef, edges-by-layers) and edge list
      .axis, .options, .design, .method, .version

  The corrected p-value applies to a component as a whole, not to any of
  its edges, regions or layers, and the first and last layers it spans are
  not corrected estimates of where an effect starts or stops. Classic NBS
  on a single network is available in the Python package (classic_nbs) and
  the desktop app; see docs/classic-nbs-parity.md.

  Example
    d = mnbs_load_demo('brain-network');
    opts = struct('t0', 3, 'nPerm', 999, 'axisName', d.axisName, ...
                  'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
    result = mnbs_analyze(d.W, d.group, opts);
    disp(result.significant)

  See also MNBS_LOAD_DEMO, MNBS_GUI, MNBS_EDGESTAT_GROUP, MNBS_EDGESTAT_GLM,
  MNBS_COMPONENTS, MNBS_PERMUTE, MNBS_PERMUTE_GLM, MNBS_SUMMARIZE.

  Reference: Zalesky A, Fornito A, Bullmore ET (2010). Network-based
  statistic: identifying differences in brain networks. NeuroImage 53:1197-1207.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_load_demo

```matlab
d = mnbs_load_demo(name)
```

```text
MNBS_LOAD_DEMO Load a bundled practice dataset (all observations simulated).

  d = mnbs_load_demo()
  d = mnbs_load_demo(name)

  The same datasets as the Python package (multiplex_nbs.load_demo) and the
  desktop app, so results agree across tools.

  Inputs
    name  'brain-network' (default): 32 regions of an open human structural
                connectome with MNI coordinates, 40 simulated participants in
                two groups, 8 time windows (0-350 ms); group 1 is higher
                along a left sensorimotor-parietal chain at 100-200 ms.
          'two-sample', 'paired', 'glm': 12 abstract regions, 8 frequency
                bins (4-18 Hz), one study design each.

  Output
    d  struct with .W (S-by-1 cell of N-by-N-by-L), .axisName, .axisUnit,
       .axisValues, .nodeLabels, .description, and the design: .group
       (labels or pair IDs) or .model (.X, .C, .statType). The brain
       example also has .nodeCoordinates (MNI mm) and .groupNames.

  Example
    d = mnbs_load_demo('glm');
    result = mnbs_analyze(d.W, d.model, struct('nPerm', 499));

  See also MNBS_ANALYZE, MNBS_DEMO.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_gui

```matlab
fig = mnbs_gui()
```

```text
MNBS_GUI Open the MATLAB interface for Multiplex-NBS.

  fig = mnbs_gui()

  A local window to load a MAT file (W with group, or W with model), set
  the analysis options, run the permutations with progress and
  cancellation, view components and save the results. Requires MATLAB
  R2021a or newer; no other toolbox and no internet connection is needed.
  The standalone desktop app (no MATLAB needed) is available from the
  project's Releases page.

  See also MNBS_ANALYZE, MNBS_LOAD_DEMO.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_demo

```matlab
[W,group,frequencies,nodeLabels] = mnbs_demo(seed)
```

```text
MNBS_DEMO Generate a small synthetic dataset in MATLAB.

  [W, group, frequencies, nodeLabels] = mnbs_demo()
  [W, group, frequencies, nodeLabels] = mnbs_demo(seed)

  Returns 40 simulated observations (two groups of 20) of a 12-region
  network in 10 frequency bins (4-22 Hz). Group 1 has a positive effect
  along regions 1-4 in bins 3-6. Use it to try the functions without data;
  it is not a validation of statistical power. The bundled datasets shared
  with Python and the app are loaded with MNBS_LOAD_DEMO.

  Inputs
    seed   random seed [7]

  Outputs
    W            S-by-1 cell of N-by-N-by-L matrices
    group        S-by-1 numeric labels (1 or 2)
    frequencies  1-by-L axis values (Hz)
    nodeLabels   1-by-N cell of region names

  Example
    [W, group, f] = mnbs_demo();
    result = mnbs_analyze(W, group, struct('nPerm', 499, 'axisName', 'Frequency', ...
                                          'axisUnit', 'Hz', 'axisValues', f));

  See also MNBS_LOAD_DEMO, MNBS_ANALYZE.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_edgestat_group

```matlab
stats = mnbs_edgestat_group(W, group, opts)
```

```text
MNBS_EDGESTAT_GROUP Edge-by-layer statistics for two groups or pairs.

  stats = mnbs_edgestat_group(W, group)
  stats = mnbs_edgestat_group(W, group, opts)

  Welch t for two independent groups (first sorted label minus second) or
  paired t (first observation of each pair minus second) at every
  upper-triangle edge and layer. No permutation is done.

  Inputs
    W      S-by-1 cell of N-by-N-by-L matrices
    group  S-by-1 group labels or pair IDs
    opts   struct: .test ('two-sample' or 'paired'), .tail (for the
           parametric p-values only), .freqMask, .useAbs, .nanPolicy, .pairs

  Output
    stats  struct: .Tef (edges-by-layers statistics), .Pef (uncorrected
           p-values), .Dfef, .Tmap / .Pmap (N-by-N-by-L), .iUT / .jUT (edge
           endpoints), group labels and sizes

  The uncorrected p-values are descriptive; use MNBS_ANALYZE for inference.

  See also MNBS_EDGESTAT_GLM, MNBS_COMPONENTS, MNBS_ANALYZE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_edgestat_glm

```matlab
stats = mnbs_edgestat_glm(W, model, opts)
```

```text
MNBS_EDGESTAT_GLM Edge-by-layer GLM t or F statistics.

  stats = mnbs_edgestat_glm(W, model)
  stats = mnbs_edgestat_glm(W, model, opts)

  Fits the design at every upper-triangle edge and layer and returns the
  contrast statistic. No permutation is done.

  Inputs
    W      S-by-1 cell of N-by-N-by-L matrices
    model  struct: .X (S-by-p, include an intercept), .C (1-by-p for t,
           k-by-p for F), .statType ('t' or 'F')
    opts   struct: .freqMask, .useAbs, .nanPolicy, .tail (t p-values only)

  Output
    stats  struct: .Tef (edges-by-layers t or F; the field name is kept for
           compatibility), .Pef, degrees of freedom, maps and edge indices

  See also MNBS_EDGESTAT_GROUP, MNBS_PERMUTE_GLM, MNBS_ANALYZE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_components

```matlab
clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0, tail, clusterMetric, layerAdjacency)
```

```text
MNBS_COMPONENTS Connected components of region-layer sites.

  clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0)
  clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0, tail, clusterMetric, layerAdjacency)

  Keeps edges whose statistic exceeds the threshold t0. A kept edge joins
  its two regions within a layer; with 'consecutive' adjacency a region
  active in two neighbouring layers is also joined to itself. No inference
  is done here.

  Inputs
    Tef             edges-by-layers statistic map
    iUT, jUT        endpoints of each edge (upper triangle, 1-based)
    nNodes          number of regions
    t0              primary threshold
    tail            'right', 'left' or 'both' (signs kept separate)  ['right']
    clusterMetric   'extent' (number of sites) or 'mass'             ['extent']
    layerAdjacency  'consecutive' or 'independent'                   ['consecutive']

  Output
    clusters  struct array: .nodes, .layerBins (also .freqBins), .extent,
              .mass, .testStat (the chosen metric), .tail, .nodeFreqIdx
              (sites), .nodeMask and .nodeMass

  See also MNBS_EDGESTAT_GROUP, MNBS_PERMUTE, MNBS_ANALYZE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_permute

```matlab
[clustersObs, nullMaxCluster, statsObs] = mnbs_permute(W, groupLabels, opts)
```

```text
MNBS_PERMUTE Permutation null for two-sample and paired designs.

  [clustersObs, nullMax, statsObs] = mnbs_permute(W, groupLabels, opts)

  Computes the observed edge statistics and components, then repeats the
  component search after shuffling group labels (two-sample) or swapping
  conditions within pairs (paired), recording the largest component of
  each permutation. MNBS_ANALYZE calls this after validating inputs; call
  it directly only to build a custom pipeline.

  Inputs
    W            S-by-1 cell of N-by-N-by-L matrices
    groupLabels  S-by-1 group labels or pair IDs
    opts         struct: .t0 (required), .nPerm, .rngSeed, .tail,
                 .clusterMetric, .layerAdjacency, .test ('two-sample' or
                 'paired'), .pairs, .exchangeBlocks, .useParallel, .progress

  Outputs
    clustersObs  observed components (see MNBS_COMPONENTS)
    nullMax      nPerm-by-1 largest component statistic per permutation
    statsObs     observed edge statistics (see MNBS_EDGESTAT_GROUP)

  See also MNBS_ANALYZE, MNBS_PERMUTE_GLM, MNBS_SUMMARIZE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_permute_glm

```matlab
[clustersObs, nullMaxCluster, statsObs] = mnbs_permute_glm(W, model, permSpec, opts)
```

```text
MNBS_PERMUTE_GLM Permutation null for a general linear model.

  [clustersObs, nullMax, statsObs] = mnbs_permute_glm(W, model, permSpec, opts)

  Observed GLM edge statistics and components, then the largest component
  under each permutation. MNBS_ANALYZE calls this after validating inputs.

  Inputs
    W         S-by-1 cell of N-by-N-by-L matrices
    model     struct: .X (S-by-p), .C (1-by-p for t, k-by-p for F),
              .statType ('t' or 'F'), optional .regressorNames, .designName
    permSpec  struct: .method ('auto' = Freedman-Lane, 'freedman-lane',
              'rowshuffle'), .nPerm, .exchangeBlocks, .useParallel, .rngSeed
    opts      struct: .t0 (required), .tail, .clusterMetric,
              .layerAdjacency, .freqMask, .useAbs, .progress

  Outputs
    clustersObs, nullMax, statsObs as in MNBS_PERMUTE.

  Freedman-Lane permutes residuals of the reduced model and is generally
  approximate when nuisance regressors are present; 'rowshuffle' permutes
  whole design rows and is exact only if that matches the randomisation.

  See also MNBS_ANALYZE, MNBS_EDGESTAT_GLM, MNBS_PERMUTE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_summarize

```matlab
[pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMaxCluster, opts)
```

```text
MNBS_SUMMARIZE Corrected p-values and a summary of observed components.

  [pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMax)
  [pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMax, opts)

  p_FWE = (1 + number of permutation maxima >= observed) / (nPerm + 1).

  Inputs
    clustersObs  observed components (MNBS_COMPONENTS)
    nullMax      largest component statistic in each permutation
    opts         struct: .alpha [0.05], .alphaStrict [0.01],
                 .usePlusOne [true], .verbose [true], .sortBy ['stat'],
                 .nullPercentiles [50 90 95 99]

  Outputs
    pvals     corrected p-value of each observed component
    sigTable  table of components with p_FWE <= alpha
    report    struct: counts, null-distribution percentiles and settings

  See also MNBS_ANALYZE, MNBS_PERMUTE.

  Original implementation: Darren S. Kadis (March 2026).
  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_selftest

```matlab
mnbs_selftest()
```

```text
MNBS_SELFTEST Run the toolbox's regression checks.

  mnbs_selftest()

  Checks clustering, the t distribution, symmetry, deterministic
  permutations, t^2 = F, input validation and a golden fixture shared with
  the Python package. Run after adding the matlab folder to the path; an
  error is raised if any check fails. No additional toolbox is required.

  See also MNBS_ANALYZE.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```

## mnbs_tcdf

```matlab
p = mnbs_tcdf(t, df)
```

```text
MNBS_TCDF Student-t cumulative distribution (base MATLAB only).

  p = mnbs_tcdf(t, df)

  Computed with the incomplete beta function, so the Statistics and
  Machine Learning Toolbox is not needed. Used internally.

  Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
  https://github.com/Minarose/multiplex-nbs
```
