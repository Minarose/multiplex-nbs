# Interpreting results

## What a component is

Each edge (and, for stacks, each layer) is tested. Edges whose statistic exceeds the
primary threshold are kept. Kept edges that share regions form a **component**. In
Multiplex-NBS a region active in two neighbouring layers is also linked to itself, so
one component can span several time points or frequencies.

## What the corrected p-value means

The p-value of a component compares its size with the largest component found in each
permutation of the data. It controls the chance of declaring *any* false component
anywhere in the tested network and layers (family-wise error).

You can say: *the network differed between conditions across this set of regions and
layers (corrected p = …).*

You cannot say:

- that any single edge, region or layer inside the component is significant on its own;
- that the first and last layers of a component mark where the effect starts or stops
  (they describe the component, not a corrected estimate of its timing or frequency).

## Choosing settings

Decide the method, design, threshold, tail and component measure **before** looking at
results. Trying several and keeping the best adds comparisons that the correction does
not cover. Use at least 5000 permutations for reported results; the smallest possible
p-value is 1/(permutations + 1).

| Measure | Counts | Use when |
|---|---|---|
| Extent | region–layer sites (edges in classic mode) | the default; effects that are broad |
| Mass / intensity | summed statistic (excess over threshold in classic mode) | strong, focal effects |

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
