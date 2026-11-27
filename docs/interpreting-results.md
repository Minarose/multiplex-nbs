# Interpreting results

## What a component is

Each edge (and, for stacks, each layer) is tested. Edges whose statistic exceeds the
primary threshold are kept. Kept edges that share regions form a **component**. In
Multiplex-NBS a region active in two neighbouring layers is also linked to itself, so
one component can span several time points or frequencies.

## What the corrected p-value means

The corrected p-value applies to the connected component as a whole, not to individual
edges, regions, or layers. It compares the component's extent or mass with the maximum
component statistic obtained in each permutation of the data, and so controls the chance
of declaring *any* false component anywhere in the tested network and layers
(family-wise error). One is added to both the numerator and the denominator to account
for the observed result: p = (1 + permutations at least as large) / (1 + permutations).

**What you can say.** A significant component identifies a connected pattern of network
differences or associations that is unlikely under the null hypothesis, after correction
for multiple comparisons. The component identifies the regions and layers contributing
to this pattern.

**What you cannot say:**

- that any individual edge, region, or layer within a significant component is
  independently significant;
- that the component's boundaries identify precisely where an effect begins or ends.
  Its spatial and layer-wise extent is descriptive.

## Choosing settings

Choose the method, primary threshold, statistical contrast, and component metric
**before** confirmatory analysis. Exploring alternative settings can help assess
robustness, but selecting results based on significance introduces additional
comparisons not accounted for by the permutation correction. The apps, command line,
Python and MATLAB functions use 9,999 permutations by default; use at least 5000 for
reported results. The smallest possible p-value is 1/(permutations + 1).

| Measure | Counts | Use when |
|---|---|---|
| Extent | region–layer sites (edges in classic mode) | the default; effects that are broad |
| Mass | summed statistic of the component's suprathreshold edges, as in FSL randomise, FieldTrip and MNE | effects that are broad, strong or both |
| Intensity | mass with the threshold subtracted from each edge, as in the NBS toolbox | strong, focal effects |

Mass and intensity differ by the threshold times the number of edges, so they can rank
components differently and give different p-values. In the apps, intensity is selected by
choosing Mass and ticking **Subtract the threshold from each edge**.

## Outputs

| File | Contains |
|---|---|
| Report (`.txt`) | Summary, notes, every component with its regions and layers, a methods paragraph and all settings |
| Component table (`.csv`) | One row per component: sign, extent, mass, corrected p, member regions and layers |
| Full results (`.json`) | Everything to reproduce or re-plot: settings, memberships, edge statistics for every layer, all permutation maxima |
| MATLAB results (`.mat`) | The same, with the main arrays as MATLAB variables |
| Figure (`.svg`) | The current figure as an editable vector graphic (app) |

## What to report

1. Software and version (Multiplex-NBS 0.1.0; cite `CITATION.cff`) and the method
   (classic, layer-wise or multiplex NBS).
2. Design, edge statistic and permutation scheme.
3. Primary threshold and tail, component measure, number of permutations and seed.
4. For each significant component: corrected p, size, number of regions, layer range,
   and member regions (supplementary table).
5. The methods paragraph generated with every result is a starting point; edit it to
   your study.
