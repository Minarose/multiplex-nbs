# Multiplex-NBS: node–layer cluster inference

The motivating application is frequency-resolved connectivity. A global
network-summary curve retains the frequency axis but discards the identities
of participating connections. Separate band analyses retain a within-band
network but do not build a component through neighboring bins, and require
an across-band multiplicity plan. Multiplex-NBS instead defines components in
node × layer space while preserving the retained edge map for description.
Time or another ordered measurement can replace frequency; the implementation
supports one layer axis, not a simultaneous time × frequency graph.

For each undirected edge and layer, fit the chosen statistic. A positive-tail edge is retained if t > t0; a negative-tail edge if t < −t0. F uses F > t0. Thresholds are strict and expressed in statistic units.

Each retained edge connects its two node–layer sites within that layer. With consecutive adjacency, a node active in two consecutive layers connects across those layers. With independent adjacency, slices have no cross-layer links; the permutation maximum is still shared across all slices. The axis may represent time, frequency, or another ordered measurement; labels do not affect inference and numerical spacing does not weight adjacency. Connected components in this graph form the inferential clusters.

The node set and edge configuration may change across layers. In one sign's
thresholded graph, A–B at layer 1 can connect to B–C at layer 2 through the two
active copies of B; this component contains four node–layer sites. A–B at layer
1 and C–D at layer 2 do not connect solely because their layers are neighbors.
An active site is defined by a retained incident edge, not by a separate
inferential test of the node. With two-sided testing, signs remain separate.

The neighborhood is specified before inference. Spectral smoothing and finite
windowing can motivate adjacency, but the rule neither estimates cross-frequency
coupling nor guarantees a sensitivity gain. Choose a layer grid and neighborhood
that match the estimand and data preparation; irregular physical spacing still
receives the same order-based adjacency. See [Interpreting results](interpreting-results.md)
for what a component does and does not show.
* **Extent:** number of unique node–layer sites in the component.
* **Mass:** sum of tail-adjusted edge statistics, allocating half to each endpoint. Since a retained edge's endpoints belong to the same component, the two halves conserve its entire contribution. This is raw statistic mass, not excess above the primary threshold.

Extent is not an edge count. Even with one layer, a three-node chain has extent
3 here and edge extent 2 in conventional NBS. A three-node triangle also has
extent 3 here. Adding layers changes the component graph, not the meaning of an
edgewise test or the assumptions required for resampling.

Each permutation refits the statistic map and reconstructs all clusters. Its largest cluster statistic (zero when no cluster exists) enters the null distribution. For observed statistic m and B random permutations, pFWE = (1 + number of null maxima ≥ m)/(B + 1). The implementation samples with replacement; the plus-one construction prevents zero p-values. For two-sided t inference, signs form separate components and each permutation contributes the maximum over both signs. The correction family is the clusters in this one configured analysis, not all thresholds/designs explored by a user.

Independent data use Welch statistics and label permutations. Paired data use paired t statistics and one sign per subject's entire difference map. GLM uses least squares and either Freedman–Lane or explicit raw row shuffling. Freedman–Lane constructs a null design X0 = X null(C), fits Y under X0, shuffles reduced-model residual rows within allowed blocks, adds them to fitted null data, and refits the full model. F contrasts use their independent contrast rank.

Assumptions cannot be verified from connectivity matrices alone. Labels/rows must be exchangeable under the null; studentization does not guarantee exactness for unequal distributions. Sign flips require symmetric differences. Nuisance-regressor residual permutations are generally approximate. Fixed-effect subject designs and complex repeated measurements need design-specific review. Global-null maximum-cluster calibration does not justify inference about every constituent edge/site or establish strong localized familywise control under every partial alternative.

The software checks data and design structure but does not establish
exchangeability from a matrix file. It does not automatically generate a valid
repeated-measures model. The corrected p-value belongs to the component:
membership and its spectral/time span are descriptive, not individually
corrected locations or precise onset, offset, duration, or frequency boundaries.
Development tests, a planted demo, and limited null simulations do not establish
comparative power or calibration for every intended use.

The method is motivated by NBS and cluster permutation inference but the graph and extent are different from conventional edge-component NBS. Adjacent layers encode the analysis neighborhood rather than measured cross-frequency coupling, temporal causality, or interactions between layers. The original six MATLAB utilities are retained for provenance; the participant-specific working script is excluded. Interpretation and reporting guidance is in [Interpreting results](interpreting-results.md).
